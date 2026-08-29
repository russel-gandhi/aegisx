"""
Tests for `app.agents.a7_remediation` — Critical-review coverage (Phase 5,
plan 05-04, Task 2).

Ticket: SENT-4-05 | Requirement: REM-01 | CLAUDE.md Rule 6

Covers the plan's `<behavior>` list (confidence-eligibility fail-closed
gate, non-empty justification, six-field CAPA payload, thirty-day
due_date, deterministic-fallback attribution, untrusted-data prompt
labelling) plus the Critical-review additions: an AST gate proves this
module never imports the verifier, a positive counterpart AST check
proves it DOES import `call_llm` (the deterministic-first boundary from
both sides), and the due-date/degraded-attribution/prompt-labelling
tests named explicitly by the plan.

`call_llm` is faked by monkeypatching the name this module imported into
its own namespace (`app.agents.a7_remediation.call_llm`) — this needs no
provider key, matches `tests/test_a2_compliance.py`'s "no provider key
needed" goal, and lets `test_prompt_labels_finding_text_as_untrusted`
capture the exact prompt text passed to the fake, which respx-level HTTP
mocking cannot do as directly (it only sees the outer request body). The
fake's `model_id`/`provider` values are the Groq ones (260826-rsw moved
remediation off `gemini_flash_thinking` onto `groq_gpt_oss`) — the fake
stands in for a Groq request/response shape, not a Google one. The
respx-level tests added by 260826-rsw (`GROQ_API_KEY`, no `call_llm`
monkeypatch, a mocked Groq endpoint) are the proof that the flag actually
reaches the wire from A7's own call site; the monkeypatch-based tests
above remain provider-agnostic by design.
"""

import ast
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import httpx
import pytest
import respx

from app.agents import a7_remediation
from app.agents.a7_remediation import A7_ELIGIBLE_CONFIDENCE, synthesize_capa
from app.agents.c3_gateway import ACTION_CATEGORIES
from app.llm_router import LLMResponse

A7_MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "agents" / "a7_remediation.py"

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

FINDING: Dict[str, Any] = {
    "finding_id": "A2-ANNEX11-S4-DOC-001-DOC-2026-URS-01",
    "claim": "URS traceability incomplete for GXP-MFG-DEMO-01.",
    "regulatory_citations": ["ANNEX11-S4-DOC-001"],
    "evidence_ids": ["DOC-2026-URS-01"],
    "target_system": "GXP-MFG-DEMO-01",
}

CAPA_NARRATIVE_FIELDS_DICT = {
    "root_cause": "Root cause narrative from the model.",
    "corrective_action": "Corrective action narrative from the model.",
    "preventive_action": "Preventive action narrative from the model.",
    "effectiveness_check": "Effectiveness-check narrative from the model.",
}

CAPA_NARRATIVE_JSON = json.dumps(CAPA_NARRATIVE_FIELDS_DICT)


def _groq_body(text: str, model: str = "openai/gpt-oss-120b") -> dict:
    """Copied from `tests/test_routes_actions.py`'s own `_openai_body`
    helper convention rather than invented fresh (260826-rsw Task 1f)."""
    return {"choices": [{"message": {"content": text}}], "model": model}


async def _fake_call_llm_success(**kwargs) -> LLMResponse:
    _fake_call_llm_success.captured_kwargs = kwargs
    return LLMResponse(
        text=CAPA_NARRATIVE_JSON,
        model_id="openai/gpt-oss-120b",
        provider="groq",
        degraded=False,
    )


async def _fake_call_llm_degraded(**kwargs) -> LLMResponse:
    return LLMResponse(text="", model_id="", provider="", degraded=True, failure_reason="missing_key:test")


# --- <behavior>: confidence eligibility, fail-closed ------------------------


def test_synthesize_capa_returns_none_for_insufficient_evidence():
    async def run():
        proposal, reason = await synthesize_capa(FINDING, {"confidence": "INSUFFICIENT_EVIDENCE"})
        assert proposal is None
        assert reason == "not-eligible"

    asyncio.run(run())


@pytest.mark.parametrize(
    "confidence",
    ["INSUFFICIENT_EVIDENCE", "UNVERIFIED", "", "MAYBE"],
)
def test_synthesize_capa_fails_closed_for_ineligible_confidence(confidence, monkeypatch):
    """The adjacent-field trap this test guards against: A2 writes the
    fixed literal 'UNVERIFIED' into finding['confidence_score'] for every
    finding it emits. A function reading that field instead of C1's
    verification_result['confidence'] would reject everything here — and
    a future edit inverting this test would accept everything unverified,
    which is the REM-01 violation this guard exists to prevent."""
    monkeypatch.setattr(a7_remediation, "call_llm", _fake_call_llm_success)

    async def run():
        proposal, reason = await synthesize_capa(FINDING, {"confidence": confidence})
        assert proposal is None
        assert reason == "not-eligible"

    asyncio.run(run())


@pytest.mark.parametrize("confidence", ["HIGH", "MEDIUM", "LOW"])
def test_synthesize_capa_returns_a_proposal_for_each_eligible_confidence(confidence, monkeypatch):
    monkeypatch.setattr(a7_remediation, "call_llm", _fake_call_llm_success)

    async def run():
        proposal, model_id = await synthesize_capa(FINDING, {"confidence": confidence})
        assert proposal is not None
        assert model_id == "openai/gpt-oss-120b"

    asyncio.run(run())


def test_eligible_confidence_set_is_exactly_high_medium_low():
    assert sorted(A7_ELIGIBLE_CONFIDENCE) == ["HIGH", "LOW", "MEDIUM"]


# --- <behavior>: proposal shape ---------------------------------------------


def test_proposal_carries_non_empty_justification_action_type_and_target_system(monkeypatch):
    monkeypatch.setattr(a7_remediation, "call_llm", _fake_call_llm_success)

    async def run():
        proposal, _ = await synthesize_capa(FINDING, {"confidence": "HIGH"})
        assert proposal["justification"]
        assert proposal["action_type"] in ACTION_CATEGORIES
        assert proposal["target_system"] == FINDING["target_system"]

    asyncio.run(run())


def test_proposal_payload_carries_findings_citations_and_evidence_ids(monkeypatch):
    monkeypatch.setattr(a7_remediation, "call_llm", _fake_call_llm_success)

    async def run():
        proposal, _ = await synthesize_capa(FINDING, {"confidence": "HIGH"})
        payload = proposal["payload"]
        assert payload["regulatory_citations"] == FINDING["regulatory_citations"]
        assert payload["evidence_ids"] == FINDING["evidence_ids"]

    asyncio.run(run())


def test_capa_payload_has_exactly_the_six_capa_proposal_field_names(monkeypatch):
    monkeypatch.setattr(a7_remediation, "call_llm", _fake_call_llm_success)

    async def run():
        proposal, _ = await synthesize_capa(FINDING, {"confidence": "HIGH"})
        capa = proposal["payload"]["capa"]
        assert set(capa.keys()) == {
            "root_cause",
            "corrective_action",
            "preventive_action",
            "effectiveness_check",
            "due_date",
            "owner",
        }

    asyncio.run(run())


# --- Critical-review addition: due_date exactly thirty days out -----------


def test_capa_due_date_is_exactly_thirty_days_out(monkeypatch):
    monkeypatch.setattr(a7_remediation, "call_llm", _fake_call_llm_success)

    async def run():
        before = datetime.now(timezone.utc).replace(tzinfo=None)
        proposal, _ = await synthesize_capa(FINDING, {"confidence": "HIGH"})
        due_date = datetime.fromisoformat(proposal["payload"]["capa"]["due_date"])
        expected = before + timedelta(days=30)
        assert abs((due_date - expected).total_seconds()) < 10

    asyncio.run(run())


# --- Critical-review addition: degraded router still produces a proposal --


def test_degraded_router_still_produces_a_proposal_with_fallback_attribution(monkeypatch):
    monkeypatch.setattr(a7_remediation, "call_llm", _fake_call_llm_degraded)

    async def run():
        proposal, model_id = await synthesize_capa(FINDING, {"confidence": "MEDIUM"})
        assert proposal is not None
        assert model_id == "deterministic-fallback"
        capa = proposal["payload"]["capa"]
        assert set(capa.keys()) == {
            "root_cause",
            "corrective_action",
            "preventive_action",
            "effectiveness_check",
            "due_date",
            "owner",
        }

    asyncio.run(run())


# --- Critical-review addition: malformed JSON also falls back safely ------


def test_malformed_json_narrative_falls_back_to_deterministic_capa(monkeypatch):
    async def fake_call_llm_malformed(**kwargs) -> LLMResponse:
        return LLMResponse(text="not valid json", model_id="openai/gpt-oss-120b", provider="groq", degraded=False)

    monkeypatch.setattr(a7_remediation, "call_llm", fake_call_llm_malformed)

    async def run():
        proposal, model_id = await synthesize_capa(FINDING, {"confidence": "LOW"})
        assert proposal is not None
        assert model_id == "deterministic-fallback"

    asyncio.run(run())


# --- Critical-review addition: prompt labels finding text as untrusted ----


def test_prompt_labels_finding_text_as_untrusted(monkeypatch):
    monkeypatch.setattr(a7_remediation, "call_llm", _fake_call_llm_success)

    async def run():
        await synthesize_capa(FINDING, {"confidence": "HIGH"})
        prompt = _fake_call_llm_success.captured_kwargs["prompt"]
        assert FINDING["claim"] in prompt
        assert "untrusted" in prompt.lower()

    asyncio.run(run())


# --- 260826-rsw: guard against a future edit dropping task/json_output ----


def test_synthesize_capa_calls_call_llm_with_remediation_task_and_json_output(monkeypatch):
    """The guard against a future edit silently dropping the remediation
    task key or the json_output=True flag at the call site -- the exact
    class of regression this plan exists to prevent from being silent."""
    monkeypatch.setattr(a7_remediation, "call_llm", _fake_call_llm_success)

    async def run():
        await synthesize_capa(FINDING, {"confidence": "HIGH"})
        kwargs = _fake_call_llm_success.captured_kwargs
        assert kwargs["task"] == "remediation"
        assert kwargs["json_output"] is True

    asyncio.run(run())


# --- 260826-rsw: respx-level proof -- json mode actually reaches the wire -


def test_respx_synthesize_capa_through_real_call_llm_reaches_groq_with_json_mode(monkeypatch):
    """The proof that matters (plan constraint): drives the REAL call_llm
    against a mocked Groq endpoint and asserts three things together --
    the outbound request body carries JSON mode, the returned proposal's
    four narrative values are the model's own strings (not the template),
    and the attribution is the provider-reported model id. Any one alone
    can pass while the json_output plumbing is silently broken."""
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")

    async def _run():
        with respx.mock:
            route = respx.post(GROQ_ENDPOINT).mock(
                return_value=httpx.Response(
                    200, json=_groq_body(CAPA_NARRATIVE_JSON, model="openai/gpt-oss-120b")
                )
            )
            proposal, model_id = await synthesize_capa(FINDING, {"confidence": "HIGH"})
            return proposal, model_id, route

    proposal, model_id, route = asyncio.run(_run())

    assert route.called
    sent_body = json.loads(route.calls.last.request.content)
    assert sent_body["response_format"] == {"type": "json_object"}

    assert proposal is not None
    assert model_id == "openai/gpt-oss-120b"
    capa = proposal["payload"]["capa"]
    for field, expected_text in CAPA_NARRATIVE_FIELDS_DICT.items():
        assert capa[field] == expected_text


def test_respx_null_content_groq_truncation_falls_back_and_logs_a_warning(monkeypatch, caplog):
    """A Groq reasoning-model truncation (finish_reason='length', null
    message content) must be handled -- not raised -- and must not be
    silent: `_parse_openai_compatible_response` coerces None to '', which
    then fails json.loads, landing in the logged parse-failure branch."""
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")

    async def _run():
        with respx.mock:
            route = respx.post(GROQ_ENDPOINT).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "choices": [{"message": {"content": None}, "finish_reason": "length"}],
                        "model": "openai/gpt-oss-120b",
                    },
                )
            )
            with caplog.at_level(logging.WARNING):
                proposal, model_id = await synthesize_capa(FINDING, {"confidence": "MEDIUM"})
            return proposal, model_id, route

    proposal, model_id, route = asyncio.run(_run())

    assert route.called
    assert proposal is not None
    assert model_id == "deterministic-fallback"
    assert any("openai/gpt-oss-120b" in record.getMessage() for record in caplog.records)


# --- 260826-rsw: wall-clock ceiling is bounded, not roughly doubled -------


def test_ceiling_breach_returns_deterministic_fallback_within_roughly_the_ceiling(monkeypatch):
    """Design Note 4's property: on a hanging provider, synthesize_capa
    returns within roughly A7_REMEDIATION_CEILING_SECONDS, not roughly
    twice it -- proving the outer asyncio.wait_for is the real ceiling,
    not merely call_llm's own (reused-for-cascade) timeout argument."""

    async def _hanging_call_llm(**kwargs):
        await asyncio.sleep(a7_remediation.A7_REMEDIATION_CEILING_SECONDS * 3)
        return LLMResponse(text="unreachable", model_id="unreachable", provider="groq", degraded=False)

    monkeypatch.setattr(a7_remediation, "call_llm", _hanging_call_llm)

    async def run():
        start = asyncio.get_event_loop().time()
        proposal, model_id = await synthesize_capa(FINDING, {"confidence": "LOW"})
        elapsed = asyncio.get_event_loop().time() - start
        return proposal, model_id, elapsed

    proposal, model_id, elapsed = asyncio.run(run())

    assert proposal is not None
    assert model_id == "deterministic-fallback"
    assert elapsed < a7_remediation.A7_REMEDIATION_CEILING_SECONDS * 2


# --- Critical-review addition: AST gate -- A7 never imports the verifier --


def test_a7_never_imports_the_verifier():
    """REM-01: A7 reads C1's already-computed verdict and must never
    duplicate C1's authority by re-running verification itself."""
    source = A7_MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(A7_MODULE_PATH))

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            assert not module_name.endswith("c1_verifier"), (
                f"a7_remediation.py imports from {module_name!r} -- A7 must "
                "never import the verifier module (REM-01)."
            )
            for alias in node.names:
                assert alias.name not in ("verify_finding", "calculate_confidence"), (
                    f"a7_remediation.py imports {alias.name!r} -- A7 must "
                    "never re-run verification (REM-01)."
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.endswith("c1_verifier"), (
                    f"a7_remediation.py imports {alias.name!r} -- A7 must "
                    "never import the verifier module (REM-01)."
                )


def test_a7_is_the_only_module_permitted_a_model_call_in_this_phase():
    """Positive counterpart to the C2/C3 no-model-dependency gates: A7 is
    the one node in this phase permitted to call a model (Bible Section
    1.3's deterministic-first boundary, viewed from both sides)."""
    source = A7_MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(A7_MODULE_PATH))

    imported_names: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported_names.extend(alias.name for alias in node.names)

    assert "call_llm" in imported_names
