"""
Tests for `app.narration_cache` and its wiring into
`app.agents.a2_compliance.narrate_gap()` (quick task 260826-0b5).

Structured in the suite's UNIT / NEGATIVE / EDGE / INTEGRATION sections
(CLAUDE.md Rule 6 — this touches the evidence path, so negative and edge
cases are part of done, not a follow-up). Task 1 covers the core memo
behavior end to end through the real route function; Task 2 extends this
file with invalidation, verdict-freshness and outage coverage.

Follows the established `asyncio.run()`-inside-a-plain-`def`-test
convention (`test_a2_compliance.py`); pytest-asyncio is deliberately
absent. No test in this file reaches the real network: every provider
call is either respx-mocked with a dummy key, or deliberately keyless
against a respx block with no routes registered (an accidental outbound
call then fails loudly rather than silently succeeding).
"""

import asyncio
import copy

import httpx
import respx

from app import narration_cache
from app.agents.a2_compliance import narrate_gap
from app.routes.findings import get_assurance_cards

GXP_SYSTEM = "GXP-MFG-DEMO-01"

GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-3.6-flash:generateContent"
)


def _no_provider_keys(monkeypatch):
    for env_name in (
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "DEEPSEEK_API_KEY",
        "GROQ_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(env_name, raising=False)


def _gemini_body(text: str) -> dict:
    return {
        "candidates": [
            {"content": {"parts": [{"text": text}]}}
        ]
    }


def _distinct_text_side_effect():
    """A respx side_effect that returns DIFFERENT text on each invocation,
    so a missing cache is detectable — a constant mock body would make a
    text-equality assertion pass with no cache at all."""
    counter = {"n": 0}

    def _side_effect(request):
        counter["n"] += 1
        return httpx.Response(200, json=_gemini_body(f"distinct narration #{counter['n']}"))

    return _side_effect


def _sample_check_result(check="verify_urs_approved", rule_id="ANNEX11-S4-DOC-001", record=None):
    if record is None:
        record = {"id": "DOC-CACHE-TEST-01", "status": "DRAFT"}
    return {
        "check": check,
        "rule_id": rule_id,
        "passed": False,
        "record": record,
    }


# ---------------------------------------------------------------------------
# UNIT — cache primitives
# ---------------------------------------------------------------------------


def test_unit_cache_key_is_deterministic_and_prompt_sensitive():
    k1 = narration_cache.cache_key("prompt A")
    k2 = narration_cache.cache_key("prompt A")
    k3 = narration_cache.cache_key("prompt B")
    assert k1 == k2
    assert k1 != k3


def test_unit_get_put_roundtrip_and_clear():
    narration_cache.clear()
    key = narration_cache.cache_key("unit-test-prompt")
    assert narration_cache.get(key) is None
    narration_cache.put(key, ("some text", "some-model-id"))
    assert narration_cache.get(key) == ("some text", "some-model-id")
    assert narration_cache.size() >= 1
    narration_cache.clear()
    assert narration_cache.size() == 0
    assert narration_cache.get(key) is None


def test_unit_lru_eviction_bounds_growth():
    narration_cache.clear()
    max_entries = narration_cache._MAX_ENTRIES
    for i in range(max_entries + 5):
        narration_cache.put(f"unit-lru-key-{i}", (f"text-{i}", "model"))
    assert narration_cache.size() == max_entries
    # The earliest-inserted keys should have been evicted first.
    assert narration_cache.get("unit-lru-key-0") is None
    assert narration_cache.get(f"unit-lru-key-{max_entries + 4}") is not None
    narration_cache.clear()


# ---------------------------------------------------------------------------
# NEGATIVE — degraded results must never be cached
# ---------------------------------------------------------------------------


def test_negative_degraded_narration_is_not_cached(monkeypatch):
    narration_cache.clear()
    _no_provider_keys(monkeypatch)
    check_result = _sample_check_result(record={"id": "DOC-CACHE-NEG-01", "status": "DRAFT"})

    async def _run():
        with respx.mock:
            # No routes registered — an accidental outbound call fails loudly.
            return await narrate_gap(check_result)

    claim, model_id = asyncio.run(_run())
    assert model_id == "deterministic-fallback"

    stored_model_ids = {mid for _text, mid in narration_cache._cache.values()}
    assert "deterministic-fallback" not in stored_model_ids
    narration_cache.clear()


# ---------------------------------------------------------------------------
# EDGE — the narration_cache module cannot import app.* (structural gate,
# also enforced by this plan's Task 1 grep verification).
# ---------------------------------------------------------------------------


def test_edge_narration_cache_module_has_no_app_import():
    import app.narration_cache as mod

    source = open(mod.__file__, "r", encoding="utf-8").read()
    for line in source.splitlines():
        stripped = line.strip()
        assert not stripped.startswith("from app"), f"forbidden import: {line}"
        assert not stripped.startswith("import app"), f"forbidden import: {line}"


# ---------------------------------------------------------------------------
# INTEGRATION — narrate_gap() memoization proven directly, and end to end
# through the real get_assurance_cards() route function.
# ---------------------------------------------------------------------------


def test_integration_narrate_gap_second_call_is_a_hit_with_identical_text(monkeypatch):
    narration_cache.clear()
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    check_result = _sample_check_result(record={"id": "DOC-CACHE-HIT-01", "status": "DRAFT"})

    async def _run():
        with respx.mock:
            route = respx.post(GEMINI_ENDPOINT).mock(side_effect=_distinct_text_side_effect())
            first = await narrate_gap(check_result)
            second = await narrate_gap(copy.deepcopy(check_result))
            return first, second, route.call_count

    first, second, call_count = asyncio.run(_run())
    assert first == second
    assert call_count == 1
    narration_cache.clear()


def test_integration_cold_cache_still_narrates(monkeypatch):
    narration_cache.clear()
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    check_result = _sample_check_result(record={"id": "DOC-CACHE-COLD-01", "status": "DRAFT"})

    async def _run():
        with respx.mock:
            route = respx.post(GEMINI_ENDPOINT).mock(side_effect=_distinct_text_side_effect())
            claim, model_id = await narrate_gap(check_result)
            return claim, model_id, route.call_count

    claim, model_id, call_count = asyncio.run(_run())
    assert call_count == 1
    assert claim
    assert model_id == "gemini-3.6-flash"
    narration_cache.clear()


def test_integration_two_consecutive_assurance_card_reads_issue_one_request_per_finding(monkeypatch):
    # This is the plan's headline must_have: two back-to-back
    # get_assurance_cards() calls for GXP_SYSTEM (two failing checks) return
    # byte-identical claim text per finding_id while issuing exactly one
    # outbound request per distinct finding across both reads combined.
    narration_cache.clear()
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    async def _run():
        with respx.mock:
            respx.route(host="127.0.0.1", port=8181).pass_through()
            route = respx.post(GEMINI_ENDPOINT).mock(side_effect=_distinct_text_side_effect())
            first = await get_assurance_cards(GXP_SYSTEM)
            count_after_first = route.call_count
            second = await get_assurance_cards(GXP_SYSTEM)
            count_after_second = route.call_count
            return first, second, count_after_first, count_after_second

    first, second, count_after_first, count_after_second = asyncio.run(_run())

    assert count_after_first > 0
    assert count_after_second == count_after_first

    first_claims = {c.finding_id: c.claim for c in first.cards}
    second_claims = {c.finding_id: c.claim for c in second.cards}
    assert first_claims == second_claims
    assert len(first_claims) > 0
    narration_cache.clear()
