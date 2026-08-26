"""
Audit chain HTTP routes (Phase 5, plan 05-03).

Ticket: SENT-4-06, SENT-4-07 | Requirement: AUDIT-02, AUDIT-03
Source: Bible Section 12 API table and Section 7.1

Neither route below recomputes anything -- each returns `audit_trail`'s
own verdict verbatim, matching `routes/actions.py`'s "no field authored
at response-assembly time" guarantee. Per D-04 the read route
(`GET /api/audit/verify`) carries no RBAC gate, consistent with the
Phase 4 read routes this repo already leaves ungated. The tamper route,
being a write (and a deliberately reachable audit-mutation endpoint --
see `audit_trail.demonstrate_tamper`'s own docstring and this plan's
threat register, T-05-15), resolves identity via `require_identity` so
its own invocation is attributable, and that invocation is logged as a
chain link *before* the tamper occurs (T-05-16). It is additionally
authorization-gated through `c2_gateway.check_rbac` (quick task
260827-045, closing review finding CR-01): `require_identity` alone
recognises all three Bible-defined roles, which left the read-only
Auditor role able to invoke a route that performs a real `UPDATE`
against the very table whose entire purpose is tamper-evidence. The
RBAC gate restricts invocation to IT System Manager, deriving that
restriction from the shared permission matrix rather than restating a
role name here -- see `post_demonstrate_tamper`'s own docstring for why.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.agents.c2_gateway import check_rbac
from app.audit_trail import demonstrate_tamper, log_event, verify_chain
from app.db import acquire_pool_or_none
from app.identity import RequestIdentity, require_identity
from app.schemas import ChainVerificationResponse, TamperDemoResponse

router = APIRouter()


class TamperDemoRequest(BaseModel):
    event_id: str


@router.get("/api/audit/verify", response_model=ChainVerificationResponse)
async def get_chain_verification():
    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")

    return ChainVerificationResponse(**await verify_chain(pool))


@router.post("/api/audit/demonstrate-tamper", response_model=TamperDemoResponse)
async def post_demonstrate_tamper(
    request: TamperDemoRequest,
    identity: RequestIdentity = Depends(require_identity),
):
    """CR-01: gated with `check_rbac(identity.role, "A7")` rather than a
    role-name comparison. A7 is used not because this route triggers A7
    Remediation -- it does not -- but because A7's holder set in
    `PERMISSION_MATRIX` (IT System Manager only) is exactly the intended
    allow set for this route, so authority is derived from the matrix
    instead of a second, route-local copy of the same fact.

    The agent id recorded in this route's own `log_event` payload below
    (`agent_id="C3"`, for audit attribution of who invoked the demo) is a
    separate concern from the capability id passed to `check_rbac` here --
    the two are not interchangeable. `PERMISSION_MATRIX` is keyed A1..A7
    only, so passing "C3" to `check_rbac` would fail closed for every
    role, including IT System Manager.

    The guard runs before `acquire_pool_or_none` and before `log_event`,
    so a denied caller never reaches Postgres and no `TAMPER_DEMO_INVOKED`
    row is written for a refused attempt -- deliberately un-audited, since
    the guard is placed exactly where `generate_capa`'s (`routes/actions.py`)
    is: ahead of the pool acquisition and any write.
    """
    if not check_rbac(identity.role, "A7"):
        raise HTTPException(
            status_code=403,
            detail=f"Role {identity.role} may not invoke the audit tamper demo",
        )

    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")

    # Logged before the tamper is issued so the demo's own audit entry is
    # itself a valid chain link, rather than a link written after the
    # chain it belongs to is already broken (T-05-16).
    await log_event(
        pool,
        {
            "session_id": None,
            "user_id": identity.user_id,
            "user_role": identity.role,
            "agent_id": "C3",
            "action_type": "TAMPER_DEMO_INVOKED",
            "target_system_id": None,
            "target_record_id": request.event_id,
            "output_summary": (
                f"{identity.user_id} invoked the demonstrate-tamper demo "
                f"against event_id {request.event_id}."
            ),
            "evidence_ids": [],
            "opa_rule_ids": [],
        },
    )

    result = await demonstrate_tamper(pool, request.event_id)
    return TamperDemoResponse(**result)
