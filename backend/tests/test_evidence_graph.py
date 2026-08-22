"""
Tests for `app.graph.evidence_graph` (Phase 4, plans 04-01/04-02).

Ticket: SENT-3-01 | Requirement: GRAPH-01
Source: AegisX-AI-Project-Bible-v6.md Section 10.1 (`build_evidence_graph` /
`find_downstream_impacts`) and Section 1.3's deterministic-first constraint.

CLAUDE.md Rule 6 requires unit + negative + edge-case + integration
coverage for the evidence graph, not a smoke test. Structured in the same
four-section comment convention `test_c1_verifier.py` establishes:

- UNIT: `make_node_id`/`split_node_id` round-tripping and the frozen
  NODE_SPECS/RELATION_TYPES/EDGE_SPECS/CHANGE_AFFECTS_ENTITY_TYPES
  allowlist shape guarantees (no DB).
- INTEGRATION: `build_graph`/`persist_graph`/`load_graph` against live,
  seeded Postgres (`GXP-MFG-DEMO-01`, 14 nodes / 9 edges after plan 04-02)
  and the empty-graph discrimination control (`BUS-IT-DEMO-02`) -- never
  mocked (D-04 convention carried over from C1's test suite).
- NEGATIVE: an out-of-allowlist change_affects.entity_type, a
  change_affects row naming a non-existent entity, and the D-03
  same-system_id-is-not-an-edge guarantee.
- EDGE: a single-node system, a system with no `changes` rows, and
  build-twice determinism.

Follows the established `asyncio.run()`-inside-a-plain-`def`-test
convention; pytest-asyncio is deliberately absent.
"""

import asyncio

import pytest

from app.db import get_pool
from app.graph.evidence_graph import (
    CHANGE_AFFECTS_ENTITY_TYPES,
    EDGE_SPECS,
    NODE_SPECS,
    RELATION_TYPES,
    _add_edge,
    build_graph,
    load_graph,
    make_node_id,
    persist_graph,
    split_node_id,
)

# ---------------------------------------------------------------------------
# UNIT -- id helpers and frozen allowlist shape (no DB)
# ---------------------------------------------------------------------------

# The full set of tables infra/postgres/initdb/001_schema.sql declares that
# NODE_SPECS is permitted to name, transcribed from that file directly (not
# derived from NODE_SPECS itself, so this test can actually catch a typo).
REAL_TABLES = {
    "gxp_systems",
    "documents",
    "document_chunks",
    "requirements",
    "risks",
    "design_elements",
    "test_cases",
    "test_results",
    "incidents",
    "access_reviews",
    "access_records",
    "suppliers",
    "supplier_assessments",
    "periodic_evaluations",
    "changes",
    "change_actions",
    "findings",
    "evidence_refs",
    "action_proposals",
    "audit_events",
    "agent_messages",
    "graph_nodes",
    "graph_edges",
    "candidate_memory",
    "trusted_memory",
    "users",
    "sessions",
}


def test_unit_make_node_id_joins_type_and_entity_with_single_colon():
    assert make_node_id("REQUIREMENT", "URS-042") == "REQUIREMENT:URS-042"


def test_unit_split_node_id_inverts_make_node_id():
    assert split_node_id("REQUIREMENT:URS-042") == ("REQUIREMENT", "URS-042")


def test_unit_split_node_id_round_trips_entity_id_containing_colon():
    entity_id = "SOME:WEIRD:ID"
    node_id = make_node_id("TEST_CASE", entity_id)
    assert split_node_id(node_id) == ("TEST_CASE", entity_id)


def test_unit_node_specs_tables_are_all_real_declared_tables():
    for node_type, spec in NODE_SPECS.items():
        assert node_type.isupper()
        assert spec.table in REAL_TABLES, f"{node_type} names undeclared table {spec.table!r}"


def test_unit_node_specs_has_exactly_fifteen_entries():
    assert len(NODE_SPECS) == 15


def test_unit_relation_types_are_exactly_the_seven_expected_strings():
    assert RELATION_TYPES == frozenset(
        {
            "VERIFIED_BY",
            "HAS_RESULT",
            "HAS_ACTION",
            "ASSESSED_BY",
            "GOVERNS",
            "ASSOCIATED_WITH",
            "AFFECTS",
        }
    )


def test_unit_edge_specs_endpoints_and_relation_types_are_all_valid():
    for spec in EDGE_SPECS:
        assert spec.source_type in NODE_SPECS, f"unknown source_type {spec.source_type!r}"
        assert spec.target_type in NODE_SPECS, f"unknown target_type {spec.target_type!r}"
        assert spec.relation_type in RELATION_TYPES, (
            f"relation_type {spec.relation_type!r} outside RELATION_TYPES"
        )
        assert spec.link_column_owner in ("source", "target")


def test_unit_change_affects_entity_types_are_all_node_specs_keys():
    for entity_type in CHANGE_AFFECTS_ENTITY_TYPES:
        assert entity_type in NODE_SPECS


def test_unit_node_specs_insertion_order_places_via_parent_after_its_parent():
    # Walks the ordered keys so a future reordering that would silently
    # drop child nodes (the parent's ids not yet collected when the child
    # is fetched) fails here, not only in an integration test.
    seen: list = []
    for node_type, spec in NODE_SPECS.items():
        if isinstance(spec.scope, tuple) and spec.scope[0] == "via_parent":
            parent_type = spec.scope[1]
            assert parent_type in seen, (
                f"{node_type}'s parent {parent_type!r} must precede it in NODE_SPECS"
            )
        seen.append(node_type)


# ---------------------------------------------------------------------------
# INTEGRATION -- live Postgres, never mocked
# ---------------------------------------------------------------------------


def test_integration_build_graph_returns_fourteen_nodes_and_nine_edges():
    async def _run():
        pool = await get_pool()
        return await build_graph(pool, "GXP-MFG-DEMO-01")

    G = asyncio.run(_run())
    assert G.number_of_nodes() == 14
    assert G.number_of_edges() == 9


def test_integration_node_type_histogram_matches_seeded_reality():
    async def _run():
        pool = await get_pool()
        return await build_graph(pool, "GXP-MFG-DEMO-01")

    G = asyncio.run(_run())
    histogram: dict = {}
    for _, attrs in G.nodes(data=True):
        histogram[attrs["node_type"]] = histogram.get(attrs["node_type"], 0) + 1

    assert histogram == {
        "SYSTEM": 1,
        "DOCUMENT": 2,
        "REQUIREMENT": 1,
        "TEST_CASE": 1,
        "RISK": 1,
        "DESIGN_ELEMENT": 1,
        "INCIDENT": 1,
        "ACCESS_REVIEW": 1,
        "ACCESS_RECORD": 1,
        "SUPPLIER": 1,
        "PERIODIC_EVALUATION": 1,
        "CHANGE": 1,
        "CHANGE_ACTION": 1,
    }
    assert "TEST_RESULT" not in histogram
    assert "SUPPLIER_ASSESSMENT" not in histogram


def test_integration_relation_type_histogram_matches_seeded_reality():
    async def _run():
        pool = await get_pool()
        return await build_graph(pool, "GXP-MFG-DEMO-01")

    G = asyncio.run(_run())
    histogram: dict = {}
    for _, _, attrs in G.edges(data=True):
        histogram[attrs["relation_type"]] = histogram.get(attrs["relation_type"], 0) + 1

    assert histogram == {
        "VERIFIED_BY": 1,
        "HAS_ACTION": 1,
        "GOVERNS": 2,
        "ASSOCIATED_WITH": 1,
        "AFFECTS": 4,
    }


def test_integration_change_affects_rows_each_produced_an_edge_to_the_right_target():
    async def _run():
        pool = await get_pool()
        return await build_graph(pool, "GXP-MFG-DEMO-01")

    G = asyncio.run(_run())
    for target in (
        "REQUIREMENT:URS-042",
        "DOCUMENT:DOC-2026-OM-99",
        "DESIGN_ELEMENT:DE-2026-DB-01",
    ):
        assert G.has_edge("CHANGE:CR-2026-089", target)
        assert G.edges["CHANGE:CR-2026-089", target]["relation_type"] == "AFFECTS"


def test_integration_change_action_reached_by_has_action_via_parent_scope():
    async def _run():
        pool = await get_pool()
        return await build_graph(pool, "GXP-MFG-DEMO-01")

    G = asyncio.run(_run())
    assert "CHANGE_ACTION:CA-2026-089-1" in G.nodes
    assert G.has_edge("CHANGE:CR-2026-089", "CHANGE_ACTION:CA-2026-089-1")
    assert G.edges["CHANGE:CR-2026-089", "CHANGE_ACTION:CA-2026-089-1"]["relation_type"] == (
        "HAS_ACTION"
    )


def test_integration_incident_node_properties_match_real_column_value():
    async def _run():
        pool = await get_pool()
        G = await build_graph(pool, "GXP-MFG-DEMO-01")
        row = await pool.fetchrow(
            "SELECT patient_safety_relevant FROM incidents WHERE id = $1", "INC-849201"
        )
        return G, row

    G, row = asyncio.run(_run())
    node = G.nodes["INCIDENT:INC-849201"]
    assert node["properties"]["patient_safety_relevant"] == row["patient_safety_relevant"]


def test_integration_persist_then_load_round_trips_full_graph():
    async def _run():
        pool = await get_pool()
        built = await build_graph(pool, "GXP-MFG-DEMO-01")
        await persist_graph(pool, "GXP-MFG-DEMO-01", built)
        loaded = await load_graph(pool, "GXP-MFG-DEMO-01")
        return built, loaded

    built, loaded = asyncio.run(_run())
    assert set(loaded.nodes) == set(built.nodes)
    assert set(loaded.edges) == set(built.edges)
    assert loaded.number_of_nodes() == 14
    assert loaded.number_of_edges() == 9
    for node_id in built.nodes:
        assert loaded.nodes[node_id]["node_type"] == built.nodes[node_id]["node_type"]
        assert loaded.nodes[node_id]["properties"] == built.nodes[node_id]["properties"]
    for edge in built.edges:
        assert loaded.edges[edge]["relation_type"] == built.edges[edge]["relation_type"]


def test_integration_build_graph_empty_system_is_the_discrimination_control():
    async def _run():
        pool = await get_pool()
        return await build_graph(pool, "BUS-IT-DEMO-02")

    G = asyncio.run(_run())
    assert set(G.nodes) == {"SYSTEM:BUS-IT-DEMO-02"}
    assert set(G.edges) == set()


# ---------------------------------------------------------------------------
# NEGATIVE
# ---------------------------------------------------------------------------


def test_negative_change_affects_row_outside_allowlist_produces_no_edge():
    async def _run():
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO change_affects (change_id, entity_type, entity_id) "
            "VALUES ($1, $2, $3) ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING",
            "CR-2026-089",
            "ACCESS_RECORD",  # valid NODE_SPECS key, but NOT in CHANGE_AFFECTS_ENTITY_TYPES
            "ACC-2026-99",
        )
        try:
            G = await build_graph(pool, "GXP-MFG-DEMO-01")
            edge_count = G.number_of_edges()
        finally:
            await pool.execute(
                "DELETE FROM change_affects WHERE change_id = $1 AND entity_type = $2 "
                "AND entity_id = $3",
                "CR-2026-089",
                "ACCESS_RECORD",
                "ACC-2026-99",
            )
        return edge_count

    edge_count = asyncio.run(_run())
    assert edge_count == 9  # unchanged from the clean-state count


def test_negative_change_affects_row_naming_nonexistent_entity_produces_no_edge_and_persists():
    async def _run():
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO change_affects (change_id, entity_type, entity_id) "
            "VALUES ($1, $2, $3) ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING",
            "CR-2026-089",
            "RISK",  # valid entity_type, but this entity_id does not exist
            "RSK-DOES-NOT-EXIST",
        )
        try:
            G = await build_graph(pool, "GXP-MFG-DEMO-01")
            edge_count = G.number_of_edges()
            persist_result = await persist_graph(pool, "GXP-MFG-DEMO-01", G)
        finally:
            await pool.execute(
                "DELETE FROM change_affects WHERE change_id = $1 AND entity_type = $2 "
                "AND entity_id = $3",
                "CR-2026-089",
                "RISK",
                "RSK-DOES-NOT-EXIST",
            )
            rebuilt = await build_graph(pool, "GXP-MFG-DEMO-01")
            await persist_graph(pool, "GXP-MFG-DEMO-01", rebuilt)
        return edge_count, persist_result

    edge_count, persist_result = asyncio.run(_run())
    assert edge_count == 9  # the dangling row produced no edge
    assert persist_result["edge_count"] == 9  # persist_graph did not raise


def test_negative_no_edge_between_nodes_sharing_only_system_id():
    async def _run():
        pool = await get_pool()
        return await build_graph(pool, "GXP-MFG-DEMO-01")

    G = asyncio.run(_run())
    # D-03's rejected shortcut: two nodes that merely share a system_id and
    # are not connected by a declared foreign key or a change_affects row
    # must never be linked, in either direction.
    assert not G.has_edge("ACCESS_REVIEW:AR-2026-05", "ACCESS_RECORD:ACC-2026-99")
    assert not G.has_edge("ACCESS_RECORD:ACC-2026-99", "ACCESS_REVIEW:AR-2026-05")
    assert not G.has_edge("SUPPLIER:SUP-2026-01", "SYSTEM:GXP-MFG-DEMO-01")
    assert not G.has_edge("SYSTEM:GXP-MFG-DEMO-01", "SUPPLIER:SUP-2026-01")


def test_edge_add_edge_rejects_relation_type_outside_allowlist():
    import networkx as nx

    G = nx.DiGraph()
    G.add_node("A:1")
    G.add_node("B:1")
    with pytest.raises(ValueError):
        _add_edge(G, "A:1", "B:1", "NOT_A_REAL_RELATION")


# ---------------------------------------------------------------------------
# EDGE
# ---------------------------------------------------------------------------


def test_edge_single_row_system_yields_one_node_and_persist_handles_zero_edges():
    async def _run():
        pool = await get_pool()
        G = await build_graph(pool, "BUS-IT-DEMO-02")
        try:
            return await persist_graph(pool, "BUS-IT-DEMO-02", G)
        finally:
            # test_routes_evidence_graph.py's
            # test_get_bus_it_demo_empty_cache_returns_200_with_empty_lists
            # asserts BUS-IT-DEMO-02's cache stays empty until an operator
            # explicitly rebuilds it (D-02) -- restore that state so this
            # test's own persist_graph call (needed to prove the zero-edge
            # case does not raise) does not leak into that assumption.
            await pool.execute("DELETE FROM graph_nodes WHERE system_id = $1", "BUS-IT-DEMO-02")

    result = asyncio.run(_run())
    assert result == {"node_count": 1, "edge_count": 0}


def test_edge_system_with_no_changes_rows_skips_change_affects_lookup_without_raising():
    async def _run():
        pool = await get_pool()
        # BUS-IT-DEMO-02 has no `changes` rows at all, so the change_ids
        # list passed to _add_change_affects_edges is empty.
        return await build_graph(pool, "BUS-IT-DEMO-02")

    G = asyncio.run(_run())
    assert set(G.nodes) == {"SYSTEM:BUS-IT-DEMO-02"}
    assert set(G.edges) == set()


def test_edge_build_graph_twice_is_deterministic():
    async def _run():
        pool = await get_pool()
        first = await build_graph(pool, "GXP-MFG-DEMO-01")
        second = await build_graph(pool, "GXP-MFG-DEMO-01")
        return first, second

    first, second = asyncio.run(_run())
    assert set(first.nodes) == set(second.nodes)
    assert set(first.edges) == set(second.edges)
