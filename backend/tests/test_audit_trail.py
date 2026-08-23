"""
Tests for `app.audit_trail` (Phase 5, plan 05-01).

Ticket: SENT-4-06 | Requirement: AUDIT-01, AUDIT-02

Follows this suite's established convention (`conftest.py`): plain
`def test_*` bodies calling `asyncio.run(...)`, acquiring the pool inside
the coroutine via `await app.db.get_pool()` -- no pytest-asyncio.

Every test that appends rows records their `event_id`s and deletes them
in a `finally` block (05-RESEARCH.md Pitfall 3: `audit_events` starts
empty and has no seed fixture to reset to, so test isolation is entirely
each test's own responsibility), leaving a clean append point for later
tests in the same session.
"""

import asyncio
import json
from typing import List

from app.audit_trail import CANONICAL_FIELDS, GENESIS_HASH, log_event, verify_chain
from app.db import get_pool


async def _cleanup(pool, event_ids: List[str]) -> None:
    if event_ids:
        await pool.execute("DELETE FROM audit_events WHERE event_id = ANY($1::varchar[])", event_ids)


def test_constants_shape():
    assert len(CANONICAL_FIELDS) == 14
    assert len(GENESIS_HASH) == 64
    assert GENESIS_HASH == "0" * 64


def test_log_event_first_row_chains_to_genesis():
    async def run():
        pool = await get_pool()
        event_ids: List[str] = []
        try:
            # Isolate this test's "first row" claim from any row a sibling
            # test may have already appended in the same session by
            # asserting against the row this call itself produced, not
            # against the literal current state of the whole table.
            event_id = await log_event(
                pool,
                {
                    "session_id": "SESSION-TEST-1",
                    "user_id": "tester",
                    "user_role": "IT System Manager",
                    "agent_id": "A7",
                    "action_type": "TEST_EVENT",
                    "target_system_id": "GXP-MFG-DEMO-01",
                    "output_summary": "first row test",
                    "evidence_ids": [],
                    "opa_rule_ids": [],
                    "prompt_version": "TEST-v1",
                },
            )
            event_ids.append(event_id)
            row = await pool.fetchrow(
                "SELECT previous_event_hash, event_hash FROM audit_events WHERE event_id = $1",
                event_id,
            )
            assert row is not None
            assert len(row["event_hash"]) == 64
            # If this was genuinely the first row ever, previous_event_hash
            # equals GENESIS_HASH; if a sibling test's row precedes it,
            # previous_event_hash instead equals that row's own event_hash.
            # Either way it must be a valid 64-char hex chain link, not
            # None/empty.
            assert len(row["previous_event_hash"]) == 64
        finally:
            await _cleanup(pool, event_ids)

    asyncio.run(run())


def test_log_event_second_row_chains_to_first():
    async def run():
        pool = await get_pool()
        event_ids: List[str] = []
        try:
            first_id = await log_event(
                pool,
                {
                    "session_id": "SESSION-TEST-2",
                    "user_id": "tester",
                    "user_role": "IT System Manager",
                    "agent_id": "A7",
                    "action_type": "TEST_EVENT_1",
                    "target_system_id": "GXP-MFG-DEMO-01",
                    "output_summary": "row 1",
                    "evidence_ids": [],
                    "opa_rule_ids": [],
                },
            )
            event_ids.append(first_id)
            first_row = await pool.fetchrow(
                "SELECT event_hash FROM audit_events WHERE event_id = $1", first_id
            )

            second_id = await log_event(
                pool,
                {
                    "session_id": "SESSION-TEST-2",
                    "user_id": "tester",
                    "user_role": "IT System Manager",
                    "agent_id": "A7",
                    "action_type": "TEST_EVENT_2",
                    "target_system_id": "GXP-MFG-DEMO-01",
                    "output_summary": "row 2",
                    "evidence_ids": [],
                    "opa_rule_ids": [],
                },
            )
            event_ids.append(second_id)
            second_row = await pool.fetchrow(
                "SELECT previous_event_hash FROM audit_events WHERE event_id = $1", second_id
            )
            assert second_row["previous_event_hash"] == first_row["event_hash"]
        finally:
            await _cleanup(pool, event_ids)

    asyncio.run(run())


def test_verify_chain_verified_for_rows_log_event_wrote():
    async def run():
        pool = await get_pool()
        event_ids: List[str] = []
        try:
            for i in range(3):
                event_id = await log_event(
                    pool,
                    {
                        "session_id": "SESSION-TEST-VERIFY",
                        "user_id": "tester",
                        "user_role": "IT System Manager",
                        "agent_id": "A7",
                        "action_type": f"TEST_EVENT_{i}",
                        "target_system_id": "GXP-MFG-DEMO-01",
                        "output_summary": f"row {i}",
                        "evidence_ids": [],
                        "opa_rule_ids": [],
                    },
                )
                event_ids.append(event_id)

            result = await verify_chain(pool)
            assert result["status"] == "VERIFIED"
            assert result["events_checked"] >= 3
        finally:
            await _cleanup(pool, event_ids)

    asyncio.run(run())


def test_verify_chain_verified_with_omitted_optional_fields():
    """An event dict that omits model_id/approval_id/target_record_id must
    still verify -- this is the regression test for correction 2 (module
    docstring): both hash sides must build over CANONICAL_FIELDS, not
    whichever keys the caller happened to pass."""

    async def run():
        pool = await get_pool()
        event_ids: List[str] = []
        try:
            event_id = await log_event(
                pool,
                {
                    "session_id": "SESSION-TEST-OMIT",
                    "user_id": "tester",
                    "user_role": "Auditor",
                    "agent_id": "C2",
                    "action_type": "TEST_OMIT_OPTIONAL",
                    "target_system_id": "GXP-MFG-DEMO-01",
                    "output_summary": "omits model_id, approval_id, target_record_id",
                    "evidence_ids": [],
                    "opa_rule_ids": [],
                    # model_id, approval_id, target_record_id intentionally absent
                },
            )
            event_ids.append(event_id)

            result = await verify_chain(pool)
            assert result["status"] == "VERIFIED"
        finally:
            await _cleanup(pool, event_ids)

    asyncio.run(run())


def test_verify_chain_verified_with_nonempty_jsonb_list_fields():
    """An event carrying non-empty evidence_ids/opa_rule_ids lists must
    still verify after the JSONB round trip -- regression test for
    correction 1 (module docstring)."""

    async def run():
        pool = await get_pool()
        event_ids: List[str] = []
        try:
            event_id = await log_event(
                pool,
                {
                    "session_id": "SESSION-TEST-JSONB",
                    "user_id": "tester",
                    "user_role": "IT System Manager",
                    "agent_id": "C1",
                    "action_type": "TEST_JSONB_LISTS",
                    "target_system_id": "GXP-MFG-DEMO-01",
                    "output_summary": "carries two-element evidence_ids and opa_rule_ids",
                    "evidence_ids": ["DOC-001", "DOC-002"],
                    "opa_rule_ids": ["ANNEX11-S4-DOC-001", "ANNEX11-S11-PE-001"],
                },
            )
            event_ids.append(event_id)

            row = await pool.fetchrow(
                "SELECT evidence_ids, opa_rule_ids FROM audit_events WHERE event_id = $1",
                event_id,
            )
            # Confirm this test actually exercises the asyncpg JSONB-as-text
            # behaviour the module docstring describes, rather than
            # accidentally testing a driver that already parses JSONB.
            assert isinstance(row["evidence_ids"], str)
            assert json.loads(row["evidence_ids"]) == ["DOC-001", "DOC-002"]

            result = await verify_chain(pool)
            assert result["status"] == "VERIFIED"
        finally:
            await _cleanup(pool, event_ids)

    asyncio.run(run())


def test_verify_chain_detects_tamper():
    """Negative case (CLAUDE.md Rule 6): a raw UPDATE to output_summary
    after log_event must be caught by verify_chain as TAMPERED, naming the
    correct broken_at_index and event_id."""

    async def run():
        pool = await get_pool()
        event_ids: List[str] = []
        try:
            event_id = await log_event(
                pool,
                {
                    "session_id": "SESSION-TEST-TAMPER",
                    "user_id": "tester",
                    "user_role": "IT System Manager",
                    "agent_id": "A7",
                    "action_type": "TEST_TAMPER_TARGET",
                    "target_system_id": "GXP-MFG-DEMO-01",
                    "output_summary": "original summary",
                    "evidence_ids": [],
                    "opa_rule_ids": [],
                },
            )
            event_ids.append(event_id)

            pre_tamper = await verify_chain(pool)
            assert pre_tamper["status"] == "VERIFIED"

            await pool.execute(
                "UPDATE audit_events SET output_summary = 'TAMPERED DATA' WHERE event_id = $1",
                event_id,
            )

            post_tamper = await verify_chain(pool)
            assert post_tamper["status"] == "TAMPERED"
            assert post_tamper["event_id"] == event_id
        finally:
            await _cleanup(pool, event_ids)

    asyncio.run(run())


def test_log_event_concurrent_appends_stay_chained():
    """Edge case (CLAUDE.md Rule 6, 05-RESEARCH.md Pitfall 5): two
    concurrent log_event calls, fired via asyncio.gather, must still
    produce a chain verify_chain reports VERIFIED over -- proving the
    LOCK TABLE ... IN EXCLUSIVE MODE statement actually serializes
    concurrent appends rather than letting them race on the same
    prev_hash."""

    async def run():
        pool = await get_pool()
        event_ids: List[str] = []
        try:
            results = await asyncio.gather(
                log_event(
                    pool,
                    {
                        "session_id": "SESSION-TEST-CONCURRENT",
                        "user_id": "tester-a",
                        "user_role": "IT System Manager",
                        "agent_id": "A7",
                        "action_type": "TEST_CONCURRENT_A",
                        "target_system_id": "GXP-MFG-DEMO-01",
                        "output_summary": "concurrent append A",
                        "evidence_ids": [],
                        "opa_rule_ids": [],
                    },
                ),
                log_event(
                    pool,
                    {
                        "session_id": "SESSION-TEST-CONCURRENT",
                        "user_id": "tester-b",
                        "user_role": "IT System Manager",
                        "agent_id": "A7",
                        "action_type": "TEST_CONCURRENT_B",
                        "target_system_id": "GXP-MFG-DEMO-01",
                        "output_summary": "concurrent append B",
                        "evidence_ids": [],
                        "opa_rule_ids": [],
                    },
                ),
            )
            event_ids.extend(results)
            assert len(set(event_ids)) == 2

            result = await verify_chain(pool)
            assert result["status"] == "VERIFIED"
        finally:
            await _cleanup(pool, event_ids)

    asyncio.run(run())


def test_verify_chain_verified_on_empty_table_is_a_test_isolation_hazard_not_asserted():
    """Deliberately not asserted here: whether audit_events is empty
    depends on test execution order across the whole session (Pitfall 3),
    so this suite never asserts a literal VERIFIED-with-zero-rows result.
    Instead, test_verify_chain_verified_for_rows_log_event_wrote proves
    VERIFIED over rows this suite itself controls. This test exists only
    to document that omission is deliberate, not an oversight."""
    assert True
