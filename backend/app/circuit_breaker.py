"""
Per-provider circuit breaker (SENT-8-02), sitting alongside
`app.rate_limiter` in `llm_router.call_llm`'s cascade loop.

## Why this exists

Confirmed live 2026-09-02: when Groq is rate-limited, every concurrent
agent call in the bible's own `[A1...A6 via Send]` fan-out discovers that
independently -- each one pays a full round trip (build request, acquire
rate-limit slot, send, wait for the 429) just to learn what the *first*
failure already proved. A circuit breaker gives the router memory: the
first 429 (or a short run of timeouts) trips the breaker OPEN for that
provider, and every other call in the same burst skips it entirely rather
than re-discovering the same failure.

## State machine

`CLOSED` (normal) -> a trip event -> `OPEN` (skip this provider, no call
attempted) -> cooldown elapses -> `HALF_OPEN` (allow exactly one probe
call through) -> probe succeeds -> `CLOSED`, or probe fails -> `OPEN` again
with a fresh cooldown.

Two distinct trip triggers, both defensible on their own:
- `record_rate_limited()`: a 429 is an *authoritative* signal from the
  provider itself -- trips OPEN immediately, no grace period. The cooldown
  uses the provider's own reported reset time when available (read from
  the same rate-limit headers `app.rate_limiter` already parses), falling
  back to `DEFAULT_COOLDOWN_SECONDS` when the provider doesn't report one.
- `record_timeout()`: a single timeout could be a transient network blip,
  not a real outage -- trips OPEN only after `CONSECUTIVE_TIMEOUTS_TO_TRIP`
  in a row, to avoid over-reacting to one slow response.

## Concurrency note

This backend runs single-worker, matching `app.rate_limiter`'s own
documented scope decision -- an in-process registry is correct here for
the same reason. The `half_open_probe_in_flight` flag prevents two
concurrent callers from both treating a just-expired cooldown as "go
ahead, try it" at the same instant, which would defeat the point of
allowing only one probe.
"""

import logging
import time
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_COOLDOWN_SECONDS = 20.0
CONSECUTIVE_TIMEOUTS_TO_TRIP = 2


class _CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class _Circuit:
    def __init__(self) -> None:
        self.state = _CircuitState.CLOSED
        self.opened_until: Optional[float] = None
        self.consecutive_timeouts = 0
        self.half_open_probe_in_flight = False


_circuits: Dict[str, _Circuit] = {}


def _get(key: str) -> _Circuit:
    circuit = _circuits.get(key)
    if circuit is None:
        circuit = _Circuit()
        _circuits[key] = circuit
    return circuit


def is_available(key: str) -> bool:
    """Returns whether a call to provider `key` should be attempted at
    all. `False` means "skip this provider, cascade onward without
    trying" -- the caller must not call `_send_one` when this is `False`.

    Transitions OPEN -> HALF_OPEN automatically once the cooldown has
    elapsed, and grants exactly one HALF_OPEN caller permission to probe
    (subsequent concurrent callers see `False` until that probe resolves
    via `record_success`/`record_rate_limited`/`record_timeout`)."""
    circuit = _get(key)
    now = time.monotonic()

    if circuit.state == _CircuitState.CLOSED:
        return True

    if circuit.state == _CircuitState.OPEN:
        if circuit.opened_until is not None and now >= circuit.opened_until:
            circuit.state = _CircuitState.HALF_OPEN
            circuit.half_open_probe_in_flight = False
        else:
            return False

    # HALF_OPEN: allow exactly one probe through.
    if circuit.half_open_probe_in_flight:
        return False
    circuit.half_open_probe_in_flight = True
    return True


def record_success(key: str) -> None:
    circuit = _get(key)
    circuit.state = _CircuitState.CLOSED
    circuit.opened_until = None
    circuit.consecutive_timeouts = 0
    circuit.half_open_probe_in_flight = False


def record_rate_limited(key: str, cooldown_seconds: Optional[float]) -> None:
    """A 429 -- authoritative, trips OPEN immediately regardless of prior
    state (including mid-HALF_OPEN-probe: a probe that itself gets
    429'd is exactly as informative as a fresh trip)."""
    circuit = _get(key)
    cooldown = cooldown_seconds if cooldown_seconds and cooldown_seconds > 0 else DEFAULT_COOLDOWN_SECONDS
    circuit.state = _CircuitState.OPEN
    circuit.opened_until = time.monotonic() + cooldown
    circuit.half_open_probe_in_flight = False
    logger.warning(
        "Circuit breaker: %s tripped OPEN by rate limit, cooldown %.1fs.", key, cooldown
    )


def record_timeout(key: str) -> None:
    """A timeout or connection-level failure. Trips OPEN only after
    `CONSECUTIVE_TIMEOUTS_TO_TRIP` in a row -- a lone timeout doesn't by
    itself prove the provider is unhealthy the way a 429 does."""
    circuit = _get(key)
    circuit.consecutive_timeouts += 1
    if circuit.consecutive_timeouts >= CONSECUTIVE_TIMEOUTS_TO_TRIP:
        circuit.state = _CircuitState.OPEN
        circuit.opened_until = time.monotonic() + DEFAULT_COOLDOWN_SECONDS
        circuit.half_open_probe_in_flight = False
        logger.warning(
            "Circuit breaker: %s tripped OPEN after %d consecutive timeouts, cooldown %.1fs.",
            key, circuit.consecutive_timeouts, DEFAULT_COOLDOWN_SECONDS,
        )
    else:
        # A HALF_OPEN probe that times out (rather than 429s) must not
        # leave the breaker stuck thinking a probe is still in flight --
        # the next `is_available()` call needs to be able to try again
        # (or trip fully once the consecutive-timeout threshold is hit).
        circuit.half_open_probe_in_flight = False


def reset_circuit_breakers() -> None:
    """Discard every cached circuit. Used by test isolation and by
    nothing else in production code."""
    global _circuits
    _circuits = {}
