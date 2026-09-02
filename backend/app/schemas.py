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
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator


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


# Phase 6 (06-01, D-04): Copilot non-hero-query request/response models.
# This route's `supported` is always `False` in v1 -- see
# `routes/copilot_query.py`'s own module docstring for why. `reason` is
# `detect_injection()`'s own return value, verbatim, never re-worded here.
class CopilotQueryRequest(BaseModel):
    query: str


class CopilotQueryResponse(BaseModel):
    supported: bool
    blocked: bool
    reason: Optional[str] = None


# Phase 5 (AUDIT-02, AUDIT-03): audit-chain HTTP response models
# (05-03-PLAN.md <artifacts>). Both models are read straight from
# `audit_trail.verify_chain`/`demonstrate_tamper`'s own return dict --
# `routes/audit.py` computes nothing of its own, matching this module's
# existing "no field authored at response-assembly time" guarantee.
class ChainVerificationResponse(BaseModel):
    status: str
    events_checked: Optional[int] = None
    broken_at_index: Optional[int] = None
    event_id: Optional[str] = None


class TamperDemoResponse(BaseModel):
    status: str
    event_id: str
    rows_modified: int
    events_checked: Optional[int] = None
    broken_at_index: Optional[int] = None


# Phase 6 (06-02, D-07 mini-cards #5/#6): access/supplier overdue-signals
# response model. Mirrors `minimal_specialists._check_a6`'s query shape
# (overdue `access_reviews`) plus a new overdue `suppliers` query -- see
# `routes/system_signals.py`'s own module docstring. Every field here is a
# plain count/name read straight off Postgres; no model is consulted.
class SystemSignalsResponse(BaseModel):
    system_id: str
    overdue_access_reviews: int
    overdue_suppliers: int
    overdue_supplier_names: List[str]


# Supplier Intelligence (Bible Section 11.5) full registry -- distinct from
# SystemSignalsResponse above, which is only the Command Centre's
# overdue-count aggregate. `latest_assessment_result`/`latest_assessment_date`
# are `None` when a supplier has no `supplier_assessments` row at all (an
# honest gap, not a guessed "N/A" string).
class SupplierRecord(BaseModel):
    supplier_id: str
    name: str
    status: Optional[str]
    reassessment_due_date_ns: Optional[int]
    is_overdue: bool
    latest_assessment_result: Optional[str]
    latest_assessment_date_ns: Optional[int]


class SuppliersResponse(BaseModel):
    system_id: str
    suppliers: List[SupplierRecord]


# Trust Centre (Bible Section 11.8): active LLM provider cascade and OPA
# policy bundle, exposed read-only and system-agnostic (both are process-wide
# configuration, not per-system state). Never includes an API key or any
# `api_key_env` value -- only the provider/model/task-routing shape itself,
# which is exactly what Bible Section 11.8 calls "current LLM provider
# configurations" (a transparency artifact, not a secret).
class LLMProviderInfo(BaseModel):
    provider_key: str
    provider: str
    model: str
    use_for: List[str]
    requires_api_key: bool


class TrustCentreResponse(BaseModel):
    llm_cascade: List[LLMProviderInfo]
    embedding_provider: LLMProviderInfo
    opa_policy_files: List[str]
    opa_policy_count: int


# Phase 06.1 (06.1-01, RAG-01/RAG-02/RAG-05/RAG-06/RAG-07, D-05): hybrid
# retrieval / real Copilot response contracts. Frozen in this plan so no
# later plan in this phase has to guess a field name -- plans 06.1-02/03
# populate the ranking fields (dense_score/bm25_score/reranker_score) and
# compute NavigationTarget; this plan only shapes the models.
#
# `RetrievalEvidenceItem` is a deliberate NEW sibling type, not an addition
# to `AgentFinding` above -- `AgentFinding` is consumed by C1,
# `routes/findings.py`, and five existing test modules (06.1-RESEARCH.md
# Anti-Pattern), and this module's own docstring already documents the
# "two type representations, converted explicitly at the API boundary"
# convention this class follows.
class RetrievalEvidenceItem(BaseModel):
    """Bible Section 15.7 names this field set. `retrieval_method` is one
    of `"semantic"`, `"keyword"`, `"hybrid"`, `"parent_context"`, `"graph"`.
    `evidence_type` is one of `"document"`, `"graph_relationship"`.
    """

    evidence_id: str
    document_id: str
    chunk_id: str
    document_title: str
    section: Optional[str] = None
    page: Optional[int] = None
    content: str
    retrieval_method: str
    dense_score: Optional[float] = None
    bm25_score: Optional[float] = None
    reranker_score: Optional[float] = None
    parent_section: Optional[str] = None
    graph_path: List[str] = []
    regulatory_citations: List[str] = []
    evidence_type: str
    why_selected: str


class InvestigationStage(BaseModel):
    """The six ordered stage ids and their exact UI labels
    (06.1-UI-SPEC.md Interaction Notes table): `understanding`/
    "Understanding question", `searching`/"Searching knowledge",
    `combining`/"Combining semantic and keyword evidence",
    `reranking`/"Reranking candidates", `evaluating`/"Evaluating evidence",
    `preparing`/"Preparing assessment". `status` is one of `"complete"`,
    `"skipped"`.
    """

    stage_id: str
    label: str
    status: str
    detail: Optional[str] = None


# D-13: the closed set of destinations Copilot-driven navigation may
# target. Declared beside `NavigationTarget` so both the route (plan
# 06.1-02) and every test import this constant rather than restating the
# strings.
NAVIGATION_KINDS: Tuple[str, ...] = ("document", "graph_node")


class NavigationTarget(BaseModel):
    """D-13: (1) `kind` is restricted to `NAVIGATION_KINDS`; (2) this model
    deliberately carries NO `url`, `href`, `path`, or `link` field -- the
    destination address is assembled in the browser from a fixed
    client-side route map keyed by `kind`, so neither this server nor an
    uploaded document's text can ever supply a navigable string (the
    open-redirect class of bug is removed structurally, not by
    validation); (3) it is computed by deterministic Python over the
    already-retrieved evidence list, never by a model, per D-08's
    boundary; (4) `reason` is a Python-composed sentence naming why the
    target was unambiguous, for display and for audit.
    """

    kind: str
    target_id: str
    label: str
    system_id: str
    reason: str

    @field_validator("kind")
    @classmethod
    def _kind_must_be_known(cls, value: str) -> str:
        if value not in NAVIGATION_KINDS:
            raise ValueError(f"kind must be one of {NAVIGATION_KINDS}, got {value!r}")
        return value


class CopilotInvestigateRequest(BaseModel):
    query: str
    system_id: Optional[str] = None


class CopilotInvestigateResponse(BaseModel):
    """`evidence_support` is one of `"HIGH"`, `"MODERATE"`, `"LIMITED"`,
    `"INSUFFICIENT_EVIDENCE"` -- computed server-side from the top
    surviving retrieval score, so the Evidence View stays pure
    presentation and never grades evidence in the browser. This band
    describes *retrieval support*, not C1's compliance confidence; the two
    are separate and this response carries both (`evidence_support` here,
    `findings[].confidence_score` for C1's own verdict).
    """

    answer: str
    insufficient_evidence: bool
    blocked: bool
    blocked_reason: Optional[str] = None
    evidence: List[RetrievalEvidenceItem] = []
    stages: List[InvestigationStage] = []
    findings: List[AgentFinding] = []
    verification_results: Dict[str, Any] = {}
    evidence_support: str
    model_attribution: str
    # None is the normal case (D-13: absent whenever the citations are
    # ambiguous or empty). Its presence is what licenses the client's
    # auto-navigation -- computed in plan 06.1-02, consumed in plan
    # 06.1-08.
    navigation_target: Optional[NavigationTarget] = None


class DocumentUploadResponse(BaseModel):
    document_id: str
    system_id: str
    title: str
    doc_type: str
    chunk_count: int
    indexed_vector_count: int
    status: str
    failed_stage: Optional[str] = None
    # True when this upload's content hash already matched an existing
    # document for this system_id -- the response describes that existing
    # document, and no parse/embed/index work ran for this request
    # (SYSTEM-DESIGN-DIAGNOSIS.md #6: upload idempotency).
    duplicate: bool = False
    # True when C2's deterministic injection detector (zero-LLM, same
    # regex+entropy check the copilot query path uses) flagged at least
    # one parsed chunk's text. A quarantined document is never embedded or
    # indexed into Qdrant -- its content never becomes retrievable
    # knowledge -- and a real audit_events row is written for it (Bible
    # Section 11.7, Assurance Lab).
    quarantined: bool = False
    quarantine_reason: Optional[str] = None


class DocumentSummary(BaseModel):
    document_id: str
    title: str
    doc_type: str
    version: Optional[str] = None
    system_id: str
    created_date: Optional[str] = None
    chunk_count: int
    ingestion_status: str
    failed_stage: Optional[str] = None


class DocumentListResponse(BaseModel):
    system_id: Optional[str]
    documents: List[DocumentSummary]
    # Pagination (SYSTEM-DESIGN-DIAGNOSIS.md #5). Defaulted so existing
    # callers/tests constructing this model positionally/without these
    # fields keep working.
    total_count: int = 0
    limit: int = 50
    offset: int = 0
