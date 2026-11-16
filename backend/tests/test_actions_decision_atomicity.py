"""
2026-11-16 audit regressions for `app.routes.actions`' approve/reject path
(C3, Critical review level).

Before the fix both routes read the proposal, compared `status` in Python,
then issued an unconditional UPDATE and a separate audit write:

- two concurrent decisions on one proposal both succeeded and both wrote an
  audit event (an approval AND a rejection, each recorded as fact);
- a failure between the UPDATE and the audit write left a decided proposal
  with no audit trail entry.

Real Postgres, never mocked, following this suite's convention. Each test
inserts its own `action_proposals` row and removes it and its audit rows
afterwards, so it depends on no seeded finding being C1-eligible.
"""

import asyncio
import json
from typing import List
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.audit_trail import verify_chain
from app.db import get_pool
from app.identity import RequestIdentity
from app.routes import actions as actions_route

APPROVER = RequestIdentity(user_id="t-approver", role="IT System Manager")
REJECTER = RequestIdentity(user_id="t-rejecter", role="IT System Manager")


async def _insert_pending(pool) -> str:
    proposal_id = f"AP-TEST-{uuid4().hex[:16]}"
    await pool.execute(
        "INSERT INTO action_proposals (id, action_type, target_system, payload, status, "
        "justification, finding_id, session_id, model_id) "
        "VALUES ($1, 'CREATE_CAPA_RECORD', 'GXP-MFG-DEMO-01', $2, 'PENDING_APPROVAL', "
        "'test', 'A2-TEST', NULL, 'deterministic-fallback')",
        proposal_id,
        json.dumps({"capa": {}}),
    )
    return proposal_id


async def _events_for(pool, proposal_id: str) -> List[dict]:
    rows = await pool.fetch(
        "SELECT event_id, action_type, user_id FROM audit_events WHERE approval_id = $1 "
        "ORDER BY timestamp_utc",
        proposal_id,
    )
    return [dict(row) for row in rows]


async def _cleanup(pool, proposal_id: str) -> None:
    await pool.execute("DELETE FROM audit_events WHERE approval_id = $1", proposal_id)
    await pool.execute("DELETE FROM action_proposals WHERE id = $1", proposal_id)


def _approve(pool, proposal_id):
    return actions_route._decide_proposal(
        pool, proposal_id, "APPROVED", "approved (test)", APPROVER,
        "ACTION_APPROVED", f"{APPROVER.user_id} approved proposal {proposal_id} (APPROVED).",
    )


def _reject(pool, proposal_id):
    return actions_route._decide_proposal(
        pool, proposal_id, "REJECTED", "rejected (test)", REJECTER,
        "ACTION_REJECTED", f"{REJECTER.user_id} rejected proposal {proposal_id}.",
    )


def test_concurrent_approve_and_reject_yield_exactly_one_decision_and_one_audit_row():
    async def run():
        pool = await get_pool()
        proposal_id = await _insert_pending(pool)
        try:
            results = await asyncio.gather(
                _approve(pool, proposal_id), _reject(pool, proposal_id), return_exceptions=True
            )
            winners = [r for r in results if isinstance(r, dict)]
            losers = [r for r in results if isinstance(r, HTTPException)]
            assert len(winners) == 1, results
            assert len(losers) == 1, results
            assert losers[0].status_code == 409

            final = await pool.fetchrow(
                "SELECT status, approved_by FROM action_proposals WHERE id = $1", proposal_id
            )
            events = await _events_for(pool, proposal_id)
            assert len(events) == 1, events
            # The stored outcome and the single audit row describe the same decision.
            assert final["status"] == winners[0]["status"]
            expected_action = "ACTION_APPROVED" if final["status"] == "APPROVED" else "ACTION_REJECTED"
            assert events[0]["action_type"] == expected_action
            assert events[0]["user_id"] == final["approved_by"]
        finally:
            await _cleanup(pool, proposal_id)

    asyncio.run(run())


def test_many_concurrent_approvals_only_one_wins():
    async def run():
        pool = await get_pool()
        proposal_id = await _insert_pending(pool)
        try:
            results = await asyncio.gather(
                *(_approve(pool, proposal_id) for _ in range(4)), return_exceptions=True
            )
            assert sum(isinstance(r, dict) for r in results) == 1
            assert all(
                isinstance(r, dict) or (isinstance(r, HTTPException) and r.status_code == 409)
                for r in results
            ), results
            assert len(await _events_for(pool, proposal_id)) == 1
        finally:
            await _cleanup(pool, proposal_id)

    asyncio.run(run())


def test_decision_and_audit_event_roll_back_together(monkeypatch):
    """If the audit append fails, the proposal must still be pending: a
    decided proposal with no audit row is exactly the state the single
    transaction exists to make impossible."""

    async def _boom(conn, event_data):
        raise RuntimeError("audit append failed")

    monkeypatch.setattr(actions_route, "log_event_in_transaction", _boom)

    async def run():
        pool = await get_pool()
        proposal_id = await _insert_pending(pool)
        try:
            with pytest.raises(RuntimeError):
                await _approve(pool, proposal_id)
            row = await pool.fetchrow(
                "SELECT status, approved_by, approved_at FROM action_proposals WHERE id = $1",
                proposal_id,
            )
            assert row["status"] == "PENDING_APPROVAL"
            assert row["approved_by"] is None
            assert row["approved_at"] is None
            assert await _events_for(pool, proposal_id) == []
        finally:
            await _cleanup(pool, proposal_id)

    asyncio.run(run())


def test_deciding_an_already_decided_proposal_is_409_and_writes_nothing():
    async def run():
        pool = await get_pool()
        proposal_id = await _insert_pending(pool)
        try:
            await _approve(pool, proposal_id)
            with pytest.raises(HTTPException) as excinfo:
                await _reject(pool, proposal_id)
            assert excinfo.value.status_code == 409
            assert "APPROVED" in excinfo.value.detail
            row = await pool.fetchrow("SELECT status FROM action_proposals WHERE id = $1", proposal_id)
            assert row["status"] == "APPROVED"
            assert [e["action_type"] for e in await _events_for(pool, proposal_id)] == ["ACTION_APPROVED"]
        finally:
            await _cleanup(pool, proposal_id)

    asyncio.run(run())


def test_deciding_an_unknown_proposal_is_404():
    async def run():
        pool = await get_pool()
        with pytest.raises(HTTPException) as excinfo:
            await _approve(pool, "AP-DOES-NOT-EXIST")
        assert excinfo.value.status_code == 404

    asyncio.run(run())


def test_audit_event_written_inside_the_decision_keeps_the_chain_verifiable():
    """The in-transaction append is the same append `log_event` performs --
    a decision must extend the hash chain exactly as any other event does."""

    async def run():
        pool = await get_pool()
        before = await verify_chain(pool)
        proposal_id = await _insert_pending(pool)
        try:
            await _approve(pool, proposal_id)
            during = await verify_chain(pool)
            assert during["status"] == before["status"]
            if before["status"] == "VERIFIED":
                assert during["events_checked"] == before["events_checked"] + 1
        finally:
            await _cleanup(pool, proposal_id)

    asyncio.run(run())
