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
mocking cannot do as directly (it only sees the outer Google request
body).
"""

import ast
import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

from app.agents import a7_remediation
from app.agents.a7_remediation import A7_ELIGIBLE_CONFIDENCE, synthesize_capa
from app.agents.c3_gateway import ACTION_CATEGORIES
from app.llm_router import LLMResponse

A7_MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "agents" / "a7_remediation.py"

FINDING: Dict[str, Any] = {
    "finding_id": "A2-ANNEX11-S4-DOC-001-DOC-2026-URS-01",
    "claim": "URS traceability incomplete for GXP-MFG-DEMO-01.",
    "regulatory_citations": ["ANNEX11-S4-DOC-001"],
    "evidence_ids": ["DOC-2026-URS-01"],
    "target_system": "GXP-MFG-DEMO-01",
}

CAPA_NARRATIVE_JSON = json.dumps(
    {
        "root_cause": "Root cause narrative from the model.",
        "corrective_action": "Corrective action narrative from the model.",
        "preventive_action": "Preventive action narrative from the model.",
        "effectiveness_check": "Effectiveness-check narrative from the model.",
    }
)


async def _fake_call_llm_success(**kwargs) -> LLMResponse:
    _fake_call_llm_success.captured_kwargs = kwargs
    return LLMResponse(
        text=CAPA_NARRATIVE_JSON,
        model_id="gemini-2.5-flash",
        provider="google",
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
        assert model_id == "gemini-2.5-flash"

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
        return LLMResponse(text="not valid json", model_id="gemini-2.5-flash", provider="google", degraded=False)

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
