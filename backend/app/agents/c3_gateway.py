"""
C3 - Action Gateway (Phase 5, plan 05-01).

Ticket: SENT-4-03 | Requirement: REM-02, REM-03 | Source: Bible Section 2,
C3

This module never contains a model call (Bible Section 1.3). Category is
derived here, from `action_type`, and stored nowhere -- `ACTION_CATEGORIES`
is the single source of truth `action_proposals` rows are read through
(`routes/actions.py`'s `GET /api/actions`), and the 05-01-PLAN.md Task 1
schema decision (Option A) deliberately did not add a `category` column,
to avoid a second source of truth that could silently drift from this
allowlist.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, FrozenSet

# Bible Section 2, C3 "Categories", mapped from concrete action_type
# strings this phase's routes/A7 module actually produce and reference.
# "DRAFT_SERVICENOW_TICKET" -> MOCK_WRITE_LOW_RISK is the Bible's own
# literal example for that category (Section 2, C3).
ACTION_CATEGORIES: Dict[str, str] = {
    "READ_SYSTEM_RECORD": "READ",
    "DRAFT_CAPA_NARRATIVE": "DRAFT",
    "DRAFT_SERVICENOW_TICKET": "MOCK_WRITE_LOW_RISK",
    "CREATE_CAPA_RECORD": "GXP_RELEVANT_WRITE",
    "UPDATE_VALIDATION_RECORD": "GXP_RELEVANT_WRITE",
    "DELETE_AUDIT_EVENT": "PROHIBITED",
    "DISABLE_AUDIT_TRAIL": "PROHIBITED",
}

# The two categories Bible Section 2's C3 workflow sends to the human
# approval queue ("Sent to Human Approval Queue" / "Blocked. Requires
# out-of-band execution.").
#
# Reconciling Bible Section 2's two GXP_RELEVANT_WRITE statements: the
# category description says "Blocked. Requires out-of-band execution,"
# while the separate C3 Workflow line says every proposed action is
# "Inserted into action_proposals (Status: PENDING) -> WebSocket push ->
# Human clicks Approve -> Audit logged -> Action executes." Both queued
# categories below are inserted PENDING_APPROVAL; on approval,
# `routes/actions.py`'s approve route lets a MOCK_WRITE_LOW_RISK proposal
# reach EXECUTED via a mock execution, while a GXP_RELEVANT_WRITE proposal
# stops at APPROVED with `execution_result` recording that real execution
# is out of band and this system never mutates a validated GxP record
# itself. Routed to SENT-7-05 for Bible reconciliation.
QUEUED_CATEGORIES: FrozenSet[str] = frozenset({"MOCK_WRITE_LOW_RISK", "GXP_RELEVANT_WRITE"})

# The one category Bible Section 2's C3 workflow blocks immediately, with
# no queue row and no out-of-band path. READ and DRAFT are auto-executing
# per Bible Section 2 and are therefore neither queued nor blocked -- they
# are simply not reachable from anything A7 emits this phase (A7's only
# `action_type`, `CREATE_CAPA_RECORD`, always resolves to
# GXP_RELEVANT_WRITE), which is why this phase's write surface only ever
# sees the queued and blocked sets.
BLOCKED_CATEGORIES: FrozenSet[str] = frozenset({"PROHIBITED"})

# Bible Section 2, C3 "Categories" -- each category's own one-line
# disposition sentence, transcribed verbatim. This is what the approval
# UI displays as the server-trusted explanation of a proposal's category,
# so it must come from the Bible's own text rather than from a
# client-side lookup table (REM-03).
CATEGORY_DISPOSITIONS: Dict[str, str] = {
    "READ": "Automatic execution.",
    "DRAFT": "Saved to local state, automatic execution.",
    "MOCK_WRITE_LOW_RISK": "Sent to Human Approval Queue.",
    "GXP_RELEVANT_WRITE": "Blocked. Requires out-of-band execution.",
    "PROHIBITED": "Blocked immediately.",
}


def describe_category(category: str) -> str:
    """Return Bible Section 2's own one-line disposition sentence for
    `category`. Raises `KeyError` for an unknown category -- there is no
    placeholder string to fall back to, since a category this function
    cannot describe is a category `route_action` should never have
    produced in the first place."""
    return CATEGORY_DISPOSITIONS[category]


def route_action(action_type: str) -> str:
    """An unrecognised `action_type` resolves to PROHIBITED, not READ --
    the fail-closed default, mirroring `c2_gateway.check_rbac`'s own
    fail-closed default for an unrecognised role."""
    return ACTION_CATEGORIES.get(action_type, "PROHIBITED")


async def persist_proposal(
    pool,
    proposal: Dict[str, Any],
    category: str,
    identity,
    finding_id: str,
    model_id: str,
) -> str:
    """Insert a new PENDING_APPROVAL row into `action_proposals`.

    `proposal_id` mirrors `audit_events.event_id`'s own `EVT-{utc
    strftime}` convention (`AP-{utc strftime}`), which also gives the
    approval queue a naturally sortable id even though this plan's Option
    A schema decision also adds a real `created_at` column. Every value is
    bound through a `$N` placeholder -- no identifier is ever interpolated
    from request data (ASVS V5, mirrors `c1_verifier.py`'s established
    no-f-string-SQL discipline).

    `session_id` is stored `NULL` here: unlike `app/ws/copilot.py`'s
    stream route, `POST .../generate-capa` carries no `session_id` path
    parameter or header of its own (05-RESEARCH.md Security Domain V3:
    "no session table wiring this phase"), so there is no real session
    identifier to bind. The column exists for a future session-aware
    caller, not for this route. `identity` is accepted as a parameter for
    symmetry with the route's own signature and to keep this function's
    call site self-documenting about who is creating the proposal, even
    though `persist_proposal` itself does not read a field off it today
    (the caller already writes `identity.user_id`/`identity.role` into the
    `PROPOSAL_CREATED` audit event separately).
    """
    proposal_id = f"AP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
    await pool.execute(
        """
        INSERT INTO action_proposals
        (id, action_type, target_system, payload, status, justification,
         finding_id, session_id, model_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """,
        proposal_id,
        proposal["action_type"],
        proposal["target_system"],
        json.dumps(proposal["payload"]),
        "PENDING_APPROVAL",
        proposal.get("justification"),
        finding_id,
        None,
        model_id,
    )
    return proposal_id
