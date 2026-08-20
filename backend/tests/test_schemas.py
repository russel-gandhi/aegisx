"""
Tests for app.schemas — the Bible Section 4.3 Pydantic application-layer
models (SENT-1-05, ENV-04).

Covers the plan's <behavior> list:
- all 12 Section 4.3 classes import from app.schemas
- a fully-populated AgentFinding (with a valid ALCOAScore) validates and
  round-trips through model_dump()
- an AgentFinding missing the required `claim` field raises ValidationError
- an OPAViolation built from the exact dict shape
  data.sentinel.gxp.violation emits validates without adaptation
- ALCOAScore() with no arguments applies the Bible's per-field defaults,
  five of which are True and three of which are False (asserted field by
  field rather than compared as a whole dict, so a failure names the field
  that drifted)
- AgentMessage() populates `timestamp` automatically, with no deprecation
  warning and a naive (tzinfo is None) value
"""

import warnings

import pytest
from pydantic import ValidationError

from app.schemas import (
    ActionProposal,
    AgentExecutionTrace,
    AgentFinding,
    AgentMessage,
    ALCOAScore,
    AuditEvent,
    AuditPackage,
    CAPAProposal,
    ConfidenceAssessment,
    EvidenceRef,
    OPAViolation,
    SystemReadinessScore,
)


def test_all_twelve_models_importable():
    # Import succeeding (module-level, above) already proves this; this
    # test additionally asserts each name really is a class.
    models = [
        EvidenceRef,
        ALCOAScore,
        AgentFinding,
        ActionProposal,
        AgentMessage,
        AuditEvent,
        OPAViolation,
        ConfidenceAssessment,
        CAPAProposal,
        AuditPackage,
        SystemReadinessScore,
        AgentExecutionTrace,
    ]
    assert len(models) == 12
    for model in models:
        assert isinstance(model, type)


def test_agent_finding_valid_instance_round_trips_through_model_dump():
    finding = AgentFinding(
        finding_id="FIND-001",
        claim="URS traceability incomplete for GXP-MFG-DEMO-01",
        regulatory_citations=["ANNEX11-S4-DOC-001"],
        confidence_score="HIGH",
        evidence_ids=["EVID-001"],
        alcoa_score=ALCOAScore(),
        model_attribution="gemini-2.5-flash",
    )
    dumped = finding.model_dump()
    assert dumped["finding_id"] == "FIND-001"
    assert dumped["claim"] == "URS traceability incomplete for GXP-MFG-DEMO-01"
    assert dumped["confidence_score"] == "HIGH"
    assert dumped["alcoa_score"]["attributable"] is False

    # Round-trip: constructing again from the dumped dict must succeed and
    # equal the original.
    rebuilt = AgentFinding(**dumped)
    assert rebuilt == finding


def test_agent_finding_missing_claim_raises_validation_error():
    with pytest.raises(ValidationError):
        AgentFinding(
            finding_id="FIND-002",
            # claim intentionally omitted
            regulatory_citations=["ANNEX11-S4-DOC-001"],
            confidence_score="LOW",
            evidence_ids=[],
            alcoa_score=ALCOAScore(),
            model_attribution="gemini-2.5-flash",
        )


def test_opa_violation_from_exact_rego_output_shape():
    # data.sentinel.gxp.violation emits exactly these five keys.
    rego_output = {
        "rule_id": "ANNEX11-S4-DOC-001",
        "severity": "high",
        "system_id": "GXP-MFG-DEMO-01",
        "record_id": "DOC-2026-OM-99",
        "description": "O&M document in DRAFT status",
    }
    violation = OPAViolation(**rego_output)
    assert violation.rule_id == "ANNEX11-S4-DOC-001"
    assert violation.severity == "high"
    assert violation.system_id == "GXP-MFG-DEMO-01"
    assert violation.record_id == "DOC-2026-OM-99"
    assert violation.description == "O&M document in DRAFT status"


def test_alcoa_score_defaults_field_by_field():
    s = ALCOAScore()
    # Defaults are not uniform — assert per field so a failure names the
    # exact field that drifted rather than diffing an opaque dict.
    assert s.attributable is False
    assert s.contemporaneous is False
    assert s.original is False
    assert s.legible is True
    assert s.accurate is True
    assert s.complete is True
    assert s.consistent is True
    assert s.enduring is True
    assert s.available is True


def test_agent_message_timestamp_auto_populated_naive_no_warning():
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        message = AgentMessage(agent_id="A2", message="test message")
    assert message.timestamp is not None
    assert message.timestamp.tzinfo is None
