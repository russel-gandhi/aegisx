"""
Tests for `app.circuit_breaker` (SENT-8-02).

Unit tests only, no real time.sleep -- `time.monotonic` is monkeypatched
where a cooldown boundary needs to be crossed, so this file runs in
milliseconds rather than actually waiting out a real cooldown.
"""

import pytest

from app import circuit_breaker
from app.circuit_breaker import (
    CONSECUTIVE_TIMEOUTS_TO_TRIP,
    DEFAULT_COOLDOWN_SECONDS,
    is_available,
    record_rate_limited,
    record_success,
    record_timeout,
    reset_circuit_breakers,
)


def setup_function():
    reset_circuit_breakers()


def test_new_provider_starts_closed_and_available():
    assert is_available("provider-a") is True


def test_rate_limit_trips_breaker_open_immediately():
    assert is_available("provider-b") is True
    record_rate_limited("provider-b", cooldown_seconds=30.0)
    assert is_available("provider-b") is False


def test_single_timeout_does_not_trip_breaker():
    # A lone timeout is not, by itself, proof of an unhealthy provider --
    # CONSECUTIVE_TIMEOUTS_TO_TRIP requires more than one in a row.
    assert CONSECUTIVE_TIMEOUTS_TO_TRIP > 1
    record_timeout("provider-c")
    assert is_available("provider-c") is True


def test_consecutive_timeouts_trip_breaker():
    for _ in range(CONSECUTIVE_TIMEOUTS_TO_TRIP):
        record_timeout("provider-d")
    assert is_available("provider-d") is False


def test_success_resets_consecutive_timeout_counter():
    record_timeout("provider-e")
    record_success("provider-e")
    # A fresh single timeout after a success must not immediately trip --
    # the counter genuinely reset, not just "one away from tripping."
    record_timeout("provider-e")
    assert is_available("provider-e") is True


def test_breaker_transitions_to_half_open_after_cooldown(monkeypatch):
    fake_now = [1000.0]
    monkeypatch.setattr("app.circuit_breaker.time.monotonic", lambda: fake_now[0])

    record_rate_limited("provider-f", cooldown_seconds=10.0)
    assert is_available("provider-f") is False

    fake_now[0] += 10.1  # past the cooldown
    assert is_available("provider-f") is True  # HALF_OPEN probe granted


def test_half_open_grants_exactly_one_concurrent_probe(monkeypatch):
    fake_now = [1000.0]
    monkeypatch.setattr("app.circuit_breaker.time.monotonic", lambda: fake_now[0])

    record_rate_limited("provider-g", cooldown_seconds=5.0)
    fake_now[0] += 5.1

    first_probe = is_available("provider-g")
    second_probe = is_available("provider-g")
    assert first_probe is True
    assert second_probe is False  # a probe is already in flight


def test_half_open_probe_success_closes_breaker(monkeypatch):
    fake_now = [1000.0]
    monkeypatch.setattr("app.circuit_breaker.time.monotonic", lambda: fake_now[0])

    record_rate_limited("provider-h", cooldown_seconds=5.0)
    fake_now[0] += 5.1
    assert is_available("provider-h") is True  # probe granted

    record_success("provider-h")
    # Fully closed now -- a second call in the same instant must also be
    # available, not still gated as a single-probe HALF_OPEN.
    assert is_available("provider-h") is True
    assert is_available("provider-h") is True


def test_half_open_probe_failure_reopens_with_fresh_cooldown(monkeypatch):
    fake_now = [1000.0]
    monkeypatch.setattr("app.circuit_breaker.time.monotonic", lambda: fake_now[0])

    record_rate_limited("provider-i", cooldown_seconds=5.0)
    fake_now[0] += 5.1
    assert is_available("provider-i") is True  # probe granted

    record_rate_limited("provider-i", cooldown_seconds=5.0)  # probe itself 429'd
    assert is_available("provider-i") is False

    fake_now[0] += 5.1
    assert is_available("provider-i") is True  # allowed to probe again


def test_rate_limited_with_no_cooldown_uses_default(monkeypatch):
    fake_now = [1000.0]
    monkeypatch.setattr("app.circuit_breaker.time.monotonic", lambda: fake_now[0])

    record_rate_limited("provider-j", cooldown_seconds=None)
    fake_now[0] += DEFAULT_COOLDOWN_SECONDS - 1
    assert is_available("provider-j") is False
    fake_now[0] += 2
    assert is_available("provider-j") is True


def test_providers_are_independent():
    record_rate_limited("provider-k", cooldown_seconds=30.0)
    assert is_available("provider-k") is False
    assert is_available("provider-l") is True


# --- 2026-11-16: a HALF_OPEN probe must always be resolvable ----------------


def _half_open_with_probe_granted(monkeypatch, key):
    """Trip `key`, let its cooldown elapse, and take the single probe."""
    now = [1000.0]
    monkeypatch.setattr(circuit_breaker.time, "monotonic", lambda: now[0])
    circuit_breaker.record_rate_limited(key, 5.0)
    now[0] += 6.0
    assert circuit_breaker.is_available(key) is True
    assert circuit_breaker.is_available(key) is False
    return now


def test_release_probe_lets_the_next_caller_probe(monkeypatch):
    _half_open_with_probe_granted(monkeypatch, "p-release")
    circuit_breaker.release_probe("p-release")
    assert circuit_breaker.is_available("p-release") is True
    # ...and still exactly one at a time.
    assert circuit_breaker.is_available("p-release") is False


def test_release_probe_is_a_noop_when_closed_or_open(monkeypatch):
    circuit_breaker.release_probe("p-never-seen")
    assert circuit_breaker.is_available("p-never-seen") is True

    circuit_breaker.record_rate_limited("p-open", 60.0)
    circuit_breaker.release_probe("p-open")
    assert circuit_breaker.is_available("p-open") is False


def test_record_probe_failure_reopens_a_half_open_breaker(monkeypatch):
    now = _half_open_with_probe_granted(monkeypatch, "p-fail")
    circuit_breaker.record_probe_failure("p-fail")
    assert circuit_breaker.is_available("p-fail") is False
    now[0] += circuit_breaker.DEFAULT_COOLDOWN_SECONDS + 0.1
    assert circuit_breaker.is_available("p-fail") is True


def test_record_probe_failure_never_trips_a_closed_breaker():
    for _ in range(10):
        circuit_breaker.record_probe_failure("p-closed")
    assert circuit_breaker.is_available("p-closed") is True


def test_abandoned_probe_is_reclaimed_after_the_stale_window(monkeypatch):
    """The backstop: even a caller that never resolves its probe cannot
    keep a provider skipped forever."""
    now = _half_open_with_probe_granted(monkeypatch, "p-stale")
    now[0] += circuit_breaker.HALF_OPEN_PROBE_STALE_SECONDS - 1.0
    assert circuit_breaker.is_available("p-stale") is False
    now[0] += 2.0
    assert circuit_breaker.is_available("p-stale") is True
    assert circuit_breaker.is_available("p-stale") is False
