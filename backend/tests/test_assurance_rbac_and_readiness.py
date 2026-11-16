"""
2026-11-16 audit regressions for `app.routes.findings` / `app.routes.systems`:

- the assurance-card routes require identity and apply
  `c2_gateway.PERMISSION_MATRIX` (an Auditor could previously read every
  A3-A6 finding through them, which the Copilot graph never allows);
- `GET /api/systems/{id}/readiness` counts open findings from the
  deterministic checks alone and issues no LLM request.

Real Postgres and real OPA via the shared `client` fixture, as everywhere
else in this suite. No provider key is set (conftest strips them), so every
narration is the deterministic fallback -- irrelevant here, these tests
assert on which findings exist, never on their wording.
"""

import asyncio
import json

import httpx
import pytest
import respx

from app.agents.c2_gateway import PERMISSION_MATRIX
from app.db import get_pool
from app.routes import findings as findings_route

GXP = "GXP-MFG-DEMO-01"
ITSM = {"X-User-Id": "t-itsm", "X-User-Role": "IT System Manager"}
QA = {"X-User-Id": "t-qa", "X-User-Role": "QA/Compliance"}
AUDITOR = {"X-User-Id": "t-auditor", "X-User-Role": "Auditor"}
CARDS = f"/api/systems/{GXP}/assurance-cards"
STREAM = f"/api/systems/{GXP}/assurance-cards/stream"


def _agent_of(finding_id: str) -> str:
    return finding_id.split("-", 1)[0]


def _stream_cards(client, headers):
    cards = []
    with client.stream("GET", STREAM, headers=headers) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line and line.startswith("data: "):
                frame = json.loads(line[len("data: "):])
                if frame["event"] == "card":
                    cards.append(frame["card"])
    return cards


@pytest.mark.parametrize("path", [CARDS, STREAM])
def test_assurance_cards_without_identity_headers_returns_422(client, path):
    assert client.get(path).status_code == 422


@pytest.mark.parametrize("path", [CARDS, STREAM])
def test_assurance_cards_unrecognised_role_returns_403(client, path):
    resp = client.get(path, headers={"X-User-Id": "x", "X-User-Role": "Superuser"})
    assert resp.status_code == 403


def test_it_manager_and_qa_see_every_agents_findings(client):
    itsm_agents = {_agent_of(c["finding_id"]) for c in client.get(CARDS, headers=ITSM).json()["cards"]}
    qa_agents = {_agent_of(c["finding_id"]) for c in client.get(CARDS, headers=QA).json()["cards"]}
    assert "A2" in itsm_agents
    assert itsm_agents - {"A2"}, "seed must surface at least one A3-A6 finding"
    assert qa_agents == itsm_agents


def test_auditor_sees_only_the_agents_the_permission_matrix_grants(client):
    cards = client.get(CARDS, headers=AUDITOR).json()["cards"]
    agents = {_agent_of(c["finding_id"]) for c in cards}
    assert agents, "an Auditor still sees A2's findings"
    assert agents <= PERMISSION_MATRIX["Auditor"]
    assert agents == {"A2"}


def test_streaming_route_applies_the_same_role_scope(client):
    auditor_ids = sorted(c["finding_id"] for c in _stream_cards(client, AUDITOR))
    blocking_ids = sorted(c["finding_id"] for c in client.get(CARDS, headers=AUDITOR).json()["cards"])
    assert auditor_ids == blocking_ids
    assert all(_agent_of(fid) == "A2" for fid in auditor_ids)

    itsm_ids = {c["finding_id"] for c in _stream_cards(client, ITSM)}
    assert itsm_ids > set(auditor_ids)


def test_permitted_card_sources_fails_closed_for_an_unknown_role():
    include_a2, specialists = findings_route._permitted_card_sources("Superuser")
    assert include_a2 is False
    assert specialists == ()


def test_permitted_card_sources_none_is_the_unrestricted_in_process_caller():
    include_a2, specialists = findings_route._permitted_card_sources(None)
    assert include_a2 is True
    assert specialists == findings_route._SPECIALIST_AGENT_IDS


def test_count_open_findings_matches_the_number_of_cards(client):
    cards = client.get(CARDS, headers=ITSM).json()["cards"]

    async def _count():
        return await findings_route.count_open_findings(await get_pool(), GXP)

    assert asyncio.run(_count()) == len(cards)


def test_readiness_issues_no_llm_request_and_matches_the_card_count(client, monkeypatch):
    """The readiness dial used to run the whole narrating assurance-card
    fan-out to produce one integer. With a live key configured and every
    provider host mocked, it must now touch none of them."""
    cards = client.get(CARDS, headers=ITSM).json()["cards"]
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")

    with respx.mock(assert_all_called=False) as mock:
        mock.route(host="127.0.0.1", port=8181).pass_through()
        groq = mock.post("https://api.groq.com/openai/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})
        )
        ollama = mock.post("http://127.0.0.1:11434/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})
        )
        openrouter = mock.post("https://openrouter.ai/api/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})
        )
        resp = client.get(f"/api/systems/{GXP}/readiness")

    assert resp.status_code == 200
    assert resp.json()["breakdown"]["open_findings"] == len(cards)
    assert groq.call_count == 0
    assert ollama.call_count == 0
    assert openrouter.call_count == 0
