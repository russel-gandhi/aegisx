"""
Access/supplier overdue-signals HTTP route (Phase 6, plan 06-02, Task 1).

Ticket: SENT-5-01 | Requirement: UI-03 | Decisions: D-06, D-07
Source: 06-02-PLAN.md Task 1 <action>; mirrors
`app.agents.minimal_specialists._check_a6`'s overdue-access-review query
pattern (that query is otherwise only reachable via the LangGraph node
path, not any HTTP route -- 06-RESEARCH.md Architecture Patterns) plus a
new, analogous overdue-suppliers query (mirrors Rego rule
`ANNEX11-S3-SUP-001`, Bible Section 3.3 rule #6).

This is the one net-new backend route Phase 6's Command Centre needs
(06-RESEARCH.md Summary) -- everything else composes client-side over
already-existing routes (`assurance-cards`, `/api/actions`,
`/api/audit/verify`). It feeds Command Centre mini-cards #5 (Access
Reviews) and #6 (Supplier Qualification), per 06-UI-SPEC.md's D-07
mapping table.

Deliberately left ungated (no RBAC, no `require_identity` dependency),
matching the explicit precedent `routes/actions.py`'s own module
docstring records for the Phase 4 read routes (`evidence_graph.py`,
`findings.py`): read-only, non-PII aggregate GxP metadata (supplier
company names, overdue counts), not a one-off exception to invent. See
this plan's `<threat_model>` (T-06-05/T-06-06) for the accepted-risk
rationale.

`_system_exists` is imported from `app.routes.evidence_graph`, never
redefined -- a second copy would be exactly the drift risk
`app.opa_client`'s own docstring warns against. Both queries below bind
`system_id` through asyncpg `$N` placeholders exclusively (ASVS V5, no
f-string SQL), matching this codebase's established no-f-string-SQL
discipline (T-06-07).
"""

import time

from fastapi import APIRouter, HTTPException

from app.db import acquire_pool_or_none
from app.routes.evidence_graph import _system_exists
from app.schemas import SystemSignalsResponse

router = APIRouter()


@router.get(
    "/api/systems/{system_id}/access-supplier-signals",
    response_model=SystemSignalsResponse,
)
async def get_access_supplier_signals(system_id: str):
    """Overdue access-review and overdue-supplier counts for `system_id`.

    `overdue_access_reviews` mirrors `_check_a6`'s own review query exactly
    (status not yet COMPLETED, scheduled in the past) but as a `pool.fetch`
    count rather than a single `fetchrow` -- this route reports how many
    are overdue, not just the earliest one. `overdue_suppliers` /
    `overdue_supplier_names` read every `suppliers` row whose
    `reassessment_due_date_ns` has passed, explicitly naming each one (Bible
    Section 11.5's own call-out; 06-UI-SPEC.md mini-card #6 requires the
    overdue supplier be named, not just counted).
    """
    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")
    if not await _system_exists(pool, system_id):
        raise HTTPException(status_code=404, detail=f"Unknown system_id: {system_id}")

    now_ns = time.time_ns()

    review_rows = await pool.fetch(
        "SELECT id FROM access_reviews WHERE system_id = $1 "
        "AND status != 'COMPLETED' AND scheduled_date_ns < $2",
        system_id,
        now_ns,
    )
    supplier_rows = await pool.fetch(
        "SELECT id, name FROM suppliers WHERE system_id = $1 "
        "AND reassessment_due_date_ns < $2",
        system_id,
        now_ns,
    )

    return SystemSignalsResponse(
        system_id=system_id,
        overdue_access_reviews=len(review_rows),
        overdue_suppliers=len(supplier_rows),
        overdue_supplier_names=[row["name"] for row in supplier_rows],
    )
