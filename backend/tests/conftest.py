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
- `audit_chain_isolation` (Phase 5, 05-03) — function-scoped, yields a
  list a test appends its own `audit_events.event_id`s to; teardown
  deletes exactly those rows. See the fixture's own docstring for why
  rollback-based isolation is not used here.
- `_clear_narration_cache` (quick task 260826-0b5) — autouse,
  function-scoped, no yield value. `app.narration_cache` introduced
  process-global state that a mocked test's response can leave behind
  for a later test in the same session to hit. Without this fixture,
  `test_a2_compliance.py`'s `test_run_a2_narration_mocked_vs_degraded_same_two_checks_fail`,
  `test_hero_tracer.py`'s `test_degraded_path_no_provider_key_same_finding_and_score`,
  and `test_hero_loop.py`'s `test_hero_keyless_run_falls_back_to_full_agent_set_and_deterministic_fallback`
  — every one of which asserts `model_attribution ==
  "deterministic-fallback"` — could instead be handed an earlier test's
  cached real-model text. Clearing on both sides (before AND after each
  test) is cheaper to reason about than picking one side: it protects a
  test regardless of whether contamination would have arrived from
  before or been left behind for after.

Fixtures only — no assertions, no import of modules that do not yet exist.
"""

import asyncio
import os
import sys
from typing import List

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
from app import narration_cache


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


@pytest.fixture
def audit_chain_isolation():
    """Test isolation for `audit_events` (05-RESEARCH.md Pitfall 3):
    `audit_events` starts empty and has no seed fixture to reset to, so
    isolation is entirely each test's own responsibility. Yields a list
    the test appends its own `event_id`s to; teardown deletes exactly
    those rows so a later test in the same session sees a clean append
    point.

    Rollback-based isolation (a test transaction wrapping the whole test
    body) is deliberately not used: `audit_trail.log_event`'s own `LOCK
    TABLE audit_events IN EXCLUSIVE MODE`-plus-multi-statement transaction
    shape makes nesting a test transaction around it fragile
    (05-RESEARCH.md Pitfall 3). Every test touching `audit_events` must
    use this fixture.
    """
    event_ids: List[str] = []
    yield event_ids

    async def _cleanup():
        if not event_ids:
            return
        pool = await get_pool()
        await pool.execute(
            "DELETE FROM audit_events WHERE event_id = ANY($1::varchar[])", event_ids
        )

    asyncio.run(_cleanup())


@pytest.fixture(autouse=True)
def _clear_narration_cache():
    """Autouse test isolation for `app.narration_cache`'s process-global
    state (quick task 260826-0b5). See this module's docstring's fixture
    list for which specific tests this protects and why. Clears both
    before and after every test in the suite, not just the ones that
    happen to touch narration today — a future test elsewhere in the
    suite gains the same protection automatically."""
    narration_cache.clear()
    yield
    narration_cache.clear()


_LLM_PROVIDER_KEY_ENV_VARS = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "DEEPSEEK_API_KEY",
    "GROQ_API_KEY",
    "OPENROUTER_API_KEY",
)


@pytest.fixture(autouse=True)
def _isolate_llm_provider_keys(monkeypatch):
    """Autouse test isolation for the four LLM provider API keys
    (2026-08-29, following `app.llm_router`'s multi-provider cascade
    change, Deviation 18).

    `app.llm_router` calls `load_dotenv()` at import time, so a real
    `.env` with genuine keys configured (as this environment now has, for
    live manual testing) makes those keys ambient in every test's
    `os.environ` unless a test explicitly clears them — previously
    harmless, because the old single-hop cascade only ever touched
    whichever ONE provider a given task routed to plus `openrouter_fallback`,
    and most tests happened to only `monkeypatch.setenv` those two. The
    multi-hop cascade now walks ALL FOUR providers on failure, so a test
    that mocks only two hosts via `respx.mock` but leaves the other two
    providers' real keys ambient will unexpectedly fire a real, unmocked
    network request — `respx` raises `AllMockedAssertionError` for that,
    a type `call_llm()` does not catch, surfacing as a confusing test
    failure far from its actual cause.

    Deletes all four before every test; a test that wants a specific key
    present still calls `monkeypatch.setenv` itself, same as before — this
    fixture only removes the ambient leak, it does not change any test's
    own explicit key configuration."""
    for env_name in _LLM_PROVIDER_KEY_ENV_VARS:
        monkeypatch.delenv(env_name, raising=False)


@pytest.fixture(autouse=True)
def _zero_llm_cascade_delay(monkeypatch):
    """Autouse test-speed fixture for `app.llm_router.LLM_CASCADE_DELAY_SECONDS`
    (the real `asyncio.sleep` `call_llm()` now performs between failed
    cascade hops, added alongside the multi-hop cascade). Production
    defaults this to 1.0s so a rate-limited provider isn't hammered again
    immediately; a mocked multi-hop cascade test has no such provider to
    protect and would otherwise pay that real wall-clock cost on every
    hop it exercises. Patches the module attribute directly (not the env
    var) since `LLM_CASCADE_DELAY_SECONDS` is read once at import time,
    same as this file's own `_isolate_llm_provider_keys` pattern for
    other `app.llm_router` module state. A test that wants to assert on
    the real delay sets `monkeypatch.setattr(llm_router,
    "LLM_CASCADE_DELAY_SECONDS", <value>)` itself, same override
    mechanism, after this fixture has already run."""
    from app import llm_router
    monkeypatch.setattr(llm_router, "LLM_CASCADE_DELAY_SECONDS", 0.0)


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """Autouse test isolation for `app.rate_limiter`'s process-global
    limiter registry (SYSTEM-DESIGN-DIAGNOSIS.md #3, proactive per-provider
    rate limiting added to `llm_router.call_llm` and
    `retrieval.embeddings`). No single existing test fires anywhere near
    even the lowest configured `rpm_limit` (30) within its own runtime, so
    this is a correctness safeguard against call-count state leaking
    across test boundaries -- not something expected to actually change
    any test's timing, mirroring `_clear_narration_cache`'s own rationale
    for why it resets state even tests that don't obviously touch it."""
    from app.rate_limiter import reset_rate_limiters
    reset_rate_limiters()
    yield
    reset_rate_limiters()
