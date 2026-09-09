"""
System inventory + readiness routes (Bible Section 12: `GET /api/systems`,
`GET /api/systems/{id}/readiness`).

Remediation follow-up to REMEDIATION-PLAN.md #6. Both routes were absent
from every phase's ticket list through Phase 06.1 -- neither is scope
creep introduced here; they close a documented gap against the Bible's
own API table.

`GET /api/systems` is a straightforward read over `gxp_systems`, matching
this codebase's established list-route shape (`routes/documents.py`,
`routes/actions.py`): pool-acquire-or-503, no further guard needed since
there's no `system_id` path/query parameter to validate against.

`GET /api/systems/{id}/readiness`'s `score` field is read directly from
`gxp_systems.readiness_score` -- a column the Bible's own Section 5 seed
data populates with a fixed value (61 for the unhealthy demo system, 94
for the healthy one) and for which the Bible defines no live-computation
formula anywhere (`SystemReadinessScore`'s own model definition is just
`{system_id, score, breakdown}`, no formula). This route does NOT
recompute that value from live gap data the way `chunk_count`/
`ingestion_status` are recomputed elsewhere in this codebase --
deliberately: inventing a weighting formula the Bible never specifies
would be exactly the kind of silently-invented metric CLAUDE.md Rule 7
warns against, not a faithful implementation of an ambiguous spec. What
IS live-computed is `breakdown["open_findings"]`, a real count from
`get_assurance_cards()` -- genuine signal, not a stored counter that
could drift, added without guessing at a category-weighted score this
route has no specification for. If the Bible reconciliation process
(SENT-7-05) later settles on a real scoring formula, this docstring is
where that decision belongs.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.db import acquire_pool_or_none
from app.identity import RequestIdentity, require_identity
from app.routes.findings import get_assurance_cards
from app.schemas import SystemCreateRequest, SystemReadinessScore, SystemRecord

router = APIRouter()

logger = logging.getLogger(__name__)


@router.post("/api/systems", response_model=SystemRecord, status_code=201)
async def create_system(
    body: SystemCreateRequest,
    identity: RequestIdentity = Depends(require_identity),
) -> SystemRecord:
    """Adds a new row to `gxp_systems`. Gated to "IT System Manager" --
    the one role the Bible's own Permission Matrix already grants every
    domain agent (A1-A7) to (`c2_gateway.PERMISSION_MATRIX`) -- rather
    than left open to every recognised role, since standing up a new
    system-of-record is an administrative action, not a read or an
    investigation. RBAC is checked before the pool guard and before any
    row is written, matching `actions.generate_capa`'s ordering.

    A freshly created system starts with zero linked evidence (no
    documents, requirements, test cases, ...) -- that is a real, expected
    empty state, not an error, and mirrors the evidence graph's own
    explicit-rebuild-only contract (`routes/evidence_graph.py`): nothing
    here fabricates placeholder domain rows on the new system's behalf.
    """
    if identity.role != "IT System Manager":
        raise HTTPException(
            status_code=403,
            detail=f"Role {identity.role} may not create a new system",
        )

    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")

    existing = await pool.fetchrow("SELECT id FROM gxp_systems WHERE id = $1", body.id)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"System id already exists: {body.id}")

    row = await pool.fetchrow(
        "INSERT INTO gxp_systems "
        "(id, name, description, system_owner, lifecycle_state, gxp_impact) "
        "VALUES ($1, $2, $3, $4, $5, $6) "
        "RETURNING id, name, description, system_owner, lifecycle_state, "
        "gxp_impact, readiness_score, last_backup_test_ns",
        body.id,
        body.name,
        body.description,
        body.system_owner,
        body.lifecycle_state,
        body.gxp_impact,
    )
    return SystemRecord(**dict(row))


@router.get("/api/systems")
async def list_systems():
    """Returns every seeded GxP system. `List[Dict]` per the Bible's own
    Section 12 response-body entry for this route -- no dedicated Pydantic
    model exists for a "system" resource anywhere else in this codebase to
    reuse, and inventing one here for a single, simple read is exactly the
    kind of scope this route doesn't need."""
    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")

    rows = await pool.fetch(
        "SELECT id, name, description, system_owner, lifecycle_state, "
        "gxp_impact, readiness_score, last_backup_test_ns "
        "FROM gxp_systems ORDER BY id"
    )
    return [dict(row) for row in rows]


@router.get(
    "/api/systems/{system_id}/readiness",
    response_model=SystemReadinessScore,
)
async def get_system_readiness(system_id: str) -> SystemReadinessScore:
    """See module docstring for why `score` is the stored
    `gxp_systems.readiness_score` value rather than a live-recomputed one,
    and why `breakdown` carries exactly one real, live-derived field."""
    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")

    row = await pool.fetchrow(
        "SELECT readiness_score FROM gxp_systems WHERE id = $1", system_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown system_id: {system_id}")

    cards_response = await get_assurance_cards(system_id)

    return SystemReadinessScore(
        system_id=system_id,
        score=row["readiness_score"],
        breakdown={"open_findings": len(cards_response.cards)},
    )
