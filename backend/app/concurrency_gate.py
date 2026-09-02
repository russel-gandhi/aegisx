"""
Bounded concurrency gate for local providers (SENT-8-03), shared between
`app.llm_router` and `app.retrieval.embeddings` -- both make real HTTP
calls to the same local Ollama process, and neither one's caller knows
about the other's in-flight requests without this.

## Why this exists

Confirmed live 2026-09-02: when Groq's circuit breaker (SENT-8-02) trips
for a whole burst of concurrent agent calls at once, every one of them
cascades to `ollama_qwen` in the same instant. An 8GB GPU running a 7B
Q4 model has room for perhaps 1-2 concurrent inferences, not 5 -- without
this gate, all 5 fire simultaneously, each one queues behind Ollama's own
internal serialization, and several of them exceed their own per-hop
timeout before ever getting a turn, propagating as *more* cascade
failures rather than a smooth, bounded queue.

## Design

A plain `asyncio.Semaphore` per gated key, sized to real local capacity
(`OLLAMA_MAX_CONCURRENCY`, tune empirically -- see the ticket for the
tuning evidence this value should carry). Unlike a naive semaphore wait,
a caller that would have to wait longer than `max_wait_seconds` for a
slot raises `GateBusyError` instead of queueing indefinitely -- treated by
`llm_router._classify_failure` as a cascadable failure, so the caller
moves on to the next cascade hop rather than piling up behind an already
saturated local GPU. A second, cheaper check (`_waiting_count` already at
or above capacity) fails fast without even entering the wait, for the
case where the queue is visibly already full.

## Concurrency note

In-process only, matching `app.rate_limiter`/`app.circuit_breaker`'s own
documented single-worker scope decision.
"""

import asyncio
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Tuning evidence (SENT-8-03/8-05, measured live 2026-09-02): an RTX 4060
# 8GB laptop GPU serving qwen2.5:7b-instruct (Q4_K_M, ~4.75GB resident)
# alongside nomic-embed-text (~325MB resident) was first assumed to have
# room for only ~2 concurrent generations and gated accordingly -- that
# guess was wrong and actively harmful: it gate-rejected 4 of every 6 real
# `[A1...A6 via Send]` fan-out calls even though Ollama itself handles the
# load fine. Measured directly: 6 concurrent calls at REAL narration-prompt
# length (not a trivial "Say OK") completed in ~7.1s total, individual
# calls finishing between 1.5s and 6.9s -- Ollama internally serializes/
# batches to some degree (roughly linear scaling per call, not exponential
# blowup), but every one of the 6 completed well inside a single per-hop
# LLM timeout (10-12s elsewhere in this codebase). 6 (matching the bible's
# own full A1-A6 fan-out width) is therefore the right concurrency ceiling
# for this hardware, not an artificially conservative guess -- re-measure
# with this same method if hardware changes.
OLLAMA_MAX_CONCURRENCY = 6

# A caller that would wait longer than this for a slot is treated as
# "provider busy" and should cascade to the next hop instead of queueing.
# 8.0s sits comfortably above the measured ~7.1s worst case for a full
# 6-way concurrent burst at real narration-prompt length, while staying
# under the per-hop LLM call timeouts elsewhere in this codebase (10-12s)
# so a genuine queue-timeout still leaves the caller time to complete a
# cascade attempt at the next provider within its own outer ceiling.
OLLAMA_MAX_WAIT_SECONDS = 8.0


class GateBusyError(Exception):
    """Raised when a gated key is at capacity and either the queue is
    already visibly full, or waiting for a slot would exceed
    `max_wait_seconds`. Callers should treat this as a cascadable
    failure, not retry against the same gate."""

    def __init__(self, key: str):
        self.key = key
        super().__init__(f"Concurrency gate for {key!r} is busy")


class _Gate:
    def __init__(self, max_concurrency: int):
        self.max_concurrency = max_concurrency
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.waiting_count = 0


_gates: Dict[str, _Gate] = {}
_gates_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_gate(key: str, max_concurrency: int) -> _Gate:
    global _gates, _gates_loop
    current_loop = asyncio.get_running_loop()
    if _gates_loop is not current_loop:
        _gates = {}
        _gates_loop = current_loop
    gate = _gates.get(key)
    if gate is None or gate.max_concurrency != max_concurrency:
        gate = _Gate(max_concurrency)
        _gates[key] = gate
    return gate


class _AcquiredSlot:
    def __init__(self, gate: _Gate):
        self._gate = gate

    async def __aenter__(self) -> "_AcquiredSlot":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._gate.semaphore.release()


def acquire_slot(
    key: str,
    max_concurrency: int = OLLAMA_MAX_CONCURRENCY,
    max_wait_seconds: float = OLLAMA_MAX_WAIT_SECONDS,
) -> "_AcquireContext":
    """Returns an async context manager: `async with acquire_slot("ollama"): ...`.
    Raises `GateBusyError` (without ever entering the `async with` body)
    when the gate is already saturated -- either the queue is visibly full
    (waiting_count >= max_concurrency, meaning every existing slot AND
    every existing waiter are already accounted for) or a slot doesn't
    free up within `max_wait_seconds`."""
    return _AcquireContext(key, max_concurrency, max_wait_seconds)


class _AcquireContext:
    def __init__(self, key: str, max_concurrency: int, max_wait_seconds: float):
        self._key = key
        self._max_concurrency = max_concurrency
        self._max_wait_seconds = max_wait_seconds
        self._gate: Optional[_Gate] = None

    async def __aenter__(self) -> "_AcquireContext":
        gate = _get_gate(self._key, self._max_concurrency)
        if gate.waiting_count >= gate.max_concurrency:
            logger.warning(
                "Concurrency gate %r: queue already at capacity (%d waiting), "
                "failing fast rather than queueing further.",
                self._key, gate.waiting_count,
            )
            raise GateBusyError(self._key)

        gate.waiting_count += 1
        try:
            try:
                await asyncio.wait_for(gate.semaphore.acquire(), timeout=self._max_wait_seconds)
            except asyncio.TimeoutError:
                logger.warning(
                    "Concurrency gate %r: no slot freed within %.1fs, treating as busy.",
                    self._key, self._max_wait_seconds,
                )
                raise GateBusyError(self._key) from None
        finally:
            gate.waiting_count -= 1

        self._gate = gate
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._gate is not None:
            self._gate.semaphore.release()


def reset_concurrency_gates() -> None:
    """Discard every cached gate. Used by test isolation and by nothing
    else in production code."""
    global _gates, _gates_loop
    _gates = {}
    _gates_loop = None
