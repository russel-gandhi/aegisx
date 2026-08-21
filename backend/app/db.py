"""
Async Postgres connectivity for AegisX AI (Phase 3, D-01).

Ticket: SENT-2-01/SENT-2-02/SENT-2-12 substrate | Requirements: ORC-02,
ORC-03, EVID-01
Source: AegisX-AI-Project-Bible-v6.md Section 7.1's `AuditLogger`
example already `import asyncpg` and assumes an `asyncpg.Pool` exists
somewhere in the app — this module is that pool.

No Postgres connectivity existed anywhere in the backend before this
module (03-RESEARCH.md Pitfall 4: `grep -r "asyncpg|DATABASE_URL|db_pool"
backend/` previously returned no matches). A2's three deterministic
verification functions and C1's `db_record` fetch both depend on it.

House style mirrors `backend/app/opa_client.py`: a module-level
env-var-backed constant read at call time (not captured at import, so a
test can `monkeypatch.setattr` it), `logging.getLogger(__name__)` rather
than `print`, and degrade-don't-raise on the caller-facing entry point.

Every SQL statement written anywhere in this phase must use asyncpg's
`$1`-style placeholders exclusively — `system_id` originates from
user-facing input (ASVS V5, SQL injection).
"""

import asyncio
import logging
import os
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)

# Module-level, read once at import via os.getenv — but every caller below
# re-reads this same module attribute (not a captured local/default-arg
# value) at call time, so a test can `monkeypatch.setattr(db, "DATABASE_URL",
# ...)` and have it take effect on the next get_pool() call. Mirrors
# opa_client.OPA_URL's 127.0.0.1-not-localhost rationale: 127.0.0.1
# sidesteps IPv6-first resolution that makes "localhost" intermittently
# slow to connect on Windows.
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://sentinel:sentinel@127.0.0.1:5432/sentinel"
)

_pool: Optional[asyncpg.Pool] = None
_pool_loop: Optional[asyncio.AbstractEventLoop] = None


async def get_pool() -> asyncpg.Pool:
    """Lazily create and return the module-level singleton `asyncpg.Pool`.

    A second call *on the same running event loop* returns the same
    object without opening a second pool. Reads the current value of the
    module-level `DATABASE_URL` on every call (not a value captured at
    import or in a default argument), so tests can override it via
    `monkeypatch.setattr` before the first call.

    An `asyncpg.Pool`'s connections are bound to the event loop that
    created them — they cannot be used from a different loop, even
    sequentially (this codebase's test convention wraps every test in its
    own `asyncio.run()`, which means a fresh loop per test). If the loop
    that owns the cached pool is no longer the currently-running loop (or
    is already closed), the stale reference is discarded — no `await` is
    attempted on it, since awaiting a closed loop's connection object
    itself raises — and a fresh pool is created on the current loop
    instead. This makes `get_pool()` safe to call once per test without
    every test having to know about this asyncpg/event-loop coupling.

    Propagates connection failures to the caller — this is the "raising"
    half of the pair; `acquire_pool_or_none()` below is the
    degrade-don't-raise entry point every agent actually uses.
    """
    global _pool, _pool_loop
    current_loop = asyncio.get_running_loop()
    if _pool is not None and _pool_loop is not current_loop:
        _pool = None
        _pool_loop = None
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=5,
            timeout=5.0,
            command_timeout=10.0,
        )
        _pool_loop = current_loop
    return _pool


async def acquire_pool_or_none() -> Optional[asyncpg.Pool]:
    """The entry point every agent uses: never raises.

    Wraps `get_pool()` and returns `None` on connection failure instead of
    propagating the exception, logging a warning that includes the target
    host and the exception text. An unreachable database this way routes
    each agent to its own Bible-specified degraded-mode fallback instead
    of crashing the graph (Bible Section 2's Degraded-Mode Fallback
    Contract; 03-RESEARCH.md's Degraded-Mode Fallback Contract table).
    """
    try:
        return await get_pool()
    except (OSError, asyncpg.PostgresError, asyncio.TimeoutError) as e:
        logger.warning(
            "Postgres pool unavailable (target=%s): %s. Callers should use "
            "their own degraded-mode fallback.",
            DATABASE_URL,
            e,
        )
        return None


async def close_pool() -> None:
    """Close and clear the singleton pool. Safe to call twice, when no
    pool was ever created, or when the cached pool belongs to a *different*
    (already-closed) event loop than the one this call is running on —
    each case is idempotent/a no-op rather than an error.

    That third case matters on this codebase's test convention: a pool
    opened inside one `asyncio.run()` call and left open past that call's
    return is bound to a now-closed loop by the time a later
    `asyncio.run(close_pool())` (e.g. a session fixture's teardown) runs.
    Awaiting `.close()` on it there raises `RuntimeError: Event loop is
    closed` from deep inside asyncpg's connection teardown — confirmed by
    reproducing it live, not assumed. There is nothing meaningful to await
    in that case (the underlying socket is already gone with its loop), so
    the reference is simply dropped.

    After this call, a subsequent `get_pool()` re-reads the current
    module-level `DATABASE_URL` rather than reusing a stale pool built
    against a previous value — this is what lets a test override the URL,
    close the pool, and open a fresh one against the new target.
    """
    global _pool, _pool_loop
    if _pool is not None:
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        if _pool_loop is current_loop:
            await _pool.close()
        _pool = None
        _pool_loop = None
