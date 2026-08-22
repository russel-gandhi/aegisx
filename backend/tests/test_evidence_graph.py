"""
Tests for `app.graph.evidence_graph` (Phase 4, plan 04-01 tracer).

Ticket: SENT-3-01 | Requirement: GRAPH-01
Source: AegisX-AI-Project-Bible-v6.md Section 10.1 (`build_evidence_graph` /
`find_downstream_impacts`) and Section 1.3's deterministic-first constraint.

CLAUDE.md Rule 6 requires unit + negative + edge-case + integration
coverage for the evidence graph, not a smoke test. Structured in the same
four-section comment convention `test_c1_verifier.py` establishes:

- UNIT: `make_node_id`/`split_node_id` round-tripping and the frozen
  allowlist shape guarantees (no DB).
- INTEGRATION: `build_graph`/`persist_graph`/`load_graph` against live,
  seeded Postgres (`GXP-MFG-DEMO-01`) and the empty-graph discrimination
  control (`BUS-IT-DEMO-02`) -- never mocked (D-04 convention carried over
  from C1's test suite).
- NEGATIVE/EDGE: a dangling `test_case_id`, an unknown system id, and an
  out-of-allowlist relation type.

Follows the established `asyncio.run()`-inside-a-plain-`def`-test
convention; pytest-asyncio is deliberately absent.
"""

import asyncio

import pytest

from app.db import get_pool
from app.graph.evidence_graph import (
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


def test_unit_make_node_id_joins_type_and_entity_with_single_colon():
    assert make_node_id("REQUIREMENT", "URS-042") == "REQUIREMENT:URS-042"


def test_unit_split_node_id_inverts_make_node_id():
    assert split_node_id("REQUIREMENT:URS-042") == ("REQUIREMENT", "URS-042")


def test_unit_split_node_id_round_trips_entity_id_containing_colon():
    entity_id = "SOME:WEIRD:ID"
    node_id = make_node_id("TEST_CASE", entity_id)
    assert split_node_id(node_id) == ("TEST_CASE", entity_id)


def test_unit_node_specs_and_relation_types_are_uppercase_and_reference_real_tables():
    real_tables = {
        "gxp_systems",
        "requirements",
        "test_cases",
        "documents",
        "access_reviews",
        "risks",
        "incidents",
        "suppliers",
        "periodic_evaluations",
        "access_records",
        "changes",
        "change_actions",
    }
    for node_type, spec in NODE_SPECS.items():
        assert node_type.isupper()
        assert spec.table in real_tables
    for relation_type in RELATION_TYPES:
        assert relation_type.isupper()


# ---------------------------------------------------------------------------
# INTEGRATION -- live Postgres, never mocked
# ---------------------------------------------------------------------------


def test_integration_build_graph_returns_exact_tracer_nodes_and_edge():
    async def _run():
        pool = await get_pool()
        return await build_graph(pool, "GXP-MFG-DEMO-01")

    G = asyncio.run(_run())
    assert set(G.nodes) == {
        "SYSTEM:GXP-MFG-DEMO-01",
        "REQUIREMENT:URS-042",
        "TEST_CASE:TC-2026-042",
    }
    assert set(G.edges) == {("REQUIREMENT:URS-042", "TEST_CASE:TC-2026-042")}
    edge_data = G.edges["REQUIREMENT:URS-042", "TEST_CASE:TC-2026-042"]
    assert edge_data["relation_type"] == "VERIFIED_BY"


def test_integration_node_properties_match_real_column_value():
    async def _run():
        pool = await get_pool()
        G = await build_graph(pool, "GXP-MFG-DEMO-01")
        row = await pool.fetchrow("SELECT status FROM test_cases WHERE id = $1", "TC-2026-042")
        return G, row

    G, row = asyncio.run(_run())
    node = G.nodes["TEST_CASE:TC-2026-042"]
    assert node["properties"]["status"] == row["status"]


def test_integration_persist_then_load_round_trips_graph():
    async def _run():
        pool = await get_pool()
        built = await build_graph(pool, "GXP-MFG-DEMO-01")
        await persist_graph(pool, "GXP-MFG-DEMO-01", built)
        loaded = await load_graph(pool, "GXP-MFG-DEMO-01")
        return built, loaded

    built, loaded = asyncio.run(_run())
    assert set(loaded.nodes) == set(built.nodes)
    assert set(loaded.edges) == set(built.edges)
    for node_id in built.nodes:
        assert loaded.nodes[node_id]["node_type"] == built.nodes[node_id]["node_type"]
    for edge in built.edges:
        assert loaded.edges[edge]["relation_type"] == built.edges[edge]["relation_type"]


def test_integration_persist_graph_twice_leaves_same_counts_and_does_not_raise():
    async def _run():
        pool = await get_pool()
        built = await build_graph(pool, "GXP-MFG-DEMO-01")
        first = await persist_graph(pool, "GXP-MFG-DEMO-01", built)
        second = await persist_graph(pool, "GXP-MFG-DEMO-01", built)
        return first, second

    first, second = asyncio.run(_run())
    assert first == second == {"node_count": 3, "edge_count": 1}


def test_integration_build_graph_empty_system_is_the_discrimination_control():
    async def _run():
        pool = await get_pool()
        return await build_graph(pool, "BUS-IT-DEMO-02")

    G = asyncio.run(_run())
    assert set(G.nodes) == {"SYSTEM:BUS-IT-DEMO-02"}
    assert set(G.edges) == set()


# ---------------------------------------------------------------------------
# NEGATIVE / EDGE
# ---------------------------------------------------------------------------


def test_negative_dangling_test_case_id_yields_node_but_no_edge():
    async def _run():
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO requirements (id, system_id, req_text, test_case_id) "
            "VALUES ($1, $2, $3, $4) ON CONFLICT (id) DO NOTHING",
            "URS-DANGLING-TEST",
            "GXP-MFG-DEMO-01",
            "temp requirement for dangling-FK test",
            "TC-DOES-NOT-EXIST",
        )
        try:
            G = await build_graph(pool, "GXP-MFG-DEMO-01")
            result = await persist_graph(pool, "GXP-MFG-DEMO-01", G)
        finally:
            await pool.execute("DELETE FROM requirements WHERE id = $1", "URS-DANGLING-TEST")
            # restore the tracer's canonical cache state for later tests
            rebuilt = await build_graph(pool, "GXP-MFG-DEMO-01")
            await persist_graph(pool, "GXP-MFG-DEMO-01", rebuilt)
        return G, result

    G, result = asyncio.run(_run())
    assert "REQUIREMENT:URS-DANGLING-TEST" in G.nodes
    assert ("REQUIREMENT:URS-DANGLING-TEST", "TEST_CASE:TC-DOES-NOT-EXIST") not in G.edges
    assert result["node_count"] >= 1


def test_negative_build_graph_unknown_system_returns_empty_graph_without_raising():
    async def _run():
        pool = await get_pool()
        return await build_graph(pool, "NO-SUCH-SYSTEM")

    G = asyncio.run(_run())
    assert set(G.nodes) == set()
    assert set(G.edges) == set()


def test_edge_add_edge_rejects_relation_type_outside_allowlist():
    import networkx as nx

    G = nx.DiGraph()
    G.add_node("A:1")
    G.add_node("B:1")
    with pytest.raises(ValueError):
        _add_edge(G, "A:1", "B:1", "NOT_A_REAL_RELATION")
