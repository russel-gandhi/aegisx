"""
Action/approval HTTP routes (Phase 5, plans 05-01, 05-04).

Ticket: SENT-4-03, SENT-4-04, SENT-4-05 | Requirement: REM-01..REM-04,
SAFE-01 | Decisions: D-01, D-02, D-03, D-04

Plan 05-04 adds `POST .../reject`, the mirror of `POST .../approve`: a
human can decline a pending proposal, not only accept it. Both routes
share the exact same guard order (RBAC, pool, row lookup, status guard)
and both reach a terminal status a further approve/reject attempt cannot
override (HTTP 409) -- see `reject_action`'s own docstring for why
`approved_by`/`approved_at` are reused rather than duplicated.

Every route in this module is write-capable and therefore RBAC-gated
through `c2_gateway.check_rbac`. The Phase 4 read routes
(`routes/evidence_graph.py`, `routes/findings.py`) are deliberately left
ungated per D-04 -- this module adds no middleware to them, and this
docstring is the record that the omission is intentional, not an
oversight a later pass should "fix."

No response field on any route below is authored by a model at
response-assembly time. `justification` is the one narrative field this
module ever returns, and it is written once (by `a7_remediation.
synthesize_capa`, at proposal-creation time) and read back verbatim on
every later request -- never re-generated at render time, mirroring
`routes/findings.py`'s own "no LLM prose assembled at read time"
guarantee.

Plan 05-05 (REM-04, UI-02) adds one further effect to `generate_capa`:
once a proposal is durably persisted and audit-logged, its record is
pushed to every connected `/api/copilot/stream/{session_id}` client via
`app.ws.copilot.broadcast_json`. That push is best-effort -- see
`_broadcast_new_proposal`'s own docstring for why a broadcast failure is
logged and swallowed rather than raised.
"""

import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.agents.a2_compliance import A2_CHECKS, build_finding, finding_id_for_check, narrate_gap
from app.agents.a7_remediation import synthesize_capa
from app.agents.c1_verifier import verify_finding
from app.agents.c2_gateway import check_rbac
from app.agents.c3_gateway import (
    QUEUED_CATEGORIES,
    describe_category,
    persist_proposal,
    route_action,
)
from app.audit_trail import log_event
from app.db import acquire_pool_or_none
from app.identity import RequestIdentity, require_identity
from app.routes.evidence_graph import _system_exists
from app.schemas import (
    ActionProposalRecord,
    ActionProposalsResponse,
    GenerateCapaResponse,
)
from app.ws.copilot import broadcast_json

logger = logging.getLogger(__name__)

router = APIRouter()


def _row_to_record(row: Dict[str, Any]) -> ActionProposalRecord:
    payload = row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    return ActionProposalRecord(
        id=row["id"],
        action_type=row["action_type"],
        category=route_action(row["action_type"]),
        target_system=row["target_system"],
        payload=payload,
        status=row["status"],
        justification=row.get("justification"),
        finding_id=row.get("finding_id"),
        model_id=row.get("model_id"),
        created_at=row.get("created_at"),
        approved_by=row.get("approved_by"),
        approved_at=row.get("approved_at"),
        execution_result=row.get("execution_result"),
    )


async def _broadcast_new_proposal(record: ActionProposalRecord) -> None:
    """Push the just-created proposal to every connected copilot-stream
    client (REM-04, UI-02, SENT-4-04).

    Deliberately best-effort: by the time this is called, `persist_proposal`
    has already durably written the row and `log_event` has already
    audit-logged `PROPOSAL_CREATED` -- the proposal is a completed,
    audit-logged fact regardless of whether any client is listening or the
    broadcast itself raises. A dead/misbehaving socket must not roll back
    or fail an otherwise-successful `generate-capa` request, so any
    exception here is logged and swallowed, never re-raised."""
    try:
        await broadcast_json(
            {"event": "action_proposal_created", "proposal": record.model_dump(mode="json")}
        )
    except Exception:
        logger.warning("broadcast_json failed for proposal %s", record.id, exc_info=True)


async def _find_finding_server_side(pool, system_id: str, finding_id: str):
    """Re-derive the finding server-side by iterating A2_CHECKS, exactly as
    `routes/findings.py`'s `get_assurance_cards` does -- the client
    supplies only `finding_id`, never claim text, so the claim rendered in
    a later CAPA proposal can never be client-controlled. Returns `None`
    when no currently-failing check produces a finding with this id (e.g.
    the check has since started passing, or the id is stale/unknown).

    Narrates only the matching check (quick task 260826-p1q): the id
    comparison now runs BEFORE narration, using `finding_id_for_check` to
    derive the candidate id from `check_result` alone -- neither
    `finding_id` form depends on claim text, so the id is knowable before
    any LLM call is made. This makes a `generate-capa` request issue at
    most one narration call instead of one per failing check.

    First-match-wins ordering is preserved deliberately: `verify_urs_approved`
    and `verify_no_stale_documents` both cite `ANNEX11-S4-DOC-001`, so two
    different checks can collide on the same `finding_id` when their record
    ids also match. `A2_CHECKS` is still iterated in its own fixed order and
    the loop still returns on the FIRST match -- same outcome as the old
    narrate-then-compare loop, just without narrating the checks that were
    never going to match. Deliberately NOT `asyncio.gather`: gathering would
    narrate every failing check up front, defeating the entire point of this
    fix.
    """
    for check_fn in A2_CHECKS:
        check_result = await check_fn(pool, system_id)
        if check_result["passed"]:
            continue
        if finding_id_for_check(check_result) != finding_id:
            continue
        claim, model_id = await narrate_gap(check_result)
        return build_finding(check_result, claim, model_id)
    return None


@router.post(
    "/api/systems/{system_id}/findings/{finding_id}/generate-capa",
    response_model=GenerateCapaResponse,
)
async def generate_capa(
    system_id: str,
    finding_id: str,
    identity: RequestIdentity = Depends(require_identity),
):
    """D-03: this route is the only trigger for A7 -- it exists precisely
    because A7 must never fire as a side effect of asking a question. RBAC
    is checked first, before the pool guard, before any model call, and
    before any row is written -- an Auditor (or any role without "A7")
    never reaches Postgres or the LLM router on this path."""
    if not check_rbac(identity.role, "A7"):
        raise HTTPException(
            status_code=403, detail=f"Role {identity.role} may not trigger A7 Remediation"
        )

    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")
    if not await _system_exists(pool, system_id):
        raise HTTPException(status_code=404, detail=f"Unknown system_id: {system_id}")

    finding = await _find_finding_server_side(pool, system_id, finding_id)
    if finding is None:
        raise HTTPException(
            status_code=404,
            detail=f"No currently-failing compliance check produced finding_id {finding_id!r}",
        )
    finding["target_system"] = system_id

    verification_result = await verify_finding(pool, finding)

    proposal, model_id = await synthesize_capa(finding, verification_result)
    if proposal is None:
        return GenerateCapaResponse(
            finding_id=finding_id,
            confidence=verification_result["confidence"],
            proposal=None,
            reason="no C1-verified finding available for remediation",
        )

    category = route_action(proposal["action_type"])
    if category not in QUEUED_CATEGORIES:
        # Bible Section 2 says only "Blocked immediately" for PROHIBITED
        # (and, by extension, any category this route does not queue) --
        # it does not itself state that the blocked attempt is logged.
        # Logging it here is this project's reading of 21 CFR 11.10(e)'s
        # tamper-evident-record intent (05-RESEARCH.md Assumption A5), not
        # a literal Bible instruction. Routed to SENT-7-05. No row is
        # written to `action_proposals` for a category in
        # `BLOCKED_CATEGORIES` -- this branch also covers a category this
        # phase never actually produces (READ/DRAFT are unreachable from
        # A7's own fixed `action_type`; `c3_gateway.py`'s module docstring
        # records why), so it degrades to the same "not queued" audit
        # event rather than assuming every non-queued category is
        # literally PROHIBITED.
        await log_event(
            pool,
            {
                "session_id": None,
                "user_id": identity.user_id,
                "user_role": identity.role,
                "agent_id": "A7",
                "action_type": "PROPOSAL_BLOCKED",
                "target_system_id": system_id,
                "target_record_id": None,
                "output_summary": (
                    f"A7 proposal for {proposal['action_type']!r} blocked: "
                    f"category {category!r} ({describe_category(category)}) "
                    "is not queued for human approval."
                ),
                "evidence_ids": finding["evidence_ids"],
                "opa_rule_ids": verification_result["opa_rule_ids"],
                "model_id": model_id,
                "prompt_version": "A7-v1",
            },
        )
        return GenerateCapaResponse(
            finding_id=finding_id,
            confidence=verification_result["confidence"],
            proposal=None,
            reason=f"proposed action_type resolves to category {category!r}, not queued for approval",
        )

    proposal_id = await persist_proposal(pool, proposal, category, identity, finding_id, model_id)

    await log_event(
        pool,
        {
            "session_id": None,
            "user_id": identity.user_id,
            "user_role": identity.role,
            "agent_id": "A7",
            "action_type": "PROPOSAL_CREATED",
            "target_system_id": system_id,
            "target_record_id": proposal_id,
            "output_summary": (
                f"A7 created proposal {proposal_id} ({proposal['action_type']}, "
                f"category={category}) for finding {finding_id}."
            ),
            "evidence_ids": finding["evidence_ids"],
            "opa_rule_ids": verification_result["opa_rule_ids"],
            "model_id": model_id,
            "prompt_version": "A7-v1",
        },
    )

    row = await pool.fetchrow("SELECT * FROM action_proposals WHERE id = $1", proposal_id)
    record = _row_to_record(dict(row))
    await _broadcast_new_proposal(record)
    return GenerateCapaResponse(
        finding_id=finding_id,
        confidence=verification_result["confidence"],
        proposal=record,
        reason=None,
    )


#  A deliberately generous ceiling (SYSTEM-DESIGN-DIAGNOSIS.md #5), not a
# real pagination contract: this is a human approval queue, and silently
# truncating it would hide a pending GxP-relevant approval from the
# Action/Approval Centre -- a compliance risk, not just a UX one. Rows are
# resolved (approved/rejected) rather than accumulating indefinitely, so a
# genuinely pending queue exceeding this in the current single-operator
# demo scope would itself be the more urgent problem. This exists only as
# a guard against unbounded growth, not an expected limit in normal use.
_ACTIONS_QUERY_CEILING = 500


@router.get("/api/actions", response_model=ActionProposalsResponse)
async def list_actions(identity: RequestIdentity = Depends(require_identity)):
    """No RBAC restriction beyond a recognised role (`require_identity`
    already fails closed on that) -- all three roles may read the queue,
    per Bible Section 2's Auditor scope ("Read-only System and Compliance
    metrics") and REM-03's approval-dialog requirement, which presumes the
    queue itself is visible before anyone can act on it."""
    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")

    rows = await pool.fetch(
        "SELECT * FROM action_proposals ORDER BY created_at ASC, id ASC LIMIT $1",
        _ACTIONS_QUERY_CEILING,
    )
    return ActionProposalsResponse(proposals=[_row_to_record(dict(row)) for row in rows])


@router.post("/api/actions/{proposal_id}/approve", response_model=ActionProposalRecord)
async def approve_action(
    proposal_id: str,
    identity: RequestIdentity = Depends(require_identity),
):
    """D-02: this route is the only way a queued proposal ever leaves
    PENDING_APPROVAL -- there is no auto-approve path, no timeout-based
    execution, and no category that skips the human click. A later
    "convenience" shortcut around this route is a decision reversal, not
    an optimisation, and should be recognised and stopped as such."""
    if not check_rbac(identity.role, "A7"):
        raise HTTPException(
            status_code=403, detail=f"Role {identity.role} may not approve actions"
        )

    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")

    row = await pool.fetchrow("SELECT * FROM action_proposals WHERE id = $1", proposal_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown proposal_id: {proposal_id}")
    row = dict(row)

    if row["status"] != "PENDING_APPROVAL":
        raise HTTPException(
            status_code=409,
            detail=f"Proposal {proposal_id} is {row['status']}, not PENDING_APPROVAL",
        )

    category = route_action(row["action_type"])
    if category == "MOCK_WRITE_LOW_RISK":
        new_status = "EXECUTED"
        execution_result = f"MOCK-TICKET-{proposal_id}"
    else:
        # GXP_RELEVANT_WRITE (the only other QUEUED_CATEGORIES member) --
        # never auto-executed. Reconciled in c3_gateway.py's own docstring.
        new_status = "APPROVED"
        execution_result = (
            "Approved for out-of-band execution; this system performs no "
            "write against a validated GxP record."
        )

    await pool.execute(
        "UPDATE action_proposals SET status = $1, approved_by = $2, "
        "approved_at = now(), execution_result = $3 WHERE id = $4",
        new_status,
        identity.user_id,
        execution_result,
        proposal_id,
    )

    await log_event(
        pool,
        {
            "session_id": None,
            "user_id": identity.user_id,
            "user_role": identity.role,
            "agent_id": "C3",
            "action_type": "ACTION_APPROVED",
            "target_system_id": row["target_system"],
            "target_record_id": proposal_id,
            "approval_id": proposal_id,
            "output_summary": f"{identity.user_id} approved proposal {proposal_id} ({new_status}).",
            "evidence_ids": [],
            "opa_rule_ids": [],
        },
    )

    updated_row = await pool.fetchrow("SELECT * FROM action_proposals WHERE id = $1", proposal_id)
    return _row_to_record(dict(updated_row))


@router.post("/api/actions/{proposal_id}/reject", response_model=ActionProposalRecord)
async def reject_action(
    proposal_id: str,
    identity: RequestIdentity = Depends(require_identity),
):
    """Closes 05-RESEARCH.md Open Question 3: a human can decline a
    pending proposal, not only approve it. Same guard order as
    `approve_action` above (RBAC first, then the pool guard, then the row
    lookup, then the status guard) so the two decision routes can never
    diverge on when they check what -- a reviewer reading one already
    understands the other.

    `approved_by`/`approved_at` are reused here deliberately, not
    duplicated into a second `rejected_by`/`rejected_at` pair: both
    columns record who made the terminal decision and when, regardless
    of which way it went. A schema with one decision-provenance pair
    reads more honestly than one with two columns that are only ever
    half-populated. Routed to SENT-7-05 (naming, not a schema change --
    Option A's migration already added these columns generically enough
    to cover both decisions)."""
    if not check_rbac(identity.role, "A7"):
        raise HTTPException(
            status_code=403, detail=f"Role {identity.role} may not reject actions"
        )

    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")

    row = await pool.fetchrow("SELECT * FROM action_proposals WHERE id = $1", proposal_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown proposal_id: {proposal_id}")
    row = dict(row)

    if row["status"] != "PENDING_APPROVAL":
        raise HTTPException(
            status_code=409,
            detail=f"Proposal {proposal_id} is {row['status']}, not PENDING_APPROVAL",
        )

    # Composed server-side from the identity, never from a client-supplied
    # string -- the same "no free-text field a client controls" discipline
    # `persist_proposal`'s own docstring establishes for `action_type`.
    execution_result = f"Rejected by {identity.role}; this action was not executed."

    await pool.execute(
        "UPDATE action_proposals SET status = $1, approved_by = $2, "
        "approved_at = now(), execution_result = $3 WHERE id = $4",
        "REJECTED",
        identity.user_id,
        execution_result,
        proposal_id,
    )

    await log_event(
        pool,
        {
            "session_id": None,
            "user_id": identity.user_id,
            "user_role": identity.role,
            "agent_id": "C3",
            "action_type": "ACTION_REJECTED",
            "target_system_id": row["target_system"],
            "target_record_id": proposal_id,
            "approval_id": proposal_id,
            "output_summary": f"{identity.user_id} rejected proposal {proposal_id}.",
            "evidence_ids": [],
            "opa_rule_ids": [],
        },
    )

    updated_row = await pool.fetchrow("SELECT * FROM action_proposals WHERE id = $1", proposal_id)
    return _row_to_record(dict(updated_row))
