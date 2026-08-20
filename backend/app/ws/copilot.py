"""
WebSocket route for /api/copilot/stream/{session_id} (SENT-1-08, UI-01).

Source: GxP-Sentinel-Project-Bible-v6.md Section 12 (API table, line 1415)
-- `WS /api/copilot/stream/{session_id}` streams agent execution state.
This module implements only the connection pattern for this phase: accept
a connection and echo whatever text the client sends. Real LangGraph
`astream_events` streaming of agent state is Phase 6 (UI-04) and is
deliberately not imported here -- this module does not import from
`app.graph`, so the transport stays uncoupled from the orchestrator.

Wire contract (the only two frame shapes this route ever sends):
  - On connect: {"event": "connected", "session_id": <str>}
  - Per received text frame: {"event": "echo", "payload": <str>}
Both are always sent as JSON, never bare text -- every later addition to
this stream (Phase 5 pending-proposal pushes, Phase 6 agent-state frames)
is structured, so a client written against a mixed text/JSON stream would
need rewriting the first time that changes.

No CORS middleware is added anywhere in this app because of this route.
Browsers do not apply the CORS preflight model to WebSocket handshakes, so
a page served from port 3000 can open a socket to port 8000 without it,
and this phase's frontend makes no `fetch` call to the backend at all.
Adding permissive CORS "just in case" would widen the surface for no
current requirement (CLAUDE.md Rule 7).

`session_id` is accepted as a path parameter but is NOT validated against
the `sessions` table, and no authentication is performed on this
connection. Both are Phase 5's job (C2 RBAC, SENT-4-01); 02-RESEARCH.md's
Security Domain table records the gap as accepted for this phase, and
SENT-1-08's contract is explicitly "accepts a connection and echoes a test
event".
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/api/copilot/stream/{session_id}")
async def copilot_stream(
    websocket: WebSocket,
    session_id: str,  # noqa: not validated against `sessions` until Phase 5 (C2 RBAC, SENT-4-01)
) -> None:
    await websocket.accept()
    await websocket.send_json({"event": "connected", "session_id": session_id})
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"event": "echo", "payload": data})
    except WebSocketDisconnect:
        # A client closing the socket is ordinary. Letting it surface as an
        # unhandled exception fills the log with noise that hides real
        # failures, so it is caught and the handler returns normally.
        return
