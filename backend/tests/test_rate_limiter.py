"""
Tests for `app.rate_limiter` (SENT-8-01: token-budget-aware rate limiting).

Covers the pre-existing request-count-only behavior (still exercised
elsewhere via `call_llm`/`call_embedding`'s own tests) plus the new
token-budget tracking this ticket adds: a caller that estimates a token
cost is fast-rejected (never waited-out) against a `tpm_limit`, and a
real response's rate-limit headers correct that tracking live via
`record_token_usage`.

The token-budget check deliberately raises `TokenBudgetExceededError`
rather than sleeping -- an earlier version of this module slept while
holding the limiter's lock, which serialized every concurrent caller
sharing a provider's exhausted budget instead of letting them cascade to
the next provider (found live 2026-09-02, SENT-8-05). These tests pin the
fast-fail contract so that regression can't creep back in unnoticed.

`reset_rate_limiters()` is called at the top of every test rather than
relying only on the autouse `conftest.py` fixture, so this file's
intent is self-evident without cross-referencing conftest.
"""

import asyncio
import time

import pytest

from app.rate_limiter import (
    TokenBudgetExceededError,
    acquire_rate_limit,
    record_token_usage,
    reset_rate_limiters,
)


def _run(coro):
    return asyncio.run(coro)


def setup_function():
    reset_rate_limiters()


def test_request_count_limit_unaffected_by_zero_token_estimate():
    # Every pre-existing call site passes no estimated_tokens at all --
    # confirms the token check stays a true no-op (no wait, no raise) when
    # the caller doesn't opt into it, preserving old behavior exactly.
    async def _run_many():
        start = time.monotonic()
        for _ in range(5):
            await acquire_rate_limit("provider-a", rpm_limit=1000)
        return time.monotonic() - start

    elapsed = _run(_run_many())
    assert elapsed < 1.0


def test_token_budget_rejects_before_exceeding_tpm_limit():
    # No live header data observed yet -- falls back to the local
    # token-event sliding window. A tpm_limit of 100 with two calls
    # estimated at 60 tokens each must fast-reject the second call rather
    # than wait for it.
    async def _run_two():
        await acquire_rate_limit("provider-b", rpm_limit=1000, estimated_tokens=60, tpm_limit=100)
        await acquire_rate_limit("provider-b", rpm_limit=1000, estimated_tokens=60, tpm_limit=100)

    with pytest.raises(TokenBudgetExceededError):
        _run(_run_two())


def test_token_budget_does_not_reject_when_under_limit():
    async def _run_two():
        await acquire_rate_limit("provider-c", rpm_limit=1000, estimated_tokens=10, tpm_limit=100)
        await acquire_rate_limit("provider-c", rpm_limit=1000, estimated_tokens=10, tpm_limit=100)

    _run(_run_two())  # must not raise


def test_token_budget_rejection_carries_a_retry_after_estimate():
    async def _run_two():
        await acquire_rate_limit("provider-b2", rpm_limit=1000, estimated_tokens=60, tpm_limit=100)
        await acquire_rate_limit("provider-b2", rpm_limit=1000, estimated_tokens=60, tpm_limit=100)

    with pytest.raises(TokenBudgetExceededError) as excinfo:
        _run(_run_two())
    assert excinfo.value.retry_after_seconds is not None
    assert excinfo.value.retry_after_seconds > 0


def test_record_token_usage_makes_next_call_fast_reject():
    async def _run_flow():
        # First call establishes the limiter for "provider-d".
        await acquire_rate_limit("provider-d", rpm_limit=1000, estimated_tokens=50)
        # A real response reports only 30 tokens remaining, resetting in 5s
        # -- simulating Groq's own x-ratelimit-remaining-tokens header.
        record_token_usage("provider-d", remaining_tokens=30, reset_seconds=5.0)
        # A second call needing 50 tokens exceeds the live-reported 30
        # remaining -- must fast-reject rather than wait for the reset.
        await acquire_rate_limit("provider-d", rpm_limit=1000, estimated_tokens=50)

    with pytest.raises(TokenBudgetExceededError) as excinfo:
        _run(_run_flow())
    assert excinfo.value.retry_after_seconds == pytest.approx(5.0, abs=0.5)


def test_record_token_usage_is_a_noop_for_unknown_provider():
    # No limiter has been created for "never-called" yet -- must not raise.
    record_token_usage("never-called", remaining_tokens=10, reset_seconds=5.0)


def test_record_token_usage_is_a_noop_when_remaining_is_none():
    # Mirrors a provider (Ollama) that sends no rate-limit headers at all --
    # `_record_token_headers` in llm_router.py always calls this with
    # `remaining=None` in that case, and it must not raise or corrupt state.
    async def _run_flow():
        await acquire_rate_limit("provider-e", rpm_limit=1000, estimated_tokens=10)
        record_token_usage("provider-e", remaining_tokens=None, reset_seconds=None)
        await acquire_rate_limit("provider-e", rpm_limit=1000, estimated_tokens=10)

    _run(_run_flow())  # must not raise


def test_a_successful_acquire_after_a_rejection_still_records_the_call():
    # A rejected call must not corrupt the limiter's own bookkeeping --
    # a later call within budget must still succeed normally.
    async def _run_flow():
        await acquire_rate_limit("provider-f", rpm_limit=1000, estimated_tokens=60, tpm_limit=100)
        try:
            await acquire_rate_limit("provider-f", rpm_limit=1000, estimated_tokens=60, tpm_limit=100)
        except TokenBudgetExceededError:
            pass
        # A small call within the remaining budget must still go through.
        await acquire_rate_limit("provider-f", rpm_limit=1000, estimated_tokens=5, tpm_limit=100)

    _run(_run_flow())  # must not raise on the final acquire
