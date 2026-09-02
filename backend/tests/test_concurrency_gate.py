"""
Tests for `app.concurrency_gate` (SENT-8-03).
"""

import asyncio

import pytest

from app.concurrency_gate import (
    GateBusyError,
    acquire_slot,
    reset_concurrency_gates,
)


def setup_function():
    reset_concurrency_gates()


def _run(coro):
    return asyncio.run(coro)


def test_single_caller_acquires_and_releases_cleanly():
    async def _run_one():
        async with acquire_slot("gate-a", max_concurrency=2):
            pass

    _run(_run_one())  # must not raise


def test_calls_up_to_max_concurrency_run_without_blocking():
    async def _run_two_concurrently():
        async def _hold():
            async with acquire_slot("gate-b", max_concurrency=2):
                await asyncio.sleep(0.05)

        await asyncio.gather(_hold(), _hold())

    _run(_run_two_concurrently())  # must not raise or deadlock


def test_exceeding_capacity_with_full_queue_fails_fast():
    # max_concurrency=1 means only one slot; a second caller that arrives
    # while the first is still holding it and the queue is already at
    # capacity (waiting_count >= max_concurrency) must fail immediately,
    # not queue.
    async def _scenario():
        async def _hold_forever(started: asyncio.Event, release: asyncio.Event):
            async with acquire_slot("gate-c", max_concurrency=1, max_wait_seconds=5.0):
                started.set()
                await release.wait()

        started = asyncio.Event()
        release = asyncio.Event()
        holder = asyncio.create_task(_hold_forever(started, release))
        await started.wait()

        # First waiter: queue not yet full (waiting_count starts at 0),
        # so it queues rather than failing immediately. Give it a moment
        # to register as waiting.
        async def _second_caller():
            async with acquire_slot("gate-c", max_concurrency=1, max_wait_seconds=5.0):
                pass

        second = asyncio.create_task(_second_caller())
        await asyncio.sleep(0.05)  # let it register as waiting

        # Third caller: queue is now already at capacity (1 waiter for a
        # max_concurrency=1 gate) -- must fail fast, not queue further.
        with pytest.raises(GateBusyError):
            async with acquire_slot("gate-c", max_concurrency=1, max_wait_seconds=5.0):
                pass

        release.set()
        await holder
        await second

    _run(_scenario())


def test_wait_timeout_raises_gate_busy_error():
    async def _scenario():
        async def _hold(release: asyncio.Event):
            async with acquire_slot("gate-d", max_concurrency=1, max_wait_seconds=5.0):
                await release.wait()

        release = asyncio.Event()
        holder = asyncio.create_task(_hold(release))
        await asyncio.sleep(0.02)  # let the holder actually acquire first

        with pytest.raises(GateBusyError):
            async with acquire_slot("gate-d", max_concurrency=1, max_wait_seconds=0.05):
                pass

        release.set()
        await holder

    _run(_scenario())


def test_slot_is_released_after_context_exits_even_on_exception():
    async def _scenario():
        with pytest.raises(ValueError):
            async with acquire_slot("gate-e", max_concurrency=1):
                raise ValueError("boom")

        # The slot must be free again -- a second acquire must succeed
        # immediately, not hang or raise GateBusyError.
        async with acquire_slot("gate-e", max_concurrency=1, max_wait_seconds=0.5):
            pass

    _run(_scenario())


def test_independent_gates_do_not_interfere():
    async def _scenario():
        async def _hold(release: asyncio.Event):
            async with acquire_slot("gate-f", max_concurrency=1):
                await release.wait()

        release = asyncio.Event()
        holder = asyncio.create_task(_hold(release))
        await asyncio.sleep(0.02)

        # A different gate key must be entirely unaffected.
        async with acquire_slot("gate-g", max_concurrency=1, max_wait_seconds=0.5):
            pass

        release.set()
        await holder

    _run(_scenario())
