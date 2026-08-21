"""
Shared pytest fixtures for the backend test suite.

Ticket: SENT-1-05 | Requirement: ENV-04

These fixtures are deliberately generic so later wave-2 backend plans
reuse rather than redefine them:
- `client` — reused by test_health.py (this plan) and any future route test.
- `opa_base_url` — consumed by plan 02-05's test_opa_client.py.
- `pinned_now_ns` — a fixed reference clock any backend test needing one
  can share with the Rego test suite's own pinned constant.
- `db_pool` (Phase 3, 03-01) — session-scoped, ensures the pool is closed
  at session end. Does NOT hand back a usable `asyncpg.Pool` object: an
  asyncpg pool's connections are bound to the event loop that created
  them, and this suite's convention (`asyncio.run()` inside a plain `def
  test_*`, no pytest-asyncio) gives every test its own fresh, short-lived
  loop. A pool created by this fixture's own setup call would be bound to
  a loop already closed by the time a test's body ran its own
  `asyncio.run()` — confirmed by reproducing the failure live
  (`asyncpg.exceptions.InterfaceError: cannot perform operation: another
  operation is in progress` / `RuntimeError: Event loop is closed`), not
  assumed. Tests that need the pool call `await app.db.get_pool()`
  themselves inside their own `asyncio.run()`; `get_pool()` detects a
  stale/foreign-loop cached pool and transparently opens a fresh one
  rather than reusing a dead connection.
- `reset_db_pool` (Phase 3, 03-01) — function-scoped, closes the pool
  before and after a test so URL-override tests (e.g. an unreachable-host
  case) start clean and do not leak a stale pool into the next test.

Fixtures only — no assertions, no import of modules that do not yet exist.
"""

import asyncio
import os
import sys

import pytest
from fastapi.testclient import TestClient

# Windows-only: pytest's stdout/stderr capture replaces sys.stdout/stderr
# with a non-file-like object, which breaks the default
# WindowsProactorEventLoopPolicy's overlapped-I/O self-pipe and manifests
# as `AttributeError: 'NoneType' object has no attribute 'send'` deep
# inside asyncio's proactor transport during a live asyncpg socket write —
# confirmed by reproducing outside pytest (works) and inside pytest (fails)
# with the default policy, and confirmed fixed by switching to the
# selector-based policy before any event loop is created (Phase 3, 03-01
# Task 2). asyncpg has no Proactor-specific requirement, so the selector
# policy is safe here. This must run at collection time, before any test
# or fixture calls asyncio.run().
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.db import close_pool, get_pool
from app.main import app


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture
def opa_base_url():
    return os.getenv("OPA_URL", "http://127.0.0.1:8181")


@pytest.fixture
def pinned_now_ns():
    # Fixed nanosecond-epoch reference clock, shared with the Rego suite's
    # own pinned "now" so backend and policy tests reason about the same
    # instant when a test needs a stable clock.
    return 1_800_000_000_000_000_000


@pytest.fixture(scope="session")
def db_pool():
    yield None
    asyncio.run(close_pool())


@pytest.fixture
def reset_db_pool():
    asyncio.run(close_pool())
    yield
    asyncio.run(close_pool())
