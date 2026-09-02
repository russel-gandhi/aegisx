"""
Proactive, per-provider rate limiting (SYSTEM-DESIGN-DIAGNOSIS.md #3),
extended 2026-09-02 (SENT-8-01) with token-budget awareness.

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

## Why token-budget awareness was added (SENT-8-01)

`rpm_limit` alone was found live (2026-09-02) to be the wrong thing to
throttle on for at least one real provider: Groq's actual binding
constraint on `openai/gpt-oss-120b` is 8,000 **tokens** per minute
(confirmed via the real `x-ratelimit-limit-tokens` response header), not
request count -- the router's `rpm_limit: 300` gave false confidence that
a call was safe to send while Groq's own server rejected it with a 429
anyway. `openai/gpt-oss-120b` is a reasoning model that burns hidden
reasoning tokens on every call regardless of prompt complexity, so a
handful of concurrent agent calls (the bible's own `[A1...A6 via Send]`
fan-out) can exhaust an 8K-token budget in seconds even though the
request count stays low.

This module now tracks two independent budgets per provider: the
existing request-count sliding window (unchanged), and an optional
token-budget sliding window that gets corrected from *live* provider
response headers whenever they're available, falling back to a locally
estimated token-usage history otherwise. A caller that would exceed
either budget waits (or, for callers that pass no token estimate at all --
every pre-existing call site -- the token check is simply inert, exactly
reproducing the old request-count-only behavior).

## Why a sliding window, not a fixed-window counter

A fixed 60-second window that resets on the minute boundary lets a caller
burst up to `2x rpm_limit` requests across the boundary (a full window's
worth just before the reset, another full window's worth just after). A
sliding window -- "how many calls (or tokens) happened in the last 60
seconds, measured continuously" -- doesn't have that edge case and is the
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
from typing import Deque, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_WINDOW_SECONDS = 60.0


class TokenBudgetExceededError(Exception):
    """Raised by `acquire()` when a call would exceed a provider's token
    budget (live-tracked or locally estimated). Deliberately raised
    instead of sleeping the wait out -- see `acquire()`'s own docstring
    comment for why sleeping here reproduces the exact cascade pile-up
    Stage 8 exists to fix. Callers should treat this as a cascadable
    failure, mirroring a real 429."""

    def __init__(self, retry_after_seconds: Optional[float] = None):
        self.retry_after_seconds = retry_after_seconds
        super().__init__("Token budget exceeded")


# A live-reported "remaining tokens" value is trusted for at most this long
# after it was observed, even if the provider's own reset window would run
# longer -- guards against a stale reading (e.g. from a call made just
# before a long idle gap) silently blocking calls forever if a reset
# never actually got re-observed.
_LIVE_TOKEN_DATA_MAX_AGE_SECONDS = 120.0


class _SlidingWindowLimiter:
    """Tracks call timestamps (and, optionally, token usage) in a rolling
    `_WINDOW_SECONDS` window and blocks `acquire()` until the caller is
    back under both `rpm_limit` and (when tracked) the token budget.

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
        # Locally estimated token usage, (timestamp, estimated_tokens)
        # pairs -- the fallback budget source when no live provider data
        # has been observed yet (e.g. the very first call to a provider).
        self._token_events: Deque[Tuple[float, int]] = deque()
        self._lock = asyncio.Lock()
        # Live-corrected state, set by `record_token_usage()` from a real
        # response's rate-limit headers. `None` until the first response
        # is observed, meaning "no live data yet, use the local estimate."
        self._live_remaining_tokens: Optional[int] = None
        self._live_reset_at: Optional[float] = None
        self._live_observed_at: Optional[float] = None

    def _prune(self, now: float) -> None:
        window_start = now - _WINDOW_SECONDS
        while self._timestamps and self._timestamps[0] < window_start:
            self._timestamps.popleft()
        while self._token_events and self._token_events[0][0] < window_start:
            self._token_events.popleft()

    def _live_data_is_fresh(self, now: float) -> bool:
        return (
            self._live_observed_at is not None
            and (now - self._live_observed_at) < _LIVE_TOKEN_DATA_MAX_AGE_SECONDS
        )

    async def acquire(self, estimated_tokens: int = 0, tpm_limit: Optional[int] = None) -> None:
        # Token-budget check happens BEFORE acquiring `self._lock` and,
        # critically, never sleeps: SENT-8-01 originally had this branch
        # `await asyncio.sleep(...)` while holding the lock, which meant
        # every concurrent caller sharing this limiter (e.g. all of the
        # bible's `[A1...A6 via Send]` fan-out routing to the same
        # exhausted Groq budget) queued behind that single sleep in turn --
        # reproducing, inside this rate limiter, the exact pile-up Stage 8
        # exists to eliminate. Confirmed live 2026-09-02: a request that
        # used to fail fast with a logged 429 instead silently consumed
        # the caller's outer wall-clock ceiling waiting on this lock, with
        # no failure ever logged. Raising `TokenBudgetExceededError`
        # immediately lets `call_llm`'s cascade loop move to the next
        # provider (or the circuit breaker skip this one) exactly as it
        # already does for a real 429 -- fast-fail, not queue.
        if estimated_tokens > 0:
            now = time.monotonic()
            if self._live_data_is_fresh(now) and self._live_remaining_tokens is not None:
                if estimated_tokens > self._live_remaining_tokens:
                    wait_seconds = max(0.0, (self._live_reset_at or now) - now)
                    logger.debug(
                        "Rate limiter: live token budget %d remaining, need ~%d; "
                        "rejecting pre-flight (reset in %.2fs) rather than waiting.",
                        self._live_remaining_tokens, estimated_tokens, wait_seconds,
                    )
                    raise TokenBudgetExceededError(wait_seconds if wait_seconds > 0 else None)
            elif tpm_limit is not None:
                async with self._lock:
                    self._prune(now)
                    used = sum(tokens for _, tokens in self._token_events)
                if used + estimated_tokens > tpm_limit:
                    oldest_ts = self._token_events[0][0] if self._token_events else now
                    wait_seconds = max(0.0, _WINDOW_SECONDS - (now - oldest_ts))
                    logger.debug(
                        "Rate limiter: estimated token budget %d/%d used in the last "
                        "%.0fs; rejecting pre-flight (frees up in %.2fs) rather than waiting.",
                        used, tpm_limit, _WINDOW_SECONDS, wait_seconds,
                    )
                    raise TokenBudgetExceededError(wait_seconds if wait_seconds > 0 else None)

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

            self._timestamps.append(now)
            if estimated_tokens > 0:
                self._token_events.append((now, estimated_tokens))
                if self._live_remaining_tokens is not None:
                    self._live_remaining_tokens = max(
                        0, self._live_remaining_tokens - estimated_tokens
                    )

    def record_usage(self, remaining_tokens: Optional[int], reset_seconds: Optional[float]) -> None:
        """Correct this limiter's live token-budget tracking from a real
        response's rate-limit headers. Called on both success and a 429 --
        a 429's own headers are exactly the freshest, most authoritative
        signal available about the provider's real remaining budget."""
        if remaining_tokens is None:
            return
        now = time.monotonic()
        self._live_remaining_tokens = remaining_tokens
        self._live_observed_at = now
        self._live_reset_at = now + reset_seconds if reset_seconds is not None else None


# Registry is loop-scoped exactly like `app.db._pool` / `app.http_client._client`
# / `app.retrieval.qdrant_store._client`: an `asyncio.Lock` is bound to the
# loop that created it, and this codebase's test convention runs every test
# in its own `asyncio.run()` (a fresh loop per test). A loop change discards
# every cached limiter rather than trying to migrate them -- a fresh rate
# history on a fresh loop is the correct behavior, not a compromise.
_limiters: Dict[str, _SlidingWindowLimiter] = {}
_limiters_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_limiter(key: str, rpm_limit: int) -> _SlidingWindowLimiter:
    global _limiters, _limiters_loop
    current_loop = asyncio.get_running_loop()
    if _limiters_loop is not current_loop:
        _limiters = {}
        _limiters_loop = current_loop
    limiter = _limiters.get(key)
    if limiter is None or limiter._rpm_limit != rpm_limit:
        limiter = _SlidingWindowLimiter(rpm_limit)
        _limiters[key] = limiter
    return limiter


async def acquire_rate_limit(
    key: str,
    rpm_limit: int,
    estimated_tokens: int = 0,
    tpm_limit: Optional[int] = None,
) -> None:
    """Block until a call under `key` (a provider's `PROVIDER_CONFIG`/
    `EMBEDDING_PROVIDER_CONFIG` entry name) is within `rpm_limit` calls per
    rolling 60-second window AND, when `estimated_tokens`/`tpm_limit` are
    given, within the tracked token budget -- then record this call and
    return. `estimated_tokens`/`tpm_limit` default to values that make the
    token check a no-op, so every pre-existing call site is unaffected."""
    limiter = _get_limiter(key, rpm_limit)
    await limiter.acquire(estimated_tokens, tpm_limit)


def record_token_usage(
    key: str, remaining_tokens: Optional[int], reset_seconds: Optional[float]
) -> None:
    """Correct `key`'s live token-budget tracking from a real response's
    rate-limit headers. A no-op if `key` has no limiter yet (can't happen
    in practice: this is always called immediately after `acquire_rate_limit`
    for the same key within the same request) or if `remaining_tokens` is
    `None` (the provider didn't report one -- e.g. Ollama, or a provider
    whose response this call site doesn't parse headers for)."""
    limiter = _limiters.get(key)
    if limiter is not None:
        limiter.record_usage(remaining_tokens, reset_seconds)


def reset_rate_limiters() -> None:
    """Discard every cached limiter. Used by test isolation and by
    nothing else in production code."""
    global _limiters, _limiters_loop
    _limiters = {}
    _limiters_loop = None
