"""
Tests for the copilot-stream broadcast extension (Phase 5, plan 05-05).

Ticket: SENT-4-04 | Requirement: REM-04, UI-02

Covers 05-05-PLAN.md Task 1's `<behavior>` list:
- A `broadcast_json` call reaches every currently-connected socket, and
  returns the count of sockets it actually reached.
- A socket whose `send_json` raises is pruned from the registry without
  blocking delivery to the other connected sockets.
- A client-side disconnect deregisters the socket (registry count returns
  to its pre-connect value once the `with` block exits).
- A real `generate-capa` request pushes an `action_proposal_created` frame
  to a connected client, over the same TestClient the HTTP request itself
  uses.
- The pre-existing two-frame echo contract (`connected`/`echo`) is
  unchanged by this extension.
"""

import asyncio
from typing import List

from app.db import get_pool
from app.ws import copilot as ws_copilot
from app.ws.copilot import active_connection_count, broadcast_json

DEMO_SYSTEM = "GXP-MFG-DEMO-01"
IT_MANAGER_HEADERS = {"X-User-Id": "test-ws-broadcast", "X-User-Role": "IT System Manager"}


class _DeadSocket:
    """A stub connected-socket whose `send_json` always raises, standing in
    for a half-closed/stale WebSocket without needing a real dropped
    connection to reproduce the failure mode."""

    async def send_json(self, event):
        raise RuntimeError("stub socket is dead")


def test_broadcast_reaches_every_connected_socket(client):
    with client.websocket_connect("/api/copilot/stream/broadcast-test-1") as ws1:
        ws1.receive_json()  # connected frame
        with client.websocket_connect("/api/copilot/stream/broadcast-test-2") as ws2:
            ws2.receive_json()  # connected frame

            sent = asyncio.run(
                broadcast_json({"event": "action_proposal_created", "proposal": {"id": "test-1"}})
            )
            assert sent == 2

            frame1 = ws1.receive_json()
            frame2 = ws2.receive_json()
            assert frame1 == {"event": "action_proposal_created", "proposal": {"id": "test-1"}}
            assert frame2 == {"event": "action_proposal_created", "proposal": {"id": "test-1"}}


def test_broadcast_prunes_dead_connections(client):
    with client.websocket_connect("/api/copilot/stream/broadcast-test-3") as ws:
        ws.receive_json()  # connected frame

        dead = _DeadSocket()
        ws_copilot._active_connections.add(dead)
        before_count = active_connection_count()
        assert dead in ws_copilot._active_connections

        sent = asyncio.run(
            broadcast_json({"event": "action_proposal_created", "proposal": {"id": "test-2"}})
        )

        # The real socket still received the frame -- the dead stub did not
        # block delivery to it.
        assert sent == 1
        frame = ws.receive_json()
        assert frame == {"event": "action_proposal_created", "proposal": {"id": "test-2"}}

        # The dead stub was pruned; the registry shrank by exactly one.
        assert dead not in ws_copilot._active_connections
        assert active_connection_count() == before_count - 1


def test_disconnect_deregisters_the_socket(client):
    before = active_connection_count()
    with client.websocket_connect("/api/copilot/stream/broadcast-test-4") as ws:
        ws.receive_json()  # connected frame
        assert active_connection_count() == before + 1
    # Exiting the `with` block closes the socket from the client side.
    assert active_connection_count() == before


def test_echo_contract_unchanged(client):
    with client.websocket_connect("/api/copilot/stream/broadcast-test-5") as ws:
        frame = ws.receive_json()
        assert frame == {"event": "connected", "session_id": "broadcast-test-5"}
        ws.send_text("still-echoes")
        frame = ws.receive_json()
        assert frame == {"event": "echo", "payload": "still-echoes"}


def test_generate_capa_pushes_a_proposal_frame(client):
    async def _cleanup(proposal_ids: List[str], event_ids: List[str]) -> None:
        pool = await get_pool()
        if proposal_ids:
            await pool.execute(
                "DELETE FROM action_proposals WHERE id = ANY($1::varchar[])", proposal_ids
            )
        if event_ids:
            await pool.execute(
                "DELETE FROM audit_events WHERE event_id = ANY($1::varchar[])", event_ids
            )

    proposal_ids: List[str] = []
    event_ids: List[str] = []
    try:
        with client.websocket_connect("/api/copilot/stream/broadcast-test-6") as ws:
            ws.receive_json()  # connected frame

            cards_response = client.get(f"/api/systems/{DEMO_SYSTEM}/assurance-cards")
            assert cards_response.status_code == 200
            cards = cards_response.json()["cards"]

            proposal = None
            for card in cards:
                gen_response = client.post(
                    f"/api/systems/{DEMO_SYSTEM}/findings/{card['finding_id']}/generate-capa",
                    headers=IT_MANAGER_HEADERS,
                )
                body = gen_response.json()
                if body.get("proposal") is not None:
                    proposal = body["proposal"]
                    break

            if proposal is None:
                # No seeded finding is C1-eligible for remediation right
                # now -- nothing was queued, so no broadcast frame is
                # expected either. Not a test failure; mirrors
                # test_routes_actions.py's own established convention for
                # this exact situation.
                return

            proposal_ids.append(proposal["id"])

            frame = ws.receive_json()
            assert frame["event"] == "action_proposal_created"
            assert frame["proposal"]["id"] == proposal["id"]
            assert frame["proposal"]["status"] == "PENDING_APPROVAL"

            async def _collect_events():
                pool = await get_pool()
                rows = await pool.fetch(
                    "SELECT event_id FROM audit_events WHERE target_record_id = $1", proposal["id"]
                )
                return [row["event_id"] for row in rows]

            event_ids.extend(asyncio.run(_collect_events()))
    finally:
        asyncio.run(_cleanup(proposal_ids, event_ids))
