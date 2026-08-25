"""
Structural topology tests for the LangGraph orchestration skeleton.

Ticket: SENT-1-06 | Requirement: ORC-01

These tests assert against the graph builder's own node/edge/branch
collections with whole-collection equality (`==` against a literal
expected set), not by inspecting a rendered diagram or doing membership
checks. A membership check would pass for a graph carrying an extra,
unintended edge or destination; that is exactly the kind of silent
topology drift this suite exists to catch (see 02-06-PLAN.md threat
T-02-25: an A-node quietly disconnected from C1 would make C1 fan in on
incomplete evidence and still return a confident verdict).

No infrastructure dependency: every assertion here runs against the
in-process `StateGraph` builder and the pure `route_specialists` function,
with no database, OPA, or network call — this suite passes with the whole
Compose stack stopped.
"""

import asyncio
import operator
import typing

import pytest
from langgraph.graph import END, START
from langgraph.types import Send

from app.graph.state import (
    AgentState,
    compiled_graph,
    graph,
    route_specialists,
)

EXPECTED_NODES = {"C2", "A0", "A1", "A2", "A3", "A4", "A5", "A6", "C1", "A7", "C3"}

EXPECTED_EDGES = {
    (START, "C2"),
    ("C2", "A0"),
    ("A1", "C1"),
    ("A2", "C1"),
    ("A3", "C1"),
    ("A4", "C1"),
    ("A5", "C1"),
    ("A6", "C1"),
    ("C1", "A7"),
    ("A7", "C3"),
    ("C3", END),
}

EXPECTED_SPECIALISTS = {"A1", "A2", "A3", "A4", "A5", "A6"}


def _initial_state(active_agents=None):
    return {
        "messages": [],
        "system_id": "GXP-MFG-DEMO-01",
        "user_intent": "",
        "active_agents": active_agents if active_agents is not None else [],
        "findings": [],
        "proposed_actions": [],
        "verification_results": {},
        "final_synthesis": "",
        # Phase 5 plan 05-06: C2 now fails closed on an absent role, so a
        # real graph invocation must carry identity.
        "user_id": "test-user",
        "user_role": "IT System Manager",
    }


# --- Node set ----------------------------------------------------------


def test_node_set_is_exactly_the_eleven_participants():
    assert set(graph.nodes.keys()) == EXPECTED_NODES


# --- Direct edge set -----------------------------------------------------


def test_direct_edge_set_matches_topology_exactly():
    assert graph.edges == EXPECTED_EDGES


def test_removing_a_specialist_to_c1_edge_fails_the_edge_assertion():
    """Proves the suite can fail before trusting it to guard the topology
    (plan Task 2 instruction: "prove the suite can fail before declaring
    it done"). Temporarily drops one A<n> -> C1 edge from a *copy* of the
    expected set, confirms the equality comparison fails, and names the
    missing pair — without mutating the real module-level `graph` object
    (which every other test in this file and the app relies on)."""
    mutated_edges = set(graph.edges)
    removed_edge = ("A3", "C1")
    mutated_edges.discard(removed_edge)

    assert mutated_edges != EXPECTED_EDGES
    missing = EXPECTED_EDGES - mutated_edges
    assert missing == {removed_edge}


# --- Conditional branch out of A0 ----------------------------------------


def test_a0_conditional_destinations_are_exactly_a1_through_a6():
    branch_specs = graph.branches["A0"]
    assert len(branch_specs) == 1
    (branch_spec,) = branch_specs.values()
    assert set(branch_spec.ends.keys()) == EXPECTED_SPECIALISTS
    assert set(branch_spec.ends.values()) == EXPECTED_SPECIALISTS


# --- route_specialists: full set, subset, empty ---------------------------


def test_route_specialists_all_six_active_returns_six_sends():
    state = _initial_state(active_agents=["A1", "A2", "A3", "A4", "A5", "A6"])
    sends = route_specialists(state)

    assert len(sends) == 6
    assert all(isinstance(s, Send) for s in sends)
    assert {s.node for s in sends} == EXPECTED_SPECIALISTS
    for s in sends:
        assert set(s.arg.keys()) >= {"messages", "system_id"}
        assert s.arg["system_id"] == "GXP-MFG-DEMO-01"


def test_route_specialists_two_agent_subset_returns_two_sends():
    state = _initial_state(active_agents=["A2", "A5"])
    sends = route_specialists(state)

    assert len(sends) == 2
    assert {s.node for s in sends} == {"A2", "A5"}


def test_route_specialists_empty_active_agents_returns_empty_list():
    state = _initial_state(active_agents=[])
    sends = route_specialists(state)

    assert sends == []


# --- End-to-end ainvoke ---------------------------------------------------


def test_ainvoke_completes_through_all_eleven_stub_nodes():
    """Phase 3 update (plan 03-02): A2 and C1 are no longer stubs — see
    tests/test_hero_tracer.py for the real end-to-end assertions on their
    behavior against live Postgres/OPA. This test's scope narrows to what
    it can still promise: the graph completes through all eleven nodes and
    C3's stub still ends the run. `verification_results` is asserted only
    to be the real dict shape C1 now emits, not a specific value — its
    exact contents depend on live infra state that this file's docstring
    does not require."""
    result = asyncio.run(compiled_graph.ainvoke(_initial_state()))

    assert result["final_synthesis"] == "Execution complete. Actions queued for approval."
    assert isinstance(result["verification_results"], dict)


# --- Reducer behaviour -----------------------------------------------------


def test_ainvoke_findings_field_is_a_list():
    result = asyncio.run(compiled_graph.ainvoke(_initial_state()))
    assert isinstance(result["findings"], list)


def test_agentstate_findings_reducer_is_operator_add():
    """The stub nodes all return empty lists, so an end-to-end invocation
    alone cannot distinguish an accumulating reducer from an overwriting
    one (five branches returning `[]` look identical to zero branches
    running under last-writer-wins). Read the reducer directly from the
    TypedDict's annotations instead — this is precisely the distinction
    that makes the six-way fan-in at C1 correct once real agents replace
    the stubs and start returning non-empty findings lists."""
    hints = typing.get_type_hints(AgentState, include_extras=True)

    findings_args = typing.get_args(hints["findings"])
    assert findings_args[1] is operator.add

    proposed_actions_args = typing.get_args(hints["proposed_actions"])
    assert proposed_actions_args[1] is operator.add


def test_reducer_accumulates_findings_from_multiple_branches_not_last_writer_wins():
    """Directly exercises the `operator.add` reducer's accumulation
    behaviour (independent of the graph, which only ever returns empty
    lists from its stub nodes): simulates LangGraph's channel-update
    mechanism by reducing two branches' partial updates the same way
    LangGraph would at the C1 fan-in, and asserts entries from both
    branches survive rather than the second overwriting the first."""
    branch_a_update = [{"finding_id": "f-a", "claim": "from A2"}]
    branch_b_update = [{"finding_id": "f-b", "claim": "from A5"}]

    accumulated = operator.add(branch_a_update, branch_b_update)

    assert accumulated == [
        {"finding_id": "f-a", "claim": "from A2"},
        {"finding_id": "f-b", "claim": "from A5"},
    ]
    # A naive last-writer-wins merge (what the state would look like
    # *without* the reducer) would leave only branch_b_update's entry.
    assert accumulated != branch_b_update
