"""
Tests for `app.routes.evidence_graph` (Phase 4, plan 04-01 tracer).

Ticket: SENT-3-01 | Requirement: GRAPH-03
Source: 04-01-PLAN.md <interface_contract> route table.

Exercises the two HTTP endpoints via `TestClient` against live, seeded
Postgres -- never mocked. The D-02 test (`test_get_does_not_recompute...`)
is the single most important assertion in this file: it proves the read
endpoint is provably incapable of silently rebuilding the cache behind an
operator's back.
"""

import asyncio

from app.db import get_pool


def _rebuild(client, system_id):
    return client.post(f"/api/systems/{system_id}/evidence-graph/rebuild")


def test_rebuild_gxp_demo_returns_fourteen_nodes_nine_edges(client):
    resp = _rebuild(client, "GXP-MFG-DEMO-01")
    assert resp.status_code == 200
    body = resp.json()
    assert body["system_id"] == "GXP-MFG-DEMO-01"
    assert body["node_count"] == 14
    assert body["edge_count"] == 9


def test_get_after_rebuild_matches_cache_tables_directly(client):
    _rebuild(client, "GXP-MFG-DEMO-01")
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/evidence-graph")
    assert resp.status_code == 200
    body = resp.json()

    async def _direct():
        pool = await get_pool()
        nodes = await pool.fetch(
            "SELECT node_id FROM graph_nodes WHERE system_id = $1", "GXP-MFG-DEMO-01"
        )
        edges = await pool.fetch(
            "SELECT ge.source_id, ge.target_id FROM graph_edges ge "
            "JOIN graph_nodes gn ON gn.node_id = ge.source_id WHERE gn.system_id = $1",
            "GXP-MFG-DEMO-01",
        )
        return nodes, edges

    nodes, edges = asyncio.run(_direct())
    assert {n["node_id"] for n in nodes} == {n["node_id"] for n in body["nodes"]}
    assert {(e["source_id"], e["target_id"]) for e in edges} == {
        (e["source_id"], e["target_id"]) for e in body["edges"]
    }


def test_get_does_not_recompute_a_cache_mutated_behind_its_back(client):
    # D-02: the read endpoint must never rebuild. Prove it by mutating the
    # cache directly, reading through the endpoint, and asserting the
    # mutation survived the read (a recomputing endpoint would silently
    # restore the deleted edge). Deleting the one edge sourced from
    # REQUIREMENT:URS-042 (VERIFIED_BY) leaves 8 of the full 9 edges behind
    # (plan 04-02: the graph now has 9 edges total, not 1).
    _rebuild(client, "GXP-MFG-DEMO-01")
    try:
        async def _delete_one_edge():
            pool = await get_pool()
            await pool.execute(
                "DELETE FROM graph_edges WHERE source_id = $1",
                "REQUIREMENT:URS-042",
            )

        asyncio.run(_delete_one_edge())

        resp = client.get("/api/systems/GXP-MFG-DEMO-01/evidence-graph")
        assert resp.status_code == 200
        assert len(resp.json()["edges"]) == 8
    finally:
        _rebuild(client, "GXP-MFG-DEMO-01")


def test_get_unknown_system_returns_404(client):
    resp = client.get("/api/systems/NO-SUCH-SYSTEM/evidence-graph")
    assert resp.status_code == 404


def test_rebuild_unknown_system_returns_404(client):
    resp = _rebuild(client, "NO-SUCH-SYSTEM")
    assert resp.status_code == 404


def test_get_bus_it_demo_empty_cache_returns_200_with_empty_lists(client):
    resp = client.get("/api/systems/BUS-IT-DEMO-02/evidence-graph")
    assert resp.status_code == 200
    body = resp.json()
    assert body["nodes"] == []
    assert body["edges"] == []
