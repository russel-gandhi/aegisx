"""
Evidence graph HTTP routes (Phase 4, plans 04-01/04-04).

Ticket: SENT-3-01 (build/rebuild/read) / SENT-3-03 (Blast Radius) |
Requirement: GRAPH-03 / GRAPH-02
Source: 04-01-PLAN.md <interface_contract> route table; 04-04-PLAN.md
<interface_contract> route table (Blast Radius).

Every handler calls `acquire_pool_or_none()` and raises `HTTPException(503)`
when it returns None, matching `app.db`'s degrade-don't-raise contract;
every handler raises `HTTPException(404)` when the named system does not
exist in `gxp_systems`.
"""

import json

import networkx as nx
from fastapi import APIRouter, HTTPException, Query

from app.db import acquire_pool_or_none
from app.graph.evidence_graph import blast_radius, build_graph, load_graph, persist_graph
from app.schemas import (
    BlastRadiusResponse,
    EvidenceGraphRebuildResponse,
    EvidenceGraphResponse,
)

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


@router.get(
    "/api/systems/{system_id}/blast-radius",
    response_model=BlastRadiusResponse,
)
async def get_blast_radius(system_id: str, node_id: str = Query(...)):
    """Blast Radius (plan 04-04, SENT-3-03, GRAPH-02). `node_id` is a
    required query parameter, not a path segment, because node ids are
    type-prefixed and carry a colon (`"REQUIREMENT:URS-042"`) -- a query
    parameter keeps the routing unambiguous and client-side encoding
    trivial.

    Reads through `load_graph` only -- never `build_graph` -- because per
    D-02 this is a read path and a read never rebuilds the cache. Raises
    404 when the system does not exist or when `node_id` is absent from
    that system's graph (`nx.NetworkXError`, the exception
    `evidence_graph.blast_radius` raises for an absent source -- see its
    own docstring); a change record with no derived edges, or a node id
    for a different system, is a valid and expected state, not a server
    error. An empty blast radius for a node that *is* present (e.g. the
    `SYSTEM` sink node itself) returns 200 with all-empty buckets, not 404.

    Deliberately carries no LLM-generated narrative summary field. Bible
    Section 14.3 permits a model to summarise an already-computed impact,
    but D-05 scopes this phase to the deterministic result only, and
    adding one would put model prose inside the same response object as
    the verified numbers.
    """
    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")
    if not await _system_exists(pool, system_id):
        raise HTTPException(status_code=404, detail=f"Unknown system_id: {system_id}")

    G = await load_graph(pool, system_id)
    try:
        result = blast_radius(G, node_id)
    except nx.NetworkXError:
        raise HTTPException(
            status_code=404,
            detail=(
                f"node_id {node_id!r} not found in {system_id}'s evidence graph. "
                f"If the graph has not been built yet, call "
                f"POST /api/systems/{system_id}/evidence-graph/rebuild first."
            ),
        )

    return BlastRadiusResponse(system_id=system_id, **result)
