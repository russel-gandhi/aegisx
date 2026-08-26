"""
Tests for `app.prewarm` (quick task 260826-p1q, Task 3).

Follows the suite's established `asyncio.run()`-inside-a-plain-`def`-test
convention (no pytest-asyncio); no asyncio primitive at module scope (the
Windows selector event-loop policy is set at collection time in
`conftest.py`, before any loop exists). Copies the Groq mock body shape
from `test_hero_loop.py`, and registers the mandatory
`respx.route(host="127.0.0.1", port=8181).pass_through()` in any body that
could reach C1's real OPA call.

Covers the plan's three required paths:
  - happy path: Groq key set and mocked -> `narration_cache.size()` ends
    non-zero.
  - keyless negative: every provider key deleted -> returns without
    raising, caches nothing (a degraded result is never cached).
  - Postgres unreachable: returns without raising, warms nothing.
Plus a warm-then-read check proving the pre-warm's prompt keys actually
match `get_assurance_cards`' own (not merely nearly match) -- reading
GXP-MFG-DEMO-01's cards after the pre-warm issues no further outbound
narration request -- and a structural check that the ordinary session-
scoped `client` fixture (which never enters `TestClient` as a context
manager, see `app/main.py`'s lifespan docstring) never triggers the
pre-warm at all.
"""

import asyncio

import httpx
import respx

from app import db, narration_cache
from app.prewarm import DEMO_SYSTEM_IDS, prewarm_narration_cache
from app.routes.findings import get_assurance_cards

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

ALL_PROVIDER_KEYS = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "DEEPSEEK_API_KEY",
    "GROQ_API_KEY",
    "OPENROUTER_API_KEY",
)


def _no_provider_keys(monkeypatch):
    for env_name in ALL_PROVIDER_KEYS:
        monkeypatch.delenv(env_name, raising=False)


def _openai_body(text: str, model: str = "openai/gpt-oss-120b") -> dict:
    return {"choices": [{"message": {"content": text}}], "model": model}


def _distinct_text_side_effect():
    """A respx side_effect returning DIFFERENT text per call, so a
    missing-cache regression is detectable -- a constant body would make a
    text-equality assertion pass even with nothing actually cached."""
    counter = {"n": 0}

    def _side_effect(request):
        counter["n"] += 1
        return httpx.Response(200, json=_openai_body(f"prewarm narration #{counter['n']}"))

    return _side_effect


def test_unit_demo_system_ids_are_the_two_real_seeded_systems():
    assert DEMO_SYSTEM_IDS == ("GXP-MFG-DEMO-01", "BUS-IT-DEMO-02")


def test_happy_path_warms_the_narration_cache(monkeypatch):
    narration_cache.clear()
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")

    async def _run():
        with respx.mock:
            respx.route(host="127.0.0.1", port=8181).pass_through()
            respx.post(GROQ_ENDPOINT).mock(side_effect=_distinct_text_side_effect())
            return await prewarm_narration_cache()

    warmed = asyncio.run(_run())
    assert warmed > 0
    assert narration_cache.size() > 0
    narration_cache.clear()


def test_negative_keyless_run_returns_without_raising_and_caches_nothing(monkeypatch):
    narration_cache.clear()
    _no_provider_keys(monkeypatch)

    async def _run():
        with respx.mock:
            # No provider route registered at all -- an accidental outbound
            # call fails loudly via respx's own "no matching route" error
            # rather than silently succeeding.
            respx.route(host="127.0.0.1", port=8181).pass_through()
            return await prewarm_narration_cache()

    warmed = asyncio.run(_run())  # must not raise
    assert warmed >= 0
    # A degraded narration result is never cached -- see narration_cache's
    # module docstring's "What is never stored" section.
    assert narration_cache.size() == 0
    narration_cache.clear()


def test_edge_postgres_unreachable_returns_without_raising(monkeypatch, reset_db_pool):
    monkeypatch.setattr(
        db, "DATABASE_URL", "postgresql://sentinel:sentinel@127.0.0.1:1/sentinel"
    )
    narration_cache.clear()

    warmed = asyncio.run(prewarm_narration_cache())  # must not raise
    assert warmed == 0
    assert narration_cache.size() == 0
    narration_cache.clear()


def test_integration_warm_then_read_issues_no_further_narration_request(monkeypatch):
    narration_cache.clear()
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")

    async def _run():
        with respx.mock:
            respx.route(host="127.0.0.1", port=8181).pass_through()
            route = respx.post(GROQ_ENDPOINT).mock(side_effect=_distinct_text_side_effect())
            warmed = await prewarm_narration_cache()
            count_after_warm = route.call_count
            response = await get_assurance_cards("GXP-MFG-DEMO-01")
            count_after_read = route.call_count
            return warmed, response, count_after_warm, count_after_read

    warmed, response, count_after_warm, count_after_read = asyncio.run(_run())
    assert warmed > 0
    assert count_after_warm > 0
    # This is the proof the pre-warm's prompt keys actually match
    # get_assurance_cards' own by construction (both go through
    # narrate_gap), not merely nearly match: reading GXP-MFG-DEMO-01 after
    # the pre-warm issues NO further outbound narration request.
    assert count_after_read == count_after_warm
    assert len(response.cards) > 0
    narration_cache.clear()


def test_structural_ordinary_client_fixture_never_triggers_prewarm(client):
    # tests/conftest.py's `client` fixture is a bare TestClient(app), never
    # entered as `with client:` -- Starlette only runs the ASGI lifespan
    # protocol on context-manager entry, so this GET must not have
    # scheduled app.state.prewarm_task at all. This is the structural proof
    # that an ordinary pytest run performs no startup narration.
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert not hasattr(client.app.state, "prewarm_task")
