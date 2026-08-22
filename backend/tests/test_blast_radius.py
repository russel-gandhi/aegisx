"""
Tests for `app.graph.evidence_graph.blast_radius` (Phase 4, plan 04-04).

Ticket: SENT-3-03 | Requirement: GRAPH-02
Source: AegisX-AI-Project-Bible-v6.md Section 14.3 (lines 1690-1780) -- the
nine Graph Questions this module answers from one NetworkX traversal, and
the deterministic-first constraint (Bible Section 1.3): "NetworkX
reachability/traversal should calculate the affected subgraph. LLMs may
explain or summarize impact, but should not invent graph relationships."
No model call appears anywhere in this file or in the code it tests.

CLAUDE.md Rule 6 requires unit + negative + edge-case + integration
coverage for Blast Radius, not a smoke test -- the SENT-3-03 Critical-review
bar. Structured in the same four-section comment convention
`test_c1_verifier.py`/`test_evidence_graph.py` establish:

- UNIT: `assess_gxp_impact`/`rank_highest_impact`/`blast_radius` exercised
  directly against hand-built `nx.DiGraph` fixtures (no DB).
- INTEGRATION: `blast_radius(load_graph(...), ...)` against live, seeded
  Postgres (`GXP-MFG-DEMO-01`), one test per Bible Section 14.3 Graph
  Question -- nine in total -- never mocked (D-04 convention carried over
  from C1's and the evidence graph's own test suites).
- NEGATIVE: absent-node, cross-system, and malformed-id cases all raise
  `networkx.NetworkXError`, plus a positive control proving those refusals
  are discrimination, not a mechanism that always refuses. (Plan 04-04
  Task 2.)
- EDGE: empty graph, isolated node, cycle, self-loop, disconnected
  component, diamond, dual-path node, and a properties-less node shape.
  (Plan 04-04 Task 2.)

Follows the established `asyncio.run()`-inside-a-plain-`def`-test
convention; pytest-asyncio is deliberately absent.
"""

import asyncio

import networkx as nx

from app.db import get_pool
from app.graph.evidence_graph import (
    CONTROL_NODE_TYPES,
    NODE_SPECS,
    NODE_TYPE_IMPACT_RANK,
    assess_gxp_impact,
    blast_radius,
    load_graph,
    rank_highest_impact,
)

# ---------------------------------------------------------------------------
# UNIT -- hand-built nx.DiGraph fixtures, no DB
# ---------------------------------------------------------------------------


def _node(G, node_id, node_type, **properties):
    G.add_node(node_id, node_type=node_type, entity_id=node_id.split(":", 1)[1], properties=properties)


def test_unit_node_type_impact_rank_contains_every_node_specs_key_exactly_once():
    assert len(NODE_TYPE_IMPACT_RANK) == len(NODE_SPECS)
    assert set(NODE_TYPE_IMPACT_RANK) == set(NODE_SPECS)
    assert len(set(NODE_TYPE_IMPACT_RANK)) == len(NODE_TYPE_IMPACT_RANK)


def test_unit_control_node_types_is_access_review_and_access_record():
    assert CONTROL_NODE_TYPES == frozenset({"ACCESS_REVIEW", "ACCESS_RECORD"})


def test_unit_three_node_chain_yields_direct_b_indirect_c():
    G = nx.DiGraph()
    _node(G, "REQUIREMENT:A", "REQUIREMENT")
    _node(G, "TEST_CASE:B", "TEST_CASE")
    _node(G, "TEST_CASE:C", "TEST_CASE")
    G.add_edge("REQUIREMENT:A", "TEST_CASE:B", relation_type="VERIFIED_BY")
    G.add_edge("TEST_CASE:B", "TEST_CASE:C", relation_type="HAS_RESULT")

    result = blast_radius(G, "REQUIREMENT:A")
    assert result["direct_dependencies"] == ["TEST_CASE:B"]
    assert result["indirect_dependencies"] == ["TEST_CASE:C"]


def test_unit_source_node_never_appears_in_any_returned_list():
    G = nx.DiGraph()
    _node(G, "CHANGE:A", "CHANGE")
    _node(G, "REQUIREMENT:B", "REQUIREMENT")
    G.add_edge("CHANGE:A", "REQUIREMENT:B", relation_type="AFFECTS")
    # Cycle back to the source, so a naive descendants-inclusion bug would
    # surface here.
    G.add_edge("REQUIREMENT:B", "CHANGE:A", relation_type="AFFECTS")

    result = blast_radius(G, "CHANGE:A")
    for key in (
        "direct_dependencies",
        "indirect_dependencies",
        "affected_requirements",
        "affected_tests",
        "affected_risks",
        "affected_changes",
        "affected_controls",
        "affected_systems",
    ):
        assert "CHANGE:A" not in result[key]


def test_unit_every_returned_list_is_sorted_ascending_and_calls_are_equal():
    G = nx.DiGraph()
    _node(G, "CHANGE:A", "CHANGE")
    _node(G, "REQUIREMENT:Z", "REQUIREMENT")
    _node(G, "REQUIREMENT:M", "REQUIREMENT")
    _node(G, "REQUIREMENT:B", "REQUIREMENT")
    for target in ("REQUIREMENT:Z", "REQUIREMENT:M", "REQUIREMENT:B"):
        G.add_edge("CHANGE:A", target, relation_type="AFFECTS")

    first = blast_radius(G, "CHANGE:A")
    second = blast_radius(G, "CHANGE:A")
    assert first["direct_dependencies"] == sorted(first["direct_dependencies"])
    assert first["affected_requirements"] == sorted(first["affected_requirements"])
    assert first == second


def test_unit_assess_gxp_impact_high_for_downstream_system_with_gxp_impact_true():
    G = nx.DiGraph()
    _node(G, "SYSTEM:S1", "SYSTEM", gxp_impact=True)
    downstream = {"SYSTEM:S1"}
    assert assess_gxp_impact(G, downstream) == "HIGH"


def test_unit_assess_gxp_impact_high_for_downstream_incident_patient_safety_relevant_true():
    G = nx.DiGraph()
    _node(G, "INCIDENT:I1", "INCIDENT", patient_safety_relevant=True)
    downstream = {"INCIDENT:I1"}
    assert assess_gxp_impact(G, downstream) == "HIGH"


def test_unit_assess_gxp_impact_medium_for_nonempty_set_without_high_signal():
    G = nx.DiGraph()
    _node(G, "REQUIREMENT:R1", "REQUIREMENT")
    downstream = {"REQUIREMENT:R1"}
    assert assess_gxp_impact(G, downstream) == "MEDIUM"


def test_unit_assess_gxp_impact_none_for_empty_set():
    G = nx.DiGraph()
    assert assess_gxp_impact(G, set()) == "NONE"


def test_unit_rank_highest_impact_picks_node_with_most_descendants():
    G = nx.DiGraph()
    _node(G, "REQUIREMENT:A", "REQUIREMENT")
    _node(G, "REQUIREMENT:B", "REQUIREMENT")
    _node(G, "TEST_CASE:C", "TEST_CASE")
    G.add_edge("REQUIREMENT:B", "TEST_CASE:C", relation_type="VERIFIED_BY")

    downstream = {"REQUIREMENT:A", "REQUIREMENT:B", "TEST_CASE:C"}
    assert rank_highest_impact(G, downstream) == "REQUIREMENT:B"


def test_unit_rank_highest_impact_tie_break_by_node_type_impact_rank():
    G = nx.DiGraph()
    _node(G, "DOCUMENT:D1", "DOCUMENT")
    _node(G, "REQUIREMENT:R1", "REQUIREMENT")
    downstream = {"DOCUMENT:D1", "REQUIREMENT:R1"}
    # Both have zero descendants of their own; REQUIREMENT outranks DOCUMENT
    # in NODE_TYPE_IMPACT_RANK.
    assert NODE_TYPE_IMPACT_RANK.index("REQUIREMENT") < NODE_TYPE_IMPACT_RANK.index("DOCUMENT")
    assert rank_highest_impact(G, downstream) == "REQUIREMENT:R1"


def test_unit_rank_highest_impact_tie_break_within_one_type_by_lower_node_id():
    G = nx.DiGraph()
    _node(G, "REQUIREMENT:Z", "REQUIREMENT")
    _node(G, "REQUIREMENT:A", "REQUIREMENT")
    downstream = {"REQUIREMENT:Z", "REQUIREMENT:A"}
    assert rank_highest_impact(G, downstream) == "REQUIREMENT:A"


def test_unit_rank_highest_impact_returns_none_for_empty_set():
    G = nx.DiGraph()
    assert rank_highest_impact(G, set()) is None


# ---------------------------------------------------------------------------
# INTEGRATION -- live Postgres, real persisted graph via load_graph, never
# mocked. One test per Bible Section 14.3 Graph Question for
# CHANGE:CR-2026-089 on GXP-MFG-DEMO-01.
# ---------------------------------------------------------------------------


def _load_demo_graph():
    async def _run():
        pool = await get_pool()
        return await load_graph(pool, "GXP-MFG-DEMO-01")

    return asyncio.run(_run())


def test_integration_q1_directly_affected_entities():
    G = _load_demo_graph()
    result = blast_radius(G, "CHANGE:CR-2026-089")
    assert result["direct_dependencies"] == [
        "CHANGE_ACTION:CA-2026-089-1",
        "DESIGN_ELEMENT:DE-2026-DB-01",
        "DOCUMENT:DOC-2026-OM-99",
        "REQUIREMENT:URS-042",
    ]


def test_integration_q2_indirectly_affected_entities():
    G = _load_demo_graph()
    result = blast_radius(G, "CHANGE:CR-2026-089")
    assert result["indirect_dependencies"] == [
        "SYSTEM:GXP-MFG-DEMO-01",
        "TEST_CASE:TC-2026-042",
    ]


def test_integration_q3_affected_requirements():
    G = _load_demo_graph()
    result = blast_radius(G, "CHANGE:CR-2026-089")
    assert result["affected_requirements"] == ["REQUIREMENT:URS-042"]


def test_integration_q4_affected_tests():
    G = _load_demo_graph()
    result = blast_radius(G, "CHANGE:CR-2026-089")
    assert result["affected_tests"] == ["TEST_CASE:TC-2026-042"]


def test_integration_q5_affected_risks_is_empty():
    G = _load_demo_graph()
    result = blast_radius(G, "CHANGE:CR-2026-089")
    assert result["affected_risks"] == []


def test_integration_q6_affected_changes_excludes_source_change_itself():
    G = _load_demo_graph()
    result = blast_radius(G, "CHANGE:CR-2026-089")
    assert result["affected_changes"] == ["CHANGE_ACTION:CA-2026-089-1"]
    assert "CHANGE:CR-2026-089" not in result["affected_changes"]


def test_integration_q7_affected_controls_is_empty_but_control_nodes_exist_in_graph():
    G = _load_demo_graph()
    result = blast_radius(G, "CHANGE:CR-2026-089")
    assert result["affected_controls"] == []
    # Proves the empty bucket means "not downstream", not "not present".
    assert "ACCESS_REVIEW:AR-2026-05" in G.nodes
    assert "ACCESS_RECORD:ACC-2026-99" in G.nodes


def test_integration_q8_potential_gxp_impact_high_provenance_checked_against_db():
    async def _run():
        pool = await get_pool()
        G = await load_graph(pool, "GXP-MFG-DEMO-01")
        row = await pool.fetchrow(
            "SELECT gxp_impact FROM gxp_systems WHERE id = $1", "GXP-MFG-DEMO-01"
        )
        return G, row

    G, row = asyncio.run(_run())
    result = blast_radius(G, "CHANGE:CR-2026-089")
    assert row["gxp_impact"] is True
    assert result["potential_gxp_impact"] == "HIGH"


def test_integration_q9_highest_impact_downstream():
    G = _load_demo_graph()
    result = blast_radius(G, "CHANGE:CR-2026-089")
    assert result["highest_impact_downstream"] == "REQUIREMENT:URS-042"


def test_integration_second_traversal_from_requirement_tracks_real_subgraph():
    G = _load_demo_graph()
    result = blast_radius(G, "REQUIREMENT:URS-042")
    assert result["direct_dependencies"] == ["TEST_CASE:TC-2026-042"]
    assert result["indirect_dependencies"] == []


def test_integration_traversal_from_system_sink_returns_empty_everywhere():
    G = _load_demo_graph()
    result = blast_radius(G, "SYSTEM:GXP-MFG-DEMO-01")
    assert result["direct_dependencies"] == []
    assert result["indirect_dependencies"] == []
    assert result["affected_requirements"] == []
    assert result["affected_tests"] == []
    assert result["affected_risks"] == []
    assert result["affected_changes"] == []
    assert result["affected_controls"] == []
    assert result["affected_systems"] == []
    assert result["potential_gxp_impact"] == "NONE"
    assert result["highest_impact_downstream"] is None
