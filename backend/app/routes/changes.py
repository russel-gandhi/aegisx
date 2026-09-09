"""
`POST /api/changes/{change_id}/affects` -- write path for the `change_affects`
junction table (`infra/postgres/initdb/002_change_affects.sql`).

Closes a real gap: `change_affects` backs the evidence graph's one non-FK
edge (`CHANGE --AFFECTS--> X`, `app.graph.evidence_graph._add_change_affects_edges`,
D-03), but prior to this route the table was only ever populated by a static
3-row seed fixture (`infra/postgres/seed/003_change_affects_fixture.sql`) --
there was no API or UI path to record this relationship for any change
record other than the one seeded demo change.

Gated to "IT System Manager" -- change control is that role's domain per
the Bible's own Permission Matrix (the same role `POST /api/systems`
requires, since standing up change-impact linkage is an administrative
action on the system-of-record, not a read or an investigation).

`entity_type` is validated against the exact same frozen
`CHANGE_AFFECTS_ENTITY_TYPES` allowlist `evidence_graph.py` already uses --
imported, never duplicated, so the two can never drift out of sync
(T-04-02's allowlist-not-database-constraint discipline). Unlike the graph
builder's own read-time handling (an out-of-allowlist or dangling row is
logged and silently skipped, never raised), this is a write path: a
caller submitting an invalid `entity_type` or a `change_id`/`entity_id`
that does not exist gets a loud 4xx, not a silent drop -- silently
accepting a row that would just be skipped on the next graph read is worse
than telling the caller now.

Explicit-rebuild-only (D-01/D-02, documented at length in
`backend/README.md`'s "Phase 4 evidence graph" sections): `persist_graph()`
is the only writer of the `graph_nodes`/`graph_edges` cache tables anywhere
in this codebase, and a read route never recomputes on its own. This route
deliberately does NOT trigger a graph rebuild after inserting a
`change_affects` row -- doing so would make this a second, less obvious
writer of derived graph state, contradicting that principle. The cache
stays stale for this new relationship until an operator explicitly calls
`POST /api/systems/{system_id}/evidence-graph/rebuild`, exactly like every
other domain-table write in this codebase's Phase-4-and-later design
(`routes/documents.py`'s own post-upload auto-rebuild is the one existing
exception to this principle, not a precedent this route follows).
"""

from fastapi import APIRouter, Depends, HTTPException

from app.db import acquire_pool_or_none
from app.graph.evidence_graph import CHANGE_AFFECTS_ENTITY_TYPES, NODE_SPECS
from app.identity import RequestIdentity, require_identity
from app.schemas import ChangeAffectsCreateRequest, ChangeAffectsRecord

router = APIRouter()


@router.post(
    "/api/changes/{change_id}/affects",
    response_model=ChangeAffectsRecord,
    status_code=201,
)
async def create_change_affects(
    change_id: str,
    body: ChangeAffectsCreateRequest,
    identity: RequestIdentity = Depends(require_identity),
) -> ChangeAffectsRecord:
    if identity.role != "IT System Manager":
        raise HTTPException(
            status_code=403,
            detail=f"Role {identity.role} may not record a change-impact relationship",
        )

    if body.entity_type not in CHANGE_AFFECTS_ENTITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"entity_type must be one of {sorted(CHANGE_AFFECTS_ENTITY_TYPES)}, "
                f"got {body.entity_type!r}"
            ),
        )

    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")

    change_row = await pool.fetchrow("SELECT id FROM changes WHERE id = $1", change_id)
    if change_row is None:
        raise HTTPException(status_code=404, detail=f"Unknown change_id: {change_id}")

    # `NODE_SPECS[entity_type].table` is the same table name the graph
    # builder itself reads for this node type -- reused, never
    # re-derived, so this existence check can never name a different table
    # than the one the graph would actually resolve `entity_id` against.
    entity_table = NODE_SPECS[body.entity_type].table
    entity_row = await pool.fetchrow(
        f"SELECT id FROM {entity_table} WHERE id = $1", body.entity_id  # noqa: S608
    )
    if entity_row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown {body.entity_type} entity_id: {body.entity_id}",
        )

    await pool.execute(
        "INSERT INTO change_affects (change_id, entity_type, entity_id) "
        "VALUES ($1, $2, $3) ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING",
        change_id,
        body.entity_type,
        body.entity_id,
    )

    return ChangeAffectsRecord(
        change_id=change_id, entity_type=body.entity_type, entity_id=body.entity_id
    )
