"""
LangGraph orchestration skeleton for AegisX AI.

Ticket: SENT-1-06 | Requirement: ORC-01
Source: AegisX-AI-Project-Bible-v6.md Section 1.2 (lines 97-196) —
transcribed as the implementation, not reinterpreted; the Bible is the
source of truth (CLAUDE.md Rule 14).

This module defines the fixed request topology:

    C2 -> A0 -> [A1...A6 in parallel via Send] -> C1 -> A7 -> C3

Every one of the eleven nodes is intentionally a stub in this phase (Phase
2 / Foundation). Phase 3+ replaces each stub body with a real agent, real
evidence retrieval, and real OPA evaluation, without changing this
topology — every future agent is a node substitution inside this same
graph, not a redesign of it.

Graph-state types vs. application-layer types (Bible Section 1.2 vs.
Section 4.3; see also 02-RESEARCH.md Pitfall 6): the `TypedDict` classes
defined here (`AgentFinding`, `ActionProposal`, `AgentState`) are the
graph-state representation used inside the LangGraph orchestration hot
path, chosen for zero per-step validation overhead. `app.schemas` holds
the Pydantic `BaseModel` representation of the same concepts, used for
runtime validation at the FastAPI request/response boundary. These are
deliberately two different Python types with the same field names, not a
single type shared across tiers. Neither module imports the other;
conversion between them happens explicitly at the API boundary (e.g.
`schemas.AgentFinding(**typed_dict_instance)`).

Deterministic-first constraint (Bible Section 1.3, CLAUDE.md): C2 (Policy
& Safety Gateway), C1 (Evidence & Grounding Verifier), and C3 (Action
Gateway) are decision nodes that Bible Section 1.3 permanently forbids an
LLM from occupying — C2 makes the RBAC/injection-detection call, C1 makes
the evidence-verification call, and C3 makes the action-category routing
call, and all three must stay deterministic Python/Rego/graph-traversal
logic forever, not just at this stub stage. No node in this module may
ever contain an LLM client call, a database call, or an OPA call; those
belong in the real agent implementations that replace these stubs in
later phases, and even there they must route through the nodes this
constraint permits (Python, Rego, NetworkX) — never through a model
occupying C2, C1, or C3 directly.

Phase 3 update (plan 03-02): `compliance_a2` and `evidence_verifier_c1`
below now delegate to real implementations in `app.agents` —
`app.agents.a2_compliance.run_a2` and `app.agents.c1_verifier.run_c1`
respectively. This module itself still performs no LLM, database, or OPA
call of its own; those calls live entirely inside the delegate modules
under `app.agents`. C2, C1, and C3 remain permanently closed to model
occupancy — `app.agents.c1_verifier` is deterministic Python only, and
C2/C3 stay stubs until Phase 5.

Phase 3 update (plan 03-03): `orchestrator_a0` and the five remaining
specialist stub bodies (`system_knowledge_a1`, `risk_a3`, `change_a4`,
`incident_a5`, `access_a6`) now delegate to real implementations in
`app.agents.a0_orchestrator.run_a0` and `app.agents.minimal_specialists`
respectively. A0's narrowed-or-full `active_agents` list flows through the
unchanged `route_specialists` fan-out below exactly as a data change, per
this module's own long-standing docstring claim — `route_specialists` and
the graph-assembly block are byte-identical to Phase 2. `remediation_a7`,
`safety_gateway_c2`, and `action_gateway_c3` remain deliberately stubbed:
A7 lands in Phase 5 (SENT-4-05), and C2/C3 are Phase 5 deterministic
gateways (SENT-4-01/4-02/4-03).

Phase 5 update (plan 05-06): the last three stub bodies are replaced with
real delegates, in exactly the one-line style `compliance_a2` and
`evidence_verifier_c1` already established — `safety_gateway_c2` ->
`app.agents.c2_gateway.run_c2`, `remediation_a7` ->
`app.agents.a7_remediation.run_a7`, `action_gateway_c3` ->
`app.agents.c3_gateway.run_c3`. `route_specialists` gains one further
intersection against `state.get("permitted_agents")` — C2's RBAC verdict
— so RBAC reaches the fan-out as a data change through this same
unchanged conditional edge, exactly as A0's Phase 3 subset routing already
does. C2, C1, and C3 remain permanently closed to model occupancy (Bible
Section 1.3); A7 is the one node in this fixed topology ever permitted a
model call, and only over findings C1 has already verified.
"""

import operator
from typing import Annotated, Any, Dict, List, Optional, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import END, StateGraph

# `Send` moved from `langgraph.constants` to `langgraph.types` between the
# Bible's LangGraph 0.x-era sample and the pinned langgraph==1.2.11 here.
# `langgraph.types.Send` is the current (non-deprecated) location; the
# `langgraph.constants` import still works on 1.2.11 but emits
# `LangGraphDeprecatedSinceV10` and is slated for removal in V2.0. Resolved
# at import time rather than hard-coding one path, so this module keeps
# working across that migration without an edit.
try:
    from langgraph.types import Send
except ImportError:  # pragma: no cover - exercised only on older langgraph
    from langgraph.constants import Send  # Bible's original import path

# `add_messages` similarly may live at either `langgraph.graph.message`
# (the Bible's path, still current on 1.2.11) or the shorter
# `langgraph.graph` re-export. Both resolved successfully against the
# pinned version; `langgraph.graph.message` is used first since it is the
# more specific, version-stable path.
try:
    from langgraph.graph.message import add_messages
except ImportError:  # pragma: no cover - exercised only if the submodule moves
    from langgraph.graph import add_messages

# Phase 3 (plans 03-02, 03-03): every node body this module delegates to a
# real implementation. Imported at module top level per plan instruction.
# Phase 5 (plan 05-06) adds run_c2, run_a7, run_c3 to this same import
# block -- C2, A7, and C3 are the last three stub bodies this module ever
# had.
from app.agents.a0_orchestrator import run_a0
from app.agents.a2_compliance import run_a2
from app.agents.a7_remediation import run_a7
from app.agents.c1_verifier import run_c1
from app.agents.c2_gateway import run_c2
from app.agents.c3_gateway import run_c3
from app.agents.minimal_specialists import run_a1, run_a3, run_a4, run_a5, run_a6


class AgentFinding(TypedDict):
    """Graph-state finding shape. See module docstring: distinct from
    `app.schemas.AgentFinding` (a `pydantic.BaseModel`)."""

    finding_id: str
    claim: str
    regulatory_citations: List[str]
    confidence_score: str
    evidence_ids: List[str]
    alcoa_score: Dict[str, bool]
    model_attribution: str


class ActionProposal(TypedDict):
    """Graph-state action-proposal shape. See module docstring: distinct
    from `app.schemas.ActionProposal` (a `pydantic.BaseModel`)."""

    action_type: str
    target_system: str
    payload: Dict[str, Any]
    justification: str


class AgentState(TypedDict):
    """The state object threaded through every node in the graph.

    `findings` and `proposed_actions` are each annotated with the
    accumulating list-concatenation reducer from the stdlib `operator`
    module (see the field annotations below): six specialist branches
    (A1-A6) run concurrently and each returns `{"findings": [...]}`.
    Without that reducer, LangGraph's default last-writer-wins merge
    would silently discard five of six branches' findings at the C1
    fan-in — a failure that would present as C1 verifying a suspiciously
    small evidence set, not as an error. `messages` carries the
    `add_messages` reducer for the same reason, following LangGraph's
    standard message-accumulation convention.
    """

    messages: Annotated[Sequence[BaseMessage], add_messages]
    system_id: str
    user_intent: str
    active_agents: List[str]
    findings: Annotated[List[AgentFinding], operator.add]
    proposed_actions: Annotated[List[ActionProposal], operator.add]
    verification_results: Dict[str, Any]
    final_synthesis: str
    # Phase 06.1 (plan 06.1-02, RAG-05/RAG-06): A1's real retrieval output.
    # Both take the same accumulating reducer `findings` already carries,
    # for the same reason (A1 runs inside the concurrent A1-A6 `Send`
    # fan-out) -- last-writer-wins would silently discard whichever
    # sibling branch's write lost the race at the C1 fan-in.
    retrieval_evidence: Annotated[List[Dict[str, Any]], operator.add]
    retrieval_trace: Annotated[List[Dict[str, Any]], operator.add]
    # Phase 5 (plan 05-06): identity and RBAC/injection verdict fields.
    # None of these six takes a reducer — exactly one node writes each
    # (C2 writes user_role/permitted_agents/blocked/blocked_reason's
    # counterpart verdict; the caller supplies user_id/user_role/
    # remediation_requested as initial state), so last-writer-wins is
    # correct, the same reasoning the class docstring already gives for
    # every other unreduced field here.
    user_id: str
    user_role: str
    permitted_agents: List[str]
    blocked: bool
    blocked_reason: Optional[str]
    remediation_requested: bool


# --- Eleven node coroutines --------------------------------------------------
# As of Phase 5 plan 05-06, every one of the eleven nodes below delegates to
# a real implementation under app.agents — none remains a literal-returning
# stub. C2, C1, and C3 permanently perform no LLM call, no database call,
# and no OPA/network call of their own; A7 is the one node in this fixed
# topology ever permitted a model call (see module docstring).


async def safety_gateway_c2(state: AgentState) -> Dict[str, Any]:
    """C2 - Policy & Safety Gateway. Delegates to
    `app.agents.c2_gateway.run_c2` (Phase 5, plan 05-06, SAFE-01/02): real
    RBAC (fail-closed on an absent or unrecognised role) and deterministic
    regex + Shannon-entropy injection detection — zero LLM in the decision
    path, permanently (Bible Section 1.3). Publishes `permitted_agents`,
    which `route_specialists` below intersects against `active_agents`
    with no change to this module's topology. This module performs no
    RBAC or injection-detection logic of its own."""
    return await run_c2(state)


async def orchestrator_a0(state: AgentState) -> Dict[str, Any]:
    """A0 - Orchestrator/Supervisor. Delegates to
    `app.agents.a0_orchestrator.run_a0` (Phase 3, plan 03-03, ORC-02): one
    real intent-classification call through the LLM router, narrowing
    `active_agents` to the classified subset, with a hard 2000ms
    `asyncio.wait_for` timeout that falls back to the full six-agent set —
    a data change routed through the unchanged `route_specialists` fan-out
    below, not a topology change. This module performs no LLM call
    itself."""
    return await run_a0(state)


async def system_knowledge_a1(state: AgentState) -> Dict[str, Any]:
    """A1 - System Knowledge (Qdrant RAG). Delegates to
    `app.agents.minimal_specialists.run_a1` (Phase 3, plan 03-03; Phase
    06.1, plan 06.1-02): validates `system_id` exists in `gxp_systems` and
    returns the Bible's verbatim `ERR-A1` abstain finding when it does not
    (or when Postgres is unreachable), exactly as before. As of plan
    06.1-02, A1 now performs real hybrid retrieval against Qdrant + Postgres
    (`app.retrieval.hybrid_search.hybrid_retrieve`) rather than only the
    existence check — the retrieval output rides the sibling
    `retrieval_evidence`/`retrieval_trace` state keys, not `findings`."""
    return await run_a1(state)


async def compliance_a2(state: AgentState) -> Dict[str, Any]:
    """A2 - Compliance Agent. Delegates to `app.agents.a2_compliance.run_a2`
    (Phase 3, plan 03-02): one deterministic check
    (`verify_periodic_eval_current`) against real Postgres, narrated via
    the LLM router when it succeeds and a deterministic template when it
    degrades. This module performs no DB or LLM call itself."""
    return await run_a2(state)


async def risk_a3(state: AgentState) -> Dict[str, Any]:
    """A3 - Risk Agent. Delegates to
    `app.agents.minimal_specialists.run_a3` (Phase 3, plan 03-03):
    flags a risk assessment overdue its ICH Q9(R1) 12-month review cycle,
    downgrading from DeepSeek to `gemini_flash_thinking` on the router's
    own failure behavior before falling to a deterministic sentence."""
    return await run_a3(state)


async def change_a4(state: AgentState) -> Dict[str, Any]:
    """A4 - Change Agent. Delegates to
    `app.agents.minimal_specialists.run_a4` (Phase 3, plan 03-03): flags a
    CLOSED change record with an OPEN linked action from direct change
    record metadata only — graph traversal lands in Phase 4."""
    return await run_a4(state)


async def incident_a5(state: AgentState) -> Dict[str, Any]:
    """A5 - Incident Agent. Delegates to
    `app.agents.minimal_specialists.run_a5` (Phase 3, plan 03-03): flags a
    P1 incident open more than 7 days without a started RCA."""
    return await run_a5(state)


async def access_a6(state: AgentState) -> Dict[str, Any]:
    """A6 - Access Agent. Delegates to
    `app.agents.minimal_specialists.run_a6` (Phase 3, plan 03-03): flags
    an overdue access review and an orphaned privileged (departed-user)
    account, each independently verifiable by C1."""
    return await run_a6(state)


async def evidence_verifier_c1(state: AgentState) -> Dict[str, Any]:
    """C1 - Evidence & Grounding Verifier. Delegates to
    `app.agents.c1_verifier.run_c1` (Phase 3, plan 03-02, SENT-2-12): real,
    deterministic Python only, verifying every finding against a real
    Postgres record and a real OPA evaluation via `calculate_confidence()`.
    This is the product's deterministic-verification thesis node — never an
    LLM occupying this node, here or in its delegate."""
    return await run_c1(state)


async def remediation_a7(state: AgentState) -> Dict[str, Any]:
    """A7 - Remediation. Delegates to
    `app.agents.a7_remediation.run_a7` (Phase 5, plan 05-06, SENT-4-05,
    REM-01, D-03): synthesizes `ActionProposal`/CAPA narratives from
    already-verified (C1-graded HIGH/MEDIUM/LOW) findings only, and only
    when `state["remediation_requested"]` is explicitly true — never as a
    side effect of asking a question or of A0's ordinary fan-out. This is
    the one node in the fixed topology ever permitted a model call (Bible
    Section 1.3); this module itself performs no LLM call of its own."""
    return await run_a7(state)


async def action_gateway_c3(state: AgentState) -> Dict[str, Any]:
    """C3 - Action Gateway. Delegates to
    `app.agents.c3_gateway.run_c3` (Phase 5, plan 05-06, SENT-4-03,
    REM-02/03): deterministic five-category routing (READ / DRAFT /
    MOCK_WRITE_LOW_RISK / GXP_RELEVANT_WRITE / PROHIBITED) over
    `state["proposed_actions"]`, composing a server-trusted
    `final_synthesis` summary — never an LLM occupying this node, and this
    module performs no database write of its own (persistence is
    `persist_proposal`'s job, called from the HTTP route where an identity
    exists)."""
    return await run_c3(state)


def route_specialists(state: AgentState) -> List[Send]:
    """A0's fan-out: one `Send` per entry in `active_agents`.

    This is what makes ORC-02's Phase 3 subset routing (and its 2000ms
    timeout fallback to the full six-agent set) a data change against
    `active_agents` rather than a topology change here — narrowing or
    widening the list changes the fan-out with no edit to this function
    or to the graph edges below.

    Phase 5 update (plan 05-06, T-05-36): the `Send` set is further
    intersected against `state["permitted_agents"]` — the RBAC-permitted
    subset `app.agents.c2_gateway.run_c2` publishes — so an under-privileged
    role's query can only narrow the fan-out A0 selected, never widen it
    (e.g. an Auditor cannot reach A3–A6 even when A0's own classification
    names them). This is still a data change through the same unchanged
    conditional edge below, exactly as the paragraph above already claims
    for A0's own subset routing — this function's node list, the graph's
    edges, and the assembly block are untouched.

    `permitted_agents` defaults to `active_agents` itself (i.e. no
    restriction) when the key is entirely absent from `state` — this
    matters only for a direct unit-test call that bypasses C2 (this
    module's own `test_graph_topology.py` calls `route_specialists`
    standalone, with no C2 verdict in state at all). Every real
    `compiled_graph.ainvoke()` invocation runs C2 first, which always sets
    `permitted_agents` — to the RBAC-permitted set, or to `[]` on a
    blocked request — before `route_specialists` is ever reached, so this
    default never masks a real RBAC decision.
    """
    permitted = state.get("permitted_agents")
    if permitted is None:
        permitted = state["active_agents"]
    return [
        Send(agent_name, {"messages": state["messages"], "system_id": state["system_id"]})
        for agent_name in state["active_agents"]
        if agent_name in permitted
    ]


# --- Graph assembly (Bible Section 1.2 order, exact node ids) --------------

graph = StateGraph(AgentState)
graph.add_node("C2", safety_gateway_c2)
graph.add_node("A0", orchestrator_a0)
graph.add_node("A1", system_knowledge_a1)
graph.add_node("A2", compliance_a2)
graph.add_node("A3", risk_a3)
graph.add_node("A4", change_a4)
graph.add_node("A5", incident_a5)
graph.add_node("A6", access_a6)
graph.add_node("C1", evidence_verifier_c1)
graph.add_node("A7", remediation_a7)
graph.add_node("C3", action_gateway_c3)

graph.set_entry_point("C2")
graph.add_edge("C2", "A0")
graph.add_conditional_edges("A0", route_specialists, ["A1", "A2", "A3", "A4", "A5", "A6"])
for _agent in ["A1", "A2", "A3", "A4", "A5", "A6"]:
    graph.add_edge(_agent, "C1")
graph.add_edge("C1", "A7")
graph.add_edge("A7", "C3")
graph.add_edge("C3", END)

# `graph` (the uncompiled builder) is exported alongside `compiled_graph`
# deliberately: the topology tests assert against the builder's node and
# edge collections directly, which is a far more direct and
# version-stable assertion than parsing a rendered diagram.
compiled_graph = graph.compile()
