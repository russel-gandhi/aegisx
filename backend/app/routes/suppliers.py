"""
Supplier Intelligence full-registry route (Bible Section 11.5).

Ticket: n/a | Requirement: bible Section 11.5's own call-out
Source: AegisX-AI-Project-Bible-v6.md Section 11.5 -- "Supplier registry for
each system showing all vendors, their qualification status, reassessment
due dates, and open CAPAs. Explicitly highlights the `DataSync Solutions`
overdue finding injected via the seed script."

Distinct from `system_signals.py`'s `access-supplier-signals` route, which
only returns the Command Centre's overdue-count aggregate -- this route
returns the full per-supplier registry the Supplier Intelligence page (Bible
11.5) needs to render, joining each `suppliers` row against its most recent
`supplier_assessments` row (if any). `action_proposals` carries no
supplier-linking column in the current schema (`target_system` only), so
"open CAPAs" cannot be resolved per-supplier honestly yet -- this route does
not fabricate that join; the frontend page reads it as absent rather than
zero.

Deliberately left ungated, matching `system_signals.py`'s own documented
precedent: read-only, non-PII aggregate GxP metadata (supplier company
names, dates, status strings), not a one-off exception to invent.
"""

import time

from fastapi import APIRouter, HTTPException

from app.db import acquire_pool_or_none
from app.routes.evidence_graph import _system_exists
from app.schemas import SupplierRecord, SuppliersResponse

router = APIRouter()


@router.get("/api/systems/{system_id}/suppliers", response_model=SuppliersResponse)
async def get_suppliers(system_id: str) -> SuppliersResponse:
    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")
    if not await _system_exists(pool, system_id):
        raise HTTPException(status_code=404, detail=f"Unknown system_id: {system_id}")

    now_ns = time.time_ns()

    # DISTINCT ON + ORDER BY ... DESC picks each supplier's single most
    # recent assessment row (or none, via the LEFT JOIN) -- never an
    # arbitrary one, and never a fan-out of multiple assessment rows per
    # supplier into duplicate SupplierRecord entries.
    rows = await pool.fetch(
        """
        SELECT s.id AS supplier_id, s.name, s.status, s.reassessment_due_date_ns,
               latest.result AS latest_result, latest.assessment_date_ns AS latest_date_ns
        FROM suppliers s
        LEFT JOIN LATERAL (
            SELECT result, assessment_date_ns
            FROM supplier_assessments sa
            WHERE sa.supplier_id = s.id
            ORDER BY sa.assessment_date_ns DESC
            LIMIT 1
        ) latest ON true
        WHERE s.system_id = $1
        ORDER BY s.name
        """,
        system_id,
    )

    suppliers = [
        SupplierRecord(
            supplier_id=row["supplier_id"],
            name=row["name"],
            status=row["status"],
            reassessment_due_date_ns=row["reassessment_due_date_ns"],
            is_overdue=(
                row["reassessment_due_date_ns"] is not None
                and row["reassessment_due_date_ns"] < now_ns
            ),
            latest_assessment_result=row["latest_result"],
            latest_assessment_date_ns=row["latest_date_ns"],
        )
        for row in rows
    ]

    return SuppliersResponse(system_id=system_id, suppliers=suppliers)
