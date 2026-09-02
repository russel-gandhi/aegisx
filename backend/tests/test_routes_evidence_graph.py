"""
Tests for `app.routes.evidence_graph` (Phase 4, plans 04-01/04-04).

Ticket: SENT-3-01 (build/rebuild/read) / SENT-3-03 (Blast Radius) |
Requirement: GRAPH-03 / GRAPH-02
Source: 04-01-PLAN.md <interface_contract> route table; 04-04-PLAN.md
<interface_contract> route table (Blast Radius).

Exercises the HTTP endpoints via `TestClient` against live, seeded
Postgres -- never mocked. The D-02 test (`test_get_does_not_recompute...`)
is the single most important assertion in the rebuild/read section: it
proves the read endpoint is provably incapable of silently rebuilding the
cache behind an operator's back. The Blast Radius section (plan 04-04)
proves the HTTP layer changes no value the traversal itself computed
(`test_blast_radius.py`'s own integration assertions), and that an unknown
node id degrades to 404 rather than 500 -- the specific defect
04-RESEARCH.md Pattern 3's edge-case note calls out.
"""

import asyncio

from app import db
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
    # REQUIREMENT:URS-042 (VERIFIED_BY) leaves 8 of the full 9 edges behind.
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


# ---------------------------------------------------------------------------
# Blast Radius (plan 04-04, GRAPH-02, SENT-3-03)
# ---------------------------------------------------------------------------


def test_blast_radius_gxp_demo_change_matches_integration_test_expectations(client):
    _rebuild(client, "GXP-MFG-DEMO-01")
    resp = client.get(
        "/api/systems/GXP-MFG-DEMO-01/blast-radius", params={"node_id": "CHANGE:CR-2026-089"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source_node_id"] == "CHANGE:CR-2026-089"
    assert body["system_id"] == "GXP-MFG-DEMO-01"
    assert body["direct_dependencies"] == [
        "CHANGE_ACTION:CA-2026-089-1",
        "DESIGN_ELEMENT:DE-2026-DB-01",
        "DOCUMENT:DOC-2026-OM-99",
        "REQUIREMENT:URS-042",
    ]
    assert body["indirect_dependencies"] == [
        "SYSTEM:GXP-MFG-DEMO-01",
        "TEST_CASE:TC-2026-042",
    ]
    assert body["affected_requirements"] == ["REQUIREMENT:URS-042"]
    assert body["affected_tests"] == ["TEST_CASE:TC-2026-042"]
    assert body["affected_risks"] == []
    assert body["affected_changes"] == ["CHANGE_ACTION:CA-2026-089-1"]
    assert body["affected_controls"] == []
    assert body["potential_gxp_impact"] == "HIGH"
    assert body["highest_impact_downstream"] == "REQUIREMENT:URS-042"


def test_blast_radius_unknown_node_id_returns_404_not_500(client):
    _rebuild(client, "GXP-MFG-DEMO-01")
    resp = client.get(
        "/api/systems/GXP-MFG-DEMO-01/blast-radius", params={"node_id": "NO-SUCH-NODE:X"}
    )
    assert resp.status_code == 404


def test_blast_radius_unknown_system_returns_404(client):
    resp = client.get(
        "/api/systems/NO-SUCH-SYSTEM/blast-radius", params={"node_id": "CHANGE:CR-2026-089"}
    )
    assert resp.status_code == 404


def test_blast_radius_missing_node_id_query_param_returns_422(client):
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/blast-radius")
    assert resp.status_code == 422


def test_blast_radius_node_id_containing_colon_survives_url_encoding_intact(client):
    _rebuild(client, "GXP-MFG-DEMO-01")
    resp = client.get(
        "/api/systems/GXP-MFG-DEMO-01/blast-radius", params={"node_id": "REQUIREMENT:URS-042"}
    )
    assert resp.status_code == 200
    assert resp.json()["source_node_id"] == "REQUIREMENT:URS-042"


def test_blast_radius_postgres_unreachable_returns_503(client, monkeypatch, reset_db_pool):
    monkeypatch.setattr(
        db, "DATABASE_URL", "postgresql://sentinel:sentinel@127.0.0.1:1/sentinel"
    )
    resp = client.get(
        "/api/systems/GXP-MFG-DEMO-01/blast-radius", params={"node_id": "CHANGE:CR-2026-089"}
    )
    assert resp.status_code == 503


def test_blast_radius_isolated_system_node_returns_200_empty_not_404(client):
    _rebuild(client, "BUS-IT-DEMO-02")
    try:
        resp = client.get(
            "/api/systems/BUS-IT-DEMO-02/blast-radius",
            params={"node_id": "SYSTEM:BUS-IT-DEMO-02"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["direct_dependencies"] == []
        assert body["indirect_dependencies"] == []
        assert body["affected_requirements"] == []
        assert body["affected_tests"] == []
        assert body["affected_risks"] == []
        assert body["affected_changes"] == []
        assert body["affected_controls"] == []
        assert body["affected_systems"] == []
        assert body["potential_gxp_impact"] == "NONE"
        assert body["highest_impact_downstream"] is None
    finally:
        # test_get_bus_it_demo_empty_cache_returns_200_with_empty_lists
        # asserts BUS-IT-DEMO-02's cache stays empty until an operator
        # explicitly rebuilds it (D-02) -- restore that state so this
        # test's own rebuild call does not leak into that assumption on a
        # later full-suite run.
        async def _clear():
            pool = await get_pool()
            await pool.execute("DELETE FROM graph_nodes WHERE system_id = $1", "BUS-IT-DEMO-02")

        asyncio.run(_clear())
