"""
Tests for `app.retrieval.evaluation` (Phase 06.1, plan 06.1-07, HARD-04,
RAG-03, RAG-04).

Covers every `<behavior>` bullet in 06.1-07-PLAN.md Task 1: the four pure
IR metric functions (`precision_at_k`, `recall_at_k`, `reciprocal_rank`,
`mean_reciprocal_rank`) and `load_cases`. No I/O, no live services, no
network -- Task 1's own acceptance criteria requires this file's tests to
run without Postgres, Qdrant, or a network call.

Task 2 (the live evaluation runner against real Postgres/Qdrant, the
discriminating-power check, the baseline-regression gate) extends this
same file; see 06.1-07-SUMMARY.md for the two task-level commits.
"""

import json
import os
import re

import pytest

from app.retrieval import evaluation
from app.retrieval.evaluation import (
    ConfigReport,
    EvalCase,
    EvalReport,
    format_report,
    load_cases,
    mean_reciprocal_rank,
    precision_at_k,
    reciprocal_rank,
    recall_at_k,
)

DEMO_SYSTEM = "GXP-MFG-DEMO-01"

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "retrieval_eval")
LABELLED_QUERIES_PATH = os.path.join(FIXTURES_DIR, "labelled_queries.json")


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


def test_evaluation_module_contains_only_metrics_and_loaders_before_task_2():
    import inspect

    source = inspect.getsource(evaluation)
    assert "hybrid_retrieve" not in source
