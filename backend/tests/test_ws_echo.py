"""
Tests for the /api/copilot/stream/{session_id} WebSocket route (SENT-1-08,
UI-01, ENV-04).

Covers the plan's <behavior> list:
- Connecting sends a `connected` frame first, echoing the path's session_id.
- A text frame sent by the client comes back as an `echo` frame.
- Three frames sent in sequence echo back in the same order.
- A different session_id in the path is reflected in the `connected` frame.
- Disconnecting from the client side ends the handler cleanly (no exception
  propagates out of the route -- proven by the context manager exiting
  without TestClient raising).
- /api/health is unaffected by registering this router.
"""


def test_connect_sends_connected_frame_with_session_id(client):
    with client.websocket_connect("/api/copilot/stream/demo-session-1") as ws:
        frame = ws.receive_json()
        assert frame == {"event": "connected", "session_id": "demo-session-1"}


def test_sending_text_produces_echo_frame(client):
    with client.websocket_connect("/api/copilot/stream/demo-session-1") as ws:
        ws.receive_json()  # connected frame
        ws.send_text("test-event")
        frame = ws.receive_json()
        assert frame == {"event": "echo", "payload": "test-event"}


def test_three_frames_echo_back_in_order(client):
    with client.websocket_connect("/api/copilot/stream/demo-session-1") as ws:
        ws.receive_json()  # connected frame
        ws.send_text("one")
        ws.send_text("two")
        ws.send_text("three")
        assert ws.receive_json() == {"event": "echo", "payload": "one"}
        assert ws.receive_json() == {"event": "echo", "payload": "two"}
        assert ws.receive_json() == {"event": "echo", "payload": "three"}


def test_different_session_id_is_reflected_in_connected_frame(client):
    with client.websocket_connect("/api/copilot/stream/another-session") as ws:
        frame = ws.receive_json()
        assert frame == {"event": "connected", "session_id": "another-session"}


def test_client_disconnect_ends_handler_cleanly(client):
    with client.websocket_connect("/api/copilot/stream/demo-session-1") as ws:
        ws.receive_json()  # connected frame
    # Exiting the `with` block closes the socket from the client side.
    # No exception propagating out of this test proves the server-side
    # handler caught WebSocketDisconnect rather than raising.


def test_health_still_returns_200_after_ws_router_registered(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
