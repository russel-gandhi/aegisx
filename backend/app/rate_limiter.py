"""
Proactive, per-provider rate limiting (SYSTEM-DESIGN-DIAGNOSIS.md #3).

## Why this exists

Both `llm_router.PROVIDER_CONFIG` and `retrieval.embeddings.
EMBEDDING_PROVIDER_CONFIG` declare an `rpm_limit` per provider -- 60, 30,
300, 1000, 100 requests per minute respectively -- and neither value was
ever read anywhere before this module. Rate-limit handling in both
callers was entirely *reactive*: send the request, wait for a 429, then
back off (embeddings) or cascade to the next provider (the LLM router).
That data was already modeled; it just never got wired to a limiter. This
module is that wiring, not a new design: it enforces the same numbers
that were already declared as the intended ceiling.

## Why a sliding window, not a fixed-window counter

A fixed 60-second window that resets on the minute boundary lets a caller
burst up to `2x rpm_limit` requests across the boundary (a full window's
worth just before the reset, another full window's worth just after). A
sliding window -- "how many calls happened in the last 60 seconds,
measured continuously" -- doesn't have that edge case and is the
standard mechanism for this class of problem.

## Why in-process, not distributed

This backend runs single-worker by explicit design elsewhere in this
codebase (`app/ws/copilot.py`'s own docstring). An in-process limiter is
the correct scope for that: it would need to move to a shared store
(Redis, a database-backed counter) the same day the WS broadcast registry
does, for the same reason, and not before.

## Test isolation

`acquire()` can genuinely `await asyncio.sleep(...)` when a caller is
over budget -- exactly what it's for in production, but not something a
fast unit-test suite should pay for by default. `backend/tests/conftest.py`
resets this module's registry to a fresh, empty state before every test
(mirroring `_zero_llm_cascade_delay`'s treatment of
`LLM_CASCADE_DELAY_SECONDS`), so no rate-limit history leaks across test
boundaries. In practice, no existing test fires anywhere near even the
lowest configured `rpm_limit` (30) within a single test's runtime, so this
is a correctness safeguard for test isolation, not something expected to
actually trigger a sleep during the suite.
"""

import asyncio
import logging
import time
from collections import deque
from typing import Deque, Dict, Optional

logger = logging.getLogger(__name__)

_WINDOW_SECONDS = 60.0


class _SlidingWindowLimiter:
    """Tracks call timestamps in a rolling `_WINDOW_SECONDS` window and
    blocks `acquire()` until the caller is back under `rpm_limit`.

    The lock is held for the full duration of any wait, deliberately: two
    concurrent callers both waking at the same instant and both
    proceeding would let the limiter overshoot its own ceiling. Serializing
    through the wait is the simplest way to guarantee the ceiling actually
    holds under concurrent callers, at the cost of not being fair/FIFO
    beyond whatever order asyncio's lock happens to wake waiters in --
    fairness is not a requirement here, staying under the provider's real
    limit is.
    """

    def __init__(self, rpm_limit: int):
        self._rpm_limit = rpm_limit
        self._timestamps: Deque[float] = deque()
        self._lock = asyncio.Lock()

    def _prune(self, now: float) -> None:
        window_start = now - _WINDOW_SECONDS
        while self._timestamps and self._timestamps[0] < window_start:
            self._timestamps.popleft()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._prune(now)
            if len(self._timestamps) >= self._rpm_limit:
                wait_seconds = _WINDOW_SECONDS - (now - self._timestamps[0])
                if wait_seconds > 0:
                    logger.debug(
                        "Rate limiter: at %d/%d calls in the last %.0fs; waiting %.2fs.",
                        len(self._timestamps), self._rpm_limit, _WINDOW_SECONDS, wait_seconds,
                    )
                    await asyncio.sleep(wait_seconds)
                    now = time.monotonic()
                    self._prune(now)
            self._timestamps.append(time.monotonic())


# Registry is loop-scoped exactly like `app.db._pool` / `app.http_client._client`
# / `app.retrieval.qdrant_store._client`: an `asyncio.Lock` is bound to the
# loop that created it, and this codebase's test convention runs every test
# in its own `asyncio.run()` (a fresh loop per test). A loop change discards
# every cached limiter rather than trying to migrate them -- a fresh rate
# history on a fresh loop is the correct behavior, not a compromise.
_limiters: Dict[str, _SlidingWindowLimiter] = {}
_limiters_loop: Optional[asyncio.AbstractEventLoop] = None


async def acquire_rate_limit(key: str, rpm_limit: int) -> None:
    """Block until a call under `key` (a provider's `PROVIDER_CONFIG`/
    `EMBEDDING_PROVIDER_CONFIG` entry name) is within `rpm_limit` calls per
    rolling 60-second window, then record this call and return."""
    global _limiters, _limiters_loop
    current_loop = asyncio.get_running_loop()
    if _limiters_loop is not current_loop:
        _limiters = {}
        _limiters_loop = current_loop
    limiter = _limiters.get(key)
    if limiter is None or limiter._rpm_limit != rpm_limit:
        limiter = _SlidingWindowLimiter(rpm_limit)
        _limiters[key] = limiter
    await limiter.acquire()


def reset_rate_limiters() -> None:
    """Discard every cached limiter. Used by test isolation and by
    nothing else in production code."""
    global _limiters, _limiters_loop
    _limiters = {}
    _limiters_loop = None
