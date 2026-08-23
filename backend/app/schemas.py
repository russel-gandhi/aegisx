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


# Phase 4 (GRAPH-01/GRAPH-03): evidence graph read/rebuild response models
# (04-01-PLAN.md <interface_contract>). Mirror `app.graph.evidence_graph`'s
# in-memory nx.DiGraph node/edge attribute shape at the API boundary.
class GraphNode(BaseModel):
    node_id: str
    node_type: str
    entity_id: str
    properties: Dict[str, Any]


class GraphEdge(BaseModel):
    source_id: str
    target_id: str
    relation_type: str


class EvidenceGraphResponse(BaseModel):
    system_id: str
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class EvidenceGraphRebuildResponse(BaseModel):
    system_id: str
    node_count: int
    edge_count: int


# Phase 4 (GRAPH-02, plan 04-04): Blast Radius response model. One field
# per Bible Section 14.3 Graph Question, transcribed from
# `evidence_graph.blast_radius()`'s return dict verbatim -- this model adds
# `system_id` (the route's own path parameter) on top. Field-to-question
# mapping:
#   direct_dependencies        -- Q1 directly affected entities
#   indirect_dependencies      -- Q2 indirectly affected entities
#   affected_requirements      -- Q3 affected requirements
#   affected_tests             -- Q4 affected tests
#   affected_risks             -- Q5 affected risks
#   affected_changes           -- Q6 affected changes
#   affected_controls          -- Q7 affected controls
#   affected_systems           -- GRAPH-02's own "affected systems" wording
#   potential_gxp_impact       -- Q8 potential GxP impact
#   highest_impact_downstream  -- Q9 highest-impact downstream dependency
class BlastRadiusResponse(BaseModel):
    system_id: str
    source_node_id: str
    direct_dependencies: List[str]
    indirect_dependencies: List[str]
    affected_requirements: List[str]
    affected_tests: List[str]
    affected_risks: List[str]
    affected_changes: List[str]
    affected_controls: List[str]
    affected_systems: List[str]
    potential_gxp_impact: str
    highest_impact_downstream: Optional[str] = None


# Phase 4 (EVID-03, D-04): Assurance Card response models
# (04-03-PLAN.md <interface_contract>, Bible Section 11.2). The card is
# assembled from already-computed Phase 3 output -- A2's `build_finding`
# and C1's `verify_finding` -- and this module adds no verification of
# its own; every field below is read, never derived.
class DeterministicCheck(BaseModel):
    check_name: str
    passed: bool
    db_record_found: bool
    opa_corroborated: bool
    opa_rule_ids: List[str]


class AssuranceCard(BaseModel):
    finding_id: str
    claim: str
    evidence_ids: List[str]
    regulatory_citations: List[str]
    deterministic_check: DeterministicCheck
    confidence: str
    alcoa_score: Dict[str, bool]
    model_attribution: str


class AssuranceCardsResponse(BaseModel):
    system_id: str
    cards: List[AssuranceCard]


# Phase 5 (REM-01..REM-04, SAFE-01, D-01..D-04): action-proposal /
# approval-workflow response models (05-01-PLAN.md <artifacts>). Every
# field here is read from an already-computed `action_proposals` row or
# from `c3_gateway.route_action`'s derived category -- never authored by a
# model at response-assembly time (`routes/actions.py`'s own module
# docstring makes this the same guarantee `AssuranceCard` already gives).
class ActionProposalRecord(BaseModel):
    id: str
    action_type: str
    category: str
    target_system: str
    payload: Dict[str, Any]
    status: str
    justification: Optional[str] = None
    finding_id: Optional[str] = None
    model_id: Optional[str] = None
    created_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    execution_result: Optional[str] = None


class ActionProposalsResponse(BaseModel):
    proposals: List[ActionProposalRecord]


class GenerateCapaResponse(BaseModel):
    finding_id: str
    confidence: str
    proposal: Optional[ActionProposalRecord] = None
    reason: Optional[str] = None
