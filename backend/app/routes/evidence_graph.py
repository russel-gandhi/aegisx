"""
Evidence graph HTTP routes (Phase 4, plan 04-01).

Ticket: SENT-3-01 | Requirement: GRAPH-03
Source: 04-01-PLAN.md <interface_contract> route table.

Both handlers call `acquire_pool_or_none()` and raise `HTTPException(503)`
when it returns None, matching `app.db`'s degrade-don't-raise contract;
both raise `HTTPException(404)` when the named system does not exist in
`gxp_systems`.
"""

import json

from fastapi import APIRouter, HTTPException

from app.db import acquire_pool_or_none
from app.graph.evidence_graph import build_graph, persist_graph
from app.schemas import EvidenceGraphRebuildResponse, EvidenceGraphResponse

router = APIRouter()


async def _system_exists(pool, system_id: str) -> bool:
    row = await pool.fetchrow("SELECT 1 FROM gxp_systems WHERE id = $1", system_id)
    return row is not None


@router.post(
    "/api/systems/{system_id}/evidence-graph/rebuild",
    response_model=EvidenceGraphRebuildResponse,
)
async def rebuild_evidence_graph(system_id: str):
    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")
    if not await _system_exists(pool, system_id):
        raise HTTPException(status_code=404, detail=f"Unknown system_id: {system_id}")

    G = await build_graph(pool, system_id)
    counts = await persist_graph(pool, system_id, G)
    return EvidenceGraphRebuildResponse(system_id=system_id, **counts)


@router.get(
    "/api/systems/{system_id}/evidence-graph",
    response_model=EvidenceGraphResponse,
)
async def get_evidence_graph(system_id: str):
    """Reads from the `graph_nodes`/`graph_edges` cache tables only and
    calls no function from this module's build path (D-02). A read that
    recomputed would reintroduce exactly the auto-rebuild-on-read design
    04-CONTEXT.md's Deferred Ideas section records as rejected -- the
    cache is populated only by a preceding call to the rebuild endpoint
    above."""
    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")
    if not await _system_exists(pool, system_id):
        raise HTTPException(status_code=404, detail=f"Unknown system_id: {system_id}")

    node_rows = await pool.fetch(
        "SELECT node_id, node_type, properties FROM graph_nodes WHERE system_id = $1",
        system_id,
    )
    edge_rows = await pool.fetch(
        "SELECT ge.source_id, ge.target_id, ge.relation_type "
        "FROM graph_edges ge JOIN graph_nodes gn ON gn.node_id = ge.source_id "
        "WHERE gn.system_id = $1",
        system_id,
    )

    nodes = []
    for row in node_rows:
        properties = row["properties"]
        if isinstance(properties, str):
            properties = json.loads(properties)
        node_type, entity_id = row["node_id"].split(":", 1)
        nodes.append(
            {
                "node_id": row["node_id"],
                "node_type": row["node_type"],
                "entity_id": entity_id,
                "properties": properties,
            }
        )

    edges = [
        {
            "source_id": row["source_id"],
            "target_id": row["target_id"],
            "relation_type": row["relation_type"],
        }
        for row in edge_rows
    ]

    return EvidenceGraphResponse(system_id=system_id, nodes=nodes, edges=edges)
