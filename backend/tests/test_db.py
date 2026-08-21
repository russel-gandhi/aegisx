"""
Tests for `app.db` — real asyncpg connectivity against the live Compose
Postgres (Phase 3, 03-01 Task 2).

Follows the established `asyncio.run()`-inside-a-plain-`def`-test
convention from `test_opa_client.py`; pytest-asyncio is deliberately
absent from this codebase.
"""

import asyncio

import asyncpg
import pytest

from app import db


def test_get_pool_returns_singleton():
    async def _run():
        pool1 = await db.get_pool()
        pool2 = await db.get_pool()
        assert pool1 is pool2
        # Close within the same loop that created the pool — closing from
        # a *different* asyncio.run() call fails (the pool's connections
        # are bound to this loop; see conftest.py's db_pool docstring).
        await db.close_pool()
        return pool1

    pool = asyncio.run(_run())
    assert pool is not None


def test_get_pool_reads_seeded_demo_system(db_pool):
    # `db_pool` (session-scoped) only guarantees end-of-session cleanup here
    # — see conftest.py's docstring for why a fixture-created Pool object
    # cannot be handed to a test's own separate `asyncio.run()` call.
    async def _run():
        pool = await db.get_pool()
        row = await pool.fetchrow(
            "SELECT name, readiness_score FROM gxp_systems WHERE id = $1",
            "GXP-MFG-DEMO-01",
        )
        return row

    row = asyncio.run(_run())
    assert row is not None
    assert row["name"] == "NovaSynth Manufacturing Execution Support System"
    assert row["readiness_score"] == 61


def test_acquire_pool_or_none_returns_none_on_unreachable_host(
    monkeypatch, caplog, reset_db_pool
):
    monkeypatch.setattr(
        db, "DATABASE_URL", "postgresql://sentinel:sentinel@127.0.0.1:1/sentinel"
    )

    async def _run():
        return await db.acquire_pool_or_none()

    with caplog.at_level("WARNING", logger="app.db"):
        result = asyncio.run(_run())

    assert result is None
    assert any("Postgres pool unavailable" in r.message for r in caplog.records)


def test_close_pool_is_idempotent():
    async def _run():
        await db.close_pool()
        await db.close_pool()

    asyncio.run(_run())  # must not raise


def test_get_pool_rereads_database_url_after_close(monkeypatch, reset_db_pool):
    async def _run():
        pool = await db.get_pool()
        await db.close_pool()
        # Point at an unreachable host — a fresh get_pool() must attempt to
        # honor the new value rather than silently reuse the closed pool.
        monkeypatch.setattr(
            db,
            "DATABASE_URL",
            "postgresql://sentinel:sentinel@127.0.0.1:1/sentinel",
        )
        try:
            await asyncio.wait_for(db.get_pool(), timeout=3.0)
            raised = False
        except (OSError, asyncpg.PostgresError, asyncio.TimeoutError):
            raised = True
        return pool, raised

    pool, raised = asyncio.run(_run())
    assert pool is not None
    assert raised, "get_pool() should attempt (and fail) against the new DATABASE_URL, not silently reuse the old pool"
