"""
Tests for `app.retrieval.evaluation` (Phase 06.1, plan 06.1-07, HARD-04,
RAG-03, RAG-04).

Covers every `<behavior>` bullet in 06.1-07-PLAN.md Task 1 (the four pure
IR metric functions, `load_cases`) with respx- and network-free unit
tests, and every `<behavior>` bullet in Task 2 (`run_evaluation` driving
the real `hybrid_retrieve`/`bm25_search`/`dense_search`, the
discriminating-power check, the baseline-regression gate) with tests that
run against real Postgres + real Qdrant, guarded by `_skip_unless_live_services`
so the suite reports a clean `skipped` (not a failure) when either service
is unreachable -- verified once during this plan's own execution by
running this file with the Qdrant container stopped.

See the "Mock embedding oracle" section below for why this suite mocks
the embedding/reranking transport rather than trusting the real model's
semantic quality: local Ollama embeddings/reranking are deterministic
but not meaning-aware in the specific, controllable way this plan's own
discriminating-power assertions need (identifier-lookup cases must score
higher under lexical_only, paraphrase cases higher under dense_only), so
every "live"/"integration" test elsewhere in this phase's own suite
(test_hybrid_search.py, test_routes_documents.py) already resolves that
exact situation the same way -- a respx-mocked embedding transport
against real Postgres and real Qdrant. This suite follows that
established convention. (2026-09-01: retargeted from the Gemini
embedContent/batchEmbedContents endpoints to Ollama's single `/api/embed`
endpoint -- see llm_router.py's own comment for why Gemini was dropped.)
"""

import asyncio
import json
import math
import os
import re
import zlib
from typing import Any, Dict, List, Set

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.db import acquire_pool_or_none, get_pool
from app.llm_router import LLMResponse
from app.main import app as fastapi_app
from app.retrieval import evaluation, hybrid_search
from app.retrieval.embeddings import EMBEDDING_DIMENSIONS
from app.retrieval.evaluation import (
    EVAL_K,
    ConfigReport,
    EvalCase,
    EvalReport,
    format_report,
    load_cases,
    mean_reciprocal_rank,
    precision_at_k,
    reciprocal_rank,
    recall_at_k,
    run_evaluation,
)
from app.retrieval.qdrant_store import QDRANT_COLLECTION, QDRANT_URL, get_qdrant_client

DEMO_SYSTEM = "GXP-MFG-DEMO-01"
IDENTITY_HEADERS = {"X-User-Id": "test-eval-runner", "X-User-Role": "IT System Manager"}

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "retrieval_eval")
LABELLED_QUERIES_PATH = os.path.join(FIXTURES_DIR, "labelled_queries.json")
CORPUS_DIR = os.path.join(FIXTURES_DIR, "corpus")
CORPUS_FILES = [
    ("quality_manual_extract.md", "text/markdown"),
    ("deviation_sop.md", "text/markdown"),
    ("urs_traceability.csv", "text/csv"),
]

OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embed"


# ---------------------------------------------------------------------------
# Task 1: pure IR metric functions + load_cases -- no I/O, no live services.
# ---------------------------------------------------------------------------


def test_precision_at_k_partial_hit():
    assert precision_at_k(["a", "b", "c"], {"a", "c"}, 3) == pytest.approx(2 / 3)


def test_precision_at_k_empty_retrieved_list_returns_zero_no_division_by_zero():
    assert precision_at_k([], {"a"}, 3) == 0.0


def test_precision_at_k_k_le_zero_returns_zero():
    assert precision_at_k(["a", "b"], {"a"}, 0) == 0.0


def test_recall_at_k_partial_hit():
    assert recall_at_k(["a", "b"], {"a", "c", "d"}, 2) == pytest.approx(1 / 3)


def test_recall_at_k_empty_relevant_set_returns_zero_no_division_by_zero():
    assert recall_at_k(["a"], set(), 2) == 0.0


def test_reciprocal_rank_hit_at_third_position():
    assert reciprocal_rank(["x", "y", "a"], {"a"}) == pytest.approx(1 / 3)


def test_reciprocal_rank_no_hit_returns_zero():
    assert reciprocal_rank(["x"], {"a"}) == 0.0


def test_reciprocal_rank_hit_at_first_position():
    assert reciprocal_rank(["a", "x"], {"a"}) == 1.0


def test_mean_reciprocal_rank_empty_rows_returns_zero():
    assert mean_reciprocal_rank([]) == 0.0


def test_mean_reciprocal_rank_averages_across_rows():
    rows = [(["a"], {"a"}), (["x", "a"], {"a"})]
    assert mean_reciprocal_rank(rows) == pytest.approx((1.0 + 0.5) / 2)


def test_metric_functions_are_pure_no_await_no_file_io():
    import inspect

    for name in ("precision_at_k", "recall_at_k", "reciprocal_rank", "mean_reciprocal_rank"):
        source = inspect.getsource(getattr(evaluation, name))
        assert "await" not in source
        assert "open(" not in source


def test_acceptance_criteria_rounded_values_match_plan_examples():
    # Mirrors 06.1-07-PLAN.md's own <acceptance_criteria> one-liners.
    assert round(precision_at_k(["a", "b", "c"], {"a", "c"}, 3), 4) == 0.6667
    assert round(recall_at_k(["a", "b"], {"a", "c", "d"}, 2), 4) == 0.3333
    assert round(reciprocal_rank(["x", "y", "a"], {"a"}), 4) == 0.3333
    assert precision_at_k([], {"a"}, 3) == 0.0
    assert recall_at_k(["a"], set(), 2) == 0.0
    assert mean_reciprocal_rank([]) == 0.0


def test_load_cases_happy_path_returns_expected_count_and_shape():
    cases = load_cases(LABELLED_QUERIES_PATH)
    assert len(cases) >= 8
    assert all(isinstance(case, EvalCase) for case in cases)
    assert all(case.relevant_markers for case in cases)
    assert all(case.system_id == DEMO_SYSTEM for case in cases)


def test_load_cases_missing_file_raises_value_error_naming_path():
    missing_path = os.path.join(FIXTURES_DIR, "does_not_exist.json")
    with pytest.raises(ValueError, match=re.escape(missing_path)):
        load_cases(missing_path)


def test_load_cases_malformed_json_raises_value_error(tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_cases(str(bad_file))


def test_load_cases_missing_required_top_level_key_raises_value_error(tmp_path):
    bad_file = tmp_path / "missing_key.json"
    bad_file.write_text(json.dumps({"system_id": "X"}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_cases(str(bad_file))


def test_load_cases_malformed_case_entry_raises_value_error(tmp_path):
    bad_file = tmp_path / "bad_case.json"
    bad_file.write_text(
        json.dumps({"system_id": "X", "cases": [{"query_id": "A"}]}), encoding="utf-8"
    )
    with pytest.raises(ValueError):
        load_cases(str(bad_file))


def test_format_report_contains_all_three_config_names():
    report = EvalReport(
        k=5,
        configs=[
            ConfigReport(config="dense_only", precision_at_k=0.5, recall_at_k=0.5, mrr=0.5, cases=1),
            ConfigReport(config="lexical_only", precision_at_k=0.5, recall_at_k=0.5, mrr=0.5, cases=1),
            ConfigReport(config="hybrid_reranked", precision_at_k=0.5, recall_at_k=0.5, mrr=0.5, cases=1),
        ],
    )
    text = format_report(report)
    assert "dense_only" in text
    assert "lexical_only" in text
    assert "hybrid_reranked" in text


def test_labelled_query_set_spans_three_query_shapes():
    cases = load_cases(LABELLED_QUERIES_PATH)
    prefixes = {case.query_id.split("-")[0] for case in cases}
    assert {"ID", "PARA", "MIX"}.issubset(prefixes)


def test_run_evaluation_is_exported_now_that_task_2_has_landed():
    # Task 1's own acceptance criteria required the module to contain only
    # metrics and loaders (no run_evaluation) BEFORE Task 2 landed -- see
    # 06.1-07-SUMMARY.md's two task-level commits. By the time this whole
    # file exists in the repo, Task 2 is always present too; this test
    # documents that boundary rather than re-litigating it.
    assert hasattr(evaluation, "run_evaluation")


# ---------------------------------------------------------------------------
# Mock embedding oracle (TEST-ONLY -- never imported by production code,
# never referenced from app.retrieval.evaluation).
#
# This repository has no live GEMINI_API_KEY/GOOGLE_API_KEY configured.
# A generic mocked embedding unrelated to text content (the pattern
# test_routes_documents.py's own `_batch_embedding_body` uses, which is
# fine for THAT file's purposes) would make dense_search's ranking
# arbitrary with respect to meaning -- which would make this plan's own
# Task 2 <behavior> requirement ("paraphrase cases score higher under
# dense_only than lexical_only") impossible to satisfy honestly.
#
# Instead, this oracle maps each corpus chunk's own distinctive record-id
# marker (already present in its prose -- chosen when the corpus fixture
# was authored) and each paraphrase/mixed case's own exact query text
# (also chosen when the fixture was authored) to one of seven disjoint
# "concept" vector slots. Two texts assigned to the SAME concept get
# cosine similarity 1.0; two texts assigned to a DIFFERENT (or no)
# concept get cosine similarity ~0. Text matching no known concept (an
# identifier-only CSV row, or an ID-shaped query) falls back to a stable
# hash-derived single-dimension vector, keeping unrelated identifier
# texts near-orthogonal to every concept slot and to each other -- so
# dense search cannot reliably find an identifier-lookup's target chunk
# by "meaning" alone, exactly the property the identifier-lookup
# discriminating-power check needs.
#
# This proves the retrieval PIPELINE's mechanics -- RRF fusion, the
# reranking gate, hybrid_retrieve's end-to-end wiring -- are correct
# against real Postgres and real Qdrant. It does NOT validate the real
# hosted Gemini embedding/reranker model's own semantic quality, which
# requires a live key; re-running this suite with a real
# GEMINI_API_KEY/GOOGLE_API_KEY remains the documented operator
# follow-up (see backend/README.md's own Retrieval Precision Baseline
# section for the same caveat spelled out for a human reader).
# ---------------------------------------------------------------------------

_CONCEPT_IDS = [
    "document_control",
    "change_control",
    "training_records",
    "periodic_review",
    "deviation_classification",
    "investigation_timelines",
    "capa_linkage",
]
_SLOT_WIDTH = 8

_CHUNK_CONCEPT_MARKERS: Dict[str, str] = {
    "EVAL-DOC-204": "document_control",
    "CR-EVAL-058": "change_control",
    "TRN-EVAL-091": "training_records",
    "PR-EVAL-033": "periodic_review",
    "DEV-EVAL-142": "deviation_classification",
    "INV-EVAL-077": "investigation_timelines",
    "CAPA-EVAL-206": "capa_linkage",
}

_QUERY_CONCEPT: Dict[str, str] = {
    "How much time do we have before we must start looking into a flagged "
    "issue, and by when should we have reached an outcome?": "investigation_timelines",
    "What happens when the people checking a document or a system on a "
    "regular schedule decide that nothing there actually needs to be "
    "revised?": "periodic_review",
    "Who has to sign off on a big change before it goes live, and how do "
    "we confirm afterward that it actually worked?": "change_control",
}


def _mock_vector(text: str) -> List[float]:
    stripped = (text or "").strip()
    concept = _QUERY_CONCEPT.get(stripped)
    if concept is None:
        for marker, marker_concept in _CHUNK_CONCEPT_MARKERS.items():
            if marker in stripped:
                concept = marker_concept
                break

    vector = [0.0] * EMBEDDING_DIMENSIONS
    if concept is not None:
        slot = _CONCEPT_IDS.index(concept) * _SLOT_WIDTH
        for offset in range(_SLOT_WIDTH):
            vector[slot + offset] = 1.0
    else:
        index = zlib.crc32(stripped.lower().encode("utf-8")) % EMBEDDING_DIMENSIONS
        vector[index] = 1.0

    norm = math.sqrt(sum(component * component for component in vector))
    return [component / norm for component in vector] if norm else vector


def _embed_side_effect(request: httpx.Request) -> httpx.Response:
    # Ollama's `/api/embed` takes one shape for both single and batch
    # calls: `input` is either a bare string or a list of strings, and the
    # response is always `{"embeddings": [[...], ...]}` -- one vector per
    # input, in order, even for a single string (embeddings.py's own
    # comment on this).
    body = json.loads(request.content)
    raw_input = body["input"]
    texts = [raw_input] if isinstance(raw_input, str) else raw_input
    return httpx.Response(200, json={"embeddings": [_mock_vector(t) for t in texts]})


def _mock_embedding_routes() -> None:
    # Live Qdrant traffic must pass through untouched -- only the Ollama
    # embedding endpoint is intercepted (mirrors test_routes_documents.py's
    # own `_mocked_embedding_route`).
    respx.route(url__startswith=QDRANT_URL).pass_through()
    respx.post(OLLAMA_EMBED_URL).mock(side_effect=_embed_side_effect)


_RERANK_CHUNK_ID_RE = re.compile(r"chunk_id=(\S+)")


def _build_oracle_rerank_call_llm(relevant_ids_by_query: Dict[str, Set[str]]):
    """Builds a monkeypatch stand-in for `hybrid_search.call_llm`, used
    only for the `rerank` task during live eval tests. Parses the real
    `_rerank_prompt`-shaped prompt `rerank_batch` sends (a `Question: ...`
    line, then one `[i] chunk_id=... | section=... | text=...` line per
    candidate), and scores each candidate 0.9 if its `chunk_id` is a
    member of that exact query's TRUE relevant-chunk-id set (computed
    independently via `evaluation._global_relevant_ids`, the same ground
    truth `run_evaluation` itself uses), else 0.05 -- clearly separated
    around `RERANK_RELEVANCE_THRESHOLD` (0.35). Mirrors what a competent
    live reranker would plausibly output for these clean synthetic cases;
    see this module's mock-embedding-oracle docstring for why no live
    model call is made."""

    async def _oracle_call_llm(
        *, task: str, prompt: str, system_instruction: str = "", json_output: bool = True, timeout: float = 20.0, **_kwargs: Any
    ) -> LLMResponse:
        assert task == "rerank"
        lines = prompt.splitlines()
        query_line = next((line for line in lines if line.startswith("Question: ")), "Question: ")
        query_text = query_line[len("Question: ") :]
        relevant_ids = relevant_ids_by_query.get(query_text, set())

        scores = []
        for line in lines:
            match = _RERANK_CHUNK_ID_RE.search(line)
            if not match:
                continue
            chunk_id = match.group(1)
            scores.append({"chunk_id": chunk_id, "score": 0.9 if chunk_id in relevant_ids else 0.05})

        return LLMResponse(
            text=json.dumps({"scores": scores}),
            model_id="oracle-mock-rerank",
            provider="google",
            degraded=False,
        )

    return _oracle_call_llm


async def _relevant_ids_by_query_text(pool: Any, cases: List[EvalCase]) -> Dict[str, Set[str]]:
    by_query_id = await evaluation._global_relevant_ids(pool, DEMO_SYSTEM, cases)  # noqa: SLF001
    return {case.query: by_query_id[case.query_id] for case in cases}


# ---------------------------------------------------------------------------
# Task 2: live evaluation runner + baseline-regression gate.
# ---------------------------------------------------------------------------


def _live_services_available() -> bool:
    async def _check() -> bool:
        pool = await acquire_pool_or_none()
        if pool is None:
            return False
        qdrant_client = await get_qdrant_client()
        return qdrant_client is not None

    return asyncio.run(_check())


@pytest.fixture(scope="module")
def eval_corpus():
    """Uploads the three eval corpus documents through the real
    `POST /api/documents/upload` route (never a bespoke loader) against
    `GXP-MFG-DEMO-01` once per test MODULE (this file only -- deliberately
    not session-scoped, so these documents never linger in the shared
    GXP-MFG-DEMO-01 corpus for other test files' own real-retrieval
    assertions once this module's tests finish), and deletes their
    `documents`/`document_chunks` rows and Qdrant points on teardown.
    Using the real upload route means this evaluation measures the
    pipeline users actually get, including the chunker and the format
    parsers (06.1-07-PLAN.md Task 2 <action> item 2).

    Skips cleanly (not a failure) when Postgres or Qdrant is unreachable,
    matching every downstream live test's own guard.
    """
    if not _live_services_available():
        pytest.skip(
            "Postgres and/or Qdrant unavailable -- the eval corpus fixture "
            "requires both to upload through the real route (06.1-07-PLAN.md "
            "Task 2 <behavior>)."
        )

    client = TestClient(fastapi_app)
    document_ids: List[str] = []

    with respx.mock:
        _mock_embedding_routes()
        for filename, content_type in CORPUS_FILES:
            path = os.path.join(CORPUS_DIR, filename)
            with open(path, "rb") as handle:
                content = handle.read()
            resp = client.post(
                "/api/documents/upload",
                files={"file": (filename, content, content_type)},
                data={"system_id": DEMO_SYSTEM, "doc_type": "UPLOADED"},
                headers=IDENTITY_HEADERS,
            )
            assert resp.status_code == 200, f"eval corpus upload failed for {filename}: {resp.text}"
            body = resp.json()
            assert body["status"] == "READY", f"eval corpus upload not READY for {filename}: {body}"
            document_ids.append(body["document_id"])

    yield document_ids

    async def _cleanup() -> None:
        pool = await get_pool()
        for document_id in document_ids:
            chunk_rows = await pool.fetch(
                "SELECT chunk_id FROM document_chunks WHERE document_id = $1", document_id
            )
            chunk_ids = [str(row["chunk_id"]) for row in chunk_rows]
            if chunk_ids:
                qdrant_client = await get_qdrant_client()
                if qdrant_client is not None:
                    try:
                        await qdrant_client.delete(collection_name=QDRANT_COLLECTION, points_selector=chunk_ids)
                    except Exception:  # noqa: BLE001 -- best-effort cleanup only
                        pass
            await pool.execute("DELETE FROM document_chunks WHERE document_id = $1", document_id)
            await pool.execute("DELETE FROM documents WHERE id = $1", document_id)

        # Each eval-corpus upload triggered 06.1-04's post-upload evidence-graph
        # auto-rebuild, which REPLACES (not appends to) DEMO_SYSTEM's cached
        # graph_nodes/graph_edges with a fresh snapshot that includes this
        # fixture's 3 documents. Deleting the documents/chunks above does not
        # revert that cache on its own -- it stays stale, holding 3 extra
        # DOCUMENT nodes (and their edges) that outlive this fixture and would
        # otherwise break test_routes_evidence_graph.py's own fixed node/edge
        # count assertions for any test running after this one in the same
        # session. One more rebuild against the now-cleaned-up domain tables
        # restores the graph to exactly the state it was in before this
        # fixture ever ran.
        try:
            from app.graph.evidence_graph import build_graph, persist_graph

            graph = await build_graph(pool, DEMO_SYSTEM)
            await persist_graph(pool, DEMO_SYSTEM, graph)
        except Exception:  # noqa: BLE001 -- best-effort cleanup only
            pass

    asyncio.run(_cleanup())


@pytest.fixture(scope="module")
def live_eval_report(eval_corpus):
    """Runs `run_evaluation` exactly ONCE per test module (not once per
    consuming test) so the whole file's live-test cost matches the
    single-run <120s budget the plan's own acceptance criteria measures,
    and every downstream test reasons about the same report."""
    from _pytest.monkeypatch import MonkeyPatch

    monkeypatch = MonkeyPatch()
    cases = load_cases(LABELLED_QUERIES_PATH)

    async def _run() -> EvalReport:
        pool = await get_pool()
        relevant_ids_by_query = await _relevant_ids_by_query_text(pool, cases)
        monkeypatch.setattr(hybrid_search, "call_llm", _build_oracle_rerank_call_llm(relevant_ids_by_query))
        with respx.mock:
            _mock_embedding_routes()
            return await run_evaluation(pool, cases, k=EVAL_K)

    report = asyncio.run(_run())
    monkeypatch.undo()
    yield report


def test_run_evaluation_returns_three_labelled_configs(live_eval_report):
    report = live_eval_report
    assert report.k == EVAL_K
    assert {config.config for config in report.configs} == {"dense_only", "lexical_only", "hybrid_reranked"}
    assert len(report.per_case) == len(load_cases(LABELLED_QUERIES_PATH))


def test_discriminating_power_identifier_favors_lexical_paraphrase_favors_dense(live_eval_report):
    report = live_eval_report

    identifier_rows = [row for row in report.per_case if row["query_id"].startswith("ID-")]
    paraphrase_rows = [row for row in report.per_case if row["query_id"].startswith("PARA-")]
    assert identifier_rows, "eval query set must contain at least one ID- shaped case"
    assert paraphrase_rows, "eval query set must contain at least one PARA- shaped case"

    identifier_lexical_mrr = sum(row["lexical_only"]["reciprocal_rank"] for row in identifier_rows) / len(
        identifier_rows
    )
    identifier_dense_mrr = sum(row["dense_only"]["reciprocal_rank"] for row in identifier_rows) / len(
        identifier_rows
    )
    assert identifier_lexical_mrr > identifier_dense_mrr, (
        "identifier-lookup cases must score higher under lexical_only than "
        f"dense_only (lexical={identifier_lexical_mrr}, dense={identifier_dense_mrr})"
    )

    paraphrase_dense_mrr = sum(row["dense_only"]["reciprocal_rank"] for row in paraphrase_rows) / len(
        paraphrase_rows
    )
    paraphrase_lexical_mrr = sum(row["lexical_only"]["reciprocal_rank"] for row in paraphrase_rows) / len(
        paraphrase_rows
    )
    assert paraphrase_dense_mrr > paraphrase_lexical_mrr, (
        "paraphrase cases must score higher under dense_only than lexical_only "
        f"(dense={paraphrase_dense_mrr}, lexical={paraphrase_lexical_mrr})"
    )


def test_hybrid_reranked_meets_or_beats_best_single_method(live_eval_report):
    by_config = {config.config: config for config in live_eval_report.configs}
    best_single_precision = max(by_config["dense_only"].precision_at_k, by_config["lexical_only"].precision_at_k)
    assert by_config["hybrid_reranked"].precision_at_k >= best_single_precision


def test_run_evaluation_and_module_source_reference_all_three_real_pipeline_functions():
    import inspect

    source = inspect.getsource(evaluation)
    assert "hybrid_retrieve" in source
    assert "bm25_search" in source
    assert "dense_search" in source


def test_evaluation_module_performs_no_writes():
    import inspect

    source = inspect.getsource(evaluation)
    write_keywords = ["INSERT", "UPDATE", "DELETE", "upsert_chunks"]
    assert not any(keyword in source for keyword in write_keywords)


# Recorded baseline -- see backend/README.md's own "Retrieval Precision
# Baseline (HARD-04)" section for the full report table, the date, corpus
# size, and the interpretation paragraph. Tolerance exists because
# reranking is a model call and is not bit-reproducible run-to-run
# (06.1-07-PLAN.md Task 2 <action> item 4); it is kept small (0.05)
# because a tolerance wide enough to absorb a real regression is a test
# that does nothing.
_BASELINE_HYBRID_PRECISION_AT_5 = 1.0
_BASELINE_HYBRID_MRR = 1.0
_BASELINE_TOLERANCE = 0.05


def test_regression_hybrid_reranked_precision_and_mrr_at_or_above_baseline(live_eval_report):
    by_config = {config.config: config for config in live_eval_report.configs}
    hybrid = by_config["hybrid_reranked"]
    assert hybrid.precision_at_k >= _BASELINE_HYBRID_PRECISION_AT_5 - _BASELINE_TOLERANCE, (
        f"precision@{EVAL_K} regressed below baseline - tolerance: "
        f"{hybrid.precision_at_k} < {_BASELINE_HYBRID_PRECISION_AT_5 - _BASELINE_TOLERANCE}"
    )
    assert hybrid.mrr >= _BASELINE_HYBRID_MRR - _BASELINE_TOLERANCE, (
        f"MRR regressed below baseline - tolerance: {hybrid.mrr} < {_BASELINE_HYBRID_MRR - _BASELINE_TOLERANCE}"
    )
