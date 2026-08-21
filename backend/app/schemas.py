"""
Application-layer Pydantic models for AegisX AI.

Ticket: SENT-1-05 | Requirement: ENV-04
Source: AegisX-AI-Project-Bible-v6.md Section 4.3 (lines 834-937) —
transcribed verbatim; the Bible is the source of truth (CLAUDE.md Rule 14).

These are the **application-layer** models, used for runtime validation at
the FastAPI request/response boundary (`fastapi.FastAPI` route handlers).
They are distinct from the **graph-state** `TypedDict` definitions that
plan 02-06 creates in `app/graph/state.py` (Bible Section 1.2). Both modules
define classes named `AgentFinding` and `ActionProposal` with the same
field names, and this is deliberate, not an inconsistency to be collapsed:

- LangGraph state (`app/graph/state.py`) uses `TypedDict` for zero
  per-step validation overhead inside the orchestration hot path.
- FastAPI routes (this module) use `pydantic.BaseModel` for runtime
  validation at the API edge, where untrusted/external data crosses a
  trust boundary and must be rejected if malformed.

Conversion between the two happens explicitly at the API boundary (e.g.
`AgentFinding(**typed_dict_instance)`); neither module imports the other.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    reference_type: str = Field(
        ..., description="Document, Test Record, Access Review, etc."
    )
    reference_id: str
    uri: Optional[str] = None


class ALCOAScore(BaseModel):
    # Defaults are intentionally not uniform — do not normalise. Per the
    # Bible: attributable, contemporaneous, and original default False;
    # the remaining six default True.
    attributable: bool = False
    legible: bool = True
    contemporaneous: bool = False
    original: bool = False
    accurate: bool = True
    complete: bool = True
    consistent: bool = True
    enduring: bool = True
    available: bool = True


class AgentFinding(BaseModel):
    finding_id: str
    claim: str
    regulatory_citations: List[str]
    # str, not an enum — documented value domain is HIGH / MEDIUM / LOW /
    # INSUFFICIENT_EVIDENCE. Keeping this a plain str preserves the exact
    # type Phase 3's C1 verifier emits against.
    confidence_score: str  # HIGH, MEDIUM, LOW, INSUFFICIENT_EVIDENCE
    evidence_ids: List[str]
    alcoa_score: ALCOAScore
    model_attribution: str


class ActionProposal(BaseModel):
    action_type: str
    target_system: str
    payload: Dict[str, Any]
    justification: str


class AgentMessage(BaseModel):
    agent_id: str
    message: str
    # Bible writes `Field(default_factory=datetime.utcnow)`. datetime.utcnow()
    # is deprecated as of Python 3.12+ and this machine runs 3.13.9, so it
    # would emit a DeprecationWarning on every construction. Substituted
    # with datetime.now(timezone.utc).replace(tzinfo=None), which produces
    # a byte-identical naive-UTC value with no warning. The result stays
    # naive deliberately: an aware datetime here would raise TypeError when
    # compared against the Bible's other naive datetime fields (e.g.
    # AuditEvent.timestamp_utc, CAPAProposal.due_date).
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )


class AuditEvent(BaseModel):
    event_id: str
    timestamp_utc: datetime
    session_id: str
    user_id: str
    user_role: str
    agent_id: str
    action_type: str
    target_system_id: str
    target_record_id: Optional[str]
    input_hash: str
    output_summary: str
    evidence_ids: List[str]
    opa_rule_ids: List[str]
    model_id: Optional[str]
    prompt_version: str
    approval_id: Optional[str]
    previous_event_hash: str
    event_hash: str


class OPAViolation(BaseModel):
    rule_id: str
    severity: str
    system_id: str
    record_id: str
    description: str


class ConfidenceAssessment(BaseModel):
    score: str
    justification: str


class CAPAProposal(BaseModel):
    root_cause: str
    corrective_action: str
    preventive_action: str
    effectiveness_check: str
    due_date: datetime
    owner: str


class AuditPackage(BaseModel):
    system_overview: Dict[str, Any]
    findings: List[AgentFinding]
    risk_summary: Dict[str, Any]
    audit_trail_valid: bool
    chain_of_custody: List[str]


class SystemReadinessScore(BaseModel):
    system_id: str
    score: int
    breakdown: Dict[str, int]


class AgentExecutionTrace(BaseModel):
    agent_id: str
    start_time: datetime
    end_time: datetime
    tools_called: List[str]
    output_produced: Any


# Phase 3 (D-01/D-07): Bible Section 2 agent input/output models for A0
# and A2, transcribed verbatim.
class OrchestratorInput(BaseModel):
    user_query: str
    system_id: str


class OrchestratorOutput(BaseModel):
    active_agents: List[str]
    intent_category: str


class ComplianceInput(BaseModel):
    system_id: str
