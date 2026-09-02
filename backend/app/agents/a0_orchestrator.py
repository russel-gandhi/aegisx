"""
A0 - Orchestrator / Supervisor (Phase 3, plan 03-03).

Ticket: SENT-2-01 | Requirement: ORC-02
Source: AegisX-AI-Project-Bible-v6.md Section 2's "A0" entry (Input/Output
schemas, Model Selection, Failure Behavior) and Section 6's "A0:
Orchestrator Routing Prompt" (transcribed verbatim below as
`A0_SYSTEM_PROMPT`).

A0 is a single classification call: build `OrchestratorInput`, ask the
router (task="orchestrator" -> `llm_router.PROVIDER_CONFIG["ollama_qwen"]`
as of the 2026-09-01 local-first migration, cascading to
`groq_gpt_oss`/`openrouter_fallback` on failure -- the Bible-literal
"Gemini 2.5 Flash, thinking ON" description this docstring carried until
2026-09-03 no longer describes any entry in `PROVIDER_CONFIG`, see that
module's own comments for why) for a strict JSON `OrchestratorOutput`, and
narrow `active_agents` to whatever subset it names. No deterministic
Postgres/OPA check backs this node (Bible
Section 2: "Deterministic Checks: N/A") - the routing decision itself
stays out of `route_specialists` (app.graph.state), which this module
never imports or modifies (03-03-PLAN.md <critical_findings>).

The Bible's hard requirement (ORC-02, D-02): a classification that has
not completed within 2000ms is abandoned - not merely raced against a
deadline while left running - and `active_agents` reverts to the full
`FULL_AGENT_SET`. `run_a0` enforces this with `asyncio.wait_for`, which
cancels the in-flight `classify_intent` coroutine on timeout; it never
uses a delay-based approximation or LangGraph's own per-node timeout
setting (03-RESEARCH.md "Alternatives Considered" explicitly rules the
latter out as a substitute for this specific, tested guarantee).

Every failure to classify - a timeout, a degraded router response, invalid
JSON, a schema-validation failure, an empty `active_agents` list, or an
agent id outside `FULL_AGENT_SET` - reaches the exact same full-set
fallback (T-03-12: an externally-produced classification can never widen
`active_agents` beyond the six ids this graph already owns). `run_a0`
itself never raises to its caller; a routing decision it cannot make is
not an error the graph should propagate.

Phase 5 update (plan 05-06): `run_a0` now short-circuits on
`state["blocked"]` (set by the real `app.agents.c2_gateway.run_c2`, which
now precedes this node in the compiled graph) before attempting any
classification, and `_extract_user_query` was renamed to the public
`extract_user_query` so C2 reads the user query through the same function
rather than a second copy.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List

from pydantic import ValidationError

from app.llm_router import call_llm
from app.schemas import OrchestratorInput, OrchestratorOutput

logger = logging.getLogger(__name__)

# Bible Section 2 "A0" Failure Behavior: "Defaults to
# [\"A1\", \"A2\", \"A3\", \"A4\", \"A5\", \"A6\"] (full diagnostic run)" -
# the literal six-id, Bible-ordered value every fallback path below
# returns. A fresh list copy is returned on every fallback (never this
# module-level list itself) so a downstream mutation of the returned value
# can never corrupt this constant for the next call.
FULL_AGENT_SET: List[str] = ["A1", "A2", "A3", "A4", "A5", "A6"]

# Bible Section 2 "A0" Failure Behavior: "...if the LLM times out after
# 2000ms" (ORC-02). Expressed in seconds, the unit `asyncio.wait_for`
# takes.
A0_TIMEOUT_SECONDS = 2.0

# AegisX-AI-Project-Bible-v6.md Section 6, "A0: Orchestrator Routing
# Prompt" - transcribed verbatim, including all six agent-capability lines
# and the required strict-JSON output example.
A0_SYSTEM_PROMPT = (
    "You are the A0 Orchestrator for AegisX AI, operating under EU GMP "
    "Annex 11 guidelines.\n\n"
    "Your task is to analyze the user query and output a JSON array of "
    "specialist agent IDs to activate.\n\n"
    "Agent capabilities:\n\n"
    '- "A1": Questions about system metadata, intended use, lifecycle '
    "state, SOP/O&M documentation.\n"
    '- "A2": Checks URS, test execution completeness, periodic '
    "evaluation.\n"
    '- "A3": Evaluates business continuity, patient safety risks, and '
    "supplier status.\n"
    '- "A4": Assesses change records and release impact.\n'
    '- "A5": Detects incidents, problem tickets, and anomalies.\n'
    '- "A6": Evaluates user access, orphaned accounts, SoD violations.\n\n'
    "Output strictly valid JSON: "
    '{"active_agents": ["A1", "A2"], "intent_category": "audit_readiness"}'
)


def extract_user_query(state: Dict[str, Any]) -> str:
    """The most recent message's text content, or `""` when `messages` is
    empty. `state["messages"]` holds `BaseMessage` instances (see
    `app.graph.state.AgentState`); this module reads only `.content`.

    Public since Phase 5 plan 05-06 (renamed from `_extract_user_query`):
    `app.agents.c2_gateway.run_c2` imports this function so C2 and A0 read
    the user query through one function rather than two copies -- the same
    single-source-of-truth discipline this codebase already applies to
    `PERMISSION_MATRIX`/`ACTION_CATEGORIES`. No other module in the
    repository referenced the private name, so this was a straight
    rename."""
    messages = state.get("messages") or []
    if not messages:
        return ""
    return getattr(messages[-1], "content", "") or ""


async def classify_intent(user_query: str, system_id: str) -> OrchestratorOutput:
    """One real classification call through the router. Raises `ValueError`
    for every way a classification can fail to be usable: a degraded
    router response, non-JSON text, a schema-validation failure, an empty
    `active_agents` list, or an agent id outside `FULL_AGENT_SET`. All of
    these are failures to classify and `run_a0` maps every one of them to
    the same full-set fallback (T-03-12).
    """
    orchestrator_input = OrchestratorInput(user_query=user_query, system_id=system_id)
    response = await call_llm(
        task="orchestrator",
        prompt=orchestrator_input.model_dump_json(),
        system_instruction=A0_SYSTEM_PROMPT,
        json_output=True,
    )
    if response.degraded:
        raise ValueError(f"LLM router degraded: {response.failure_reason}")

    try:
        parsed = json.loads(response.text)
    except json.JSONDecodeError as e:
        raise ValueError(f"classification response was not valid JSON: {e}") from e

    try:
        result = OrchestratorOutput.model_validate(parsed)
    except ValidationError as e:
        raise ValueError(f"classification response failed schema validation: {e}") from e

    if not result.active_agents:
        raise ValueError("classification returned an empty active_agents list")

    invalid = [agent_id for agent_id in result.active_agents if agent_id not in FULL_AGENT_SET]
    if invalid:
        raise ValueError(f"classification named unknown agent ids: {invalid}")

    return result


async def run_a0(state: Dict[str, Any]) -> Dict[str, Any]:
    """A0 node body: classify under a hard 2000ms budget, or fall back to
    the full agent set.

    Uses `asyncio.wait_for` - a real awaited async timeout that cancels
    the in-flight `classify_intent` coroutine when the budget expires,
    never a delay-based approximation and never LangGraph's own per-node
    timeout setting (both ruled out by 03-CONTEXT.md and
    03-RESEARCH.md's "Alternatives Considered"). Catches `asyncio.TimeoutError`
    alongside `ValueError` (every classification-failure mode
    `classify_intent` raises) so both land on the identical fallback.
    Never raises to its caller.

    Phase 5 plan 05-06 (T-05-35): the very first statement returns
    immediately when `state["blocked"]` is true (C2's RBAC/injection
    verdict), before any classification is attempted. A0 is the first
    node after C2 and the first place this graph would otherwise call a
    model, so returning here is what makes "blocked before it reaches an
    agent" literally true -- a blocked payload never reaches any provider,
    and `route_specialists`' own `permitted_agents` intersection (an empty
    set on a blocked request) independently guarantees no specialist Send
    fires either, even if this short-circuit were ever removed.
    """
    if state.get("blocked"):
        return {"active_agents": [], "user_intent": "blocked"}

    user_query = extract_user_query(state)
    system_id = state["system_id"]
    try:
        result = await asyncio.wait_for(
            classify_intent(user_query, system_id),
            timeout=A0_TIMEOUT_SECONDS,
        )
    except (asyncio.TimeoutError, ValueError) as e:
        logger.warning("A0 falling back to full agent set: %s", e)
        return {"active_agents": list(FULL_AGENT_SET), "user_intent": "unclassified_fallback"}

    return {"active_agents": result.active_agents, "user_intent": result.intent_category}
