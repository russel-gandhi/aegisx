"""
WebSocket route for /api/copilot/stream/{session_id} (SENT-1-08, UI-01,
SENT-4-04/REM-04/UI-02).

Source: AegisX-AI-Project-Bible-v6.md Section 12 (API table, line 1415)
-- `WS /api/copilot/stream/{session_id}` streams agent execution state.
This module implements the connection pattern (echo) plus, as of plan
05-05, the pending-proposal broadcast Bible Section 11.6 and SENT-4-04
require. Real LangGraph `astream_events` streaming of agent state is
Phase 6 (UI-04) and is deliberately not imported here -- this module does
not import from `app.graph`, so the transport stays uncoupled from the
orchestrator.

Wire contract (the only three frame shapes this route ever sends):
  - On connect: {"event": "connected", "session_id": <str>}
  - Per received text frame: {"event": "echo", "payload": <str>}
  - On a new action proposal (any connected client, any session):
    {"event": "action_proposal_created", "proposal": {...}}
All three are always sent as JSON, never bare text -- every later addition
to this stream (Phase 6 agent-state frames) is structured, so a client
written against a mixed text/JSON stream would need rewriting the first
time that changes.

No CORS middleware is added anywhere in this app because of this route.
Browsers do not apply the CORS preflight model to WebSocket handshakes, so
a page served from port 3000 can open a socket to port 8000 without it,
and this phase's frontend makes no `fetch` call to the backend at all.
Adding permissive CORS "just in case" would widen the surface for no
current requirement (CLAUDE.md Rule 7).

`session_id` is accepted as a path parameter but is still NOT validated
against the `sessions` table, and no authentication is performed on this
connection. `broadcast_json` is deliberately session-agnostic: every
connected client receives every proposal frame, regardless of the
`session_id` it connected with. That is correct for this project's
single-operator demo scope (D-01: one fixed-identity operator at a time)
and is the point at which a real multi-tenant deployment would need
per-session filtering -- this docstring is the record of that boundary,
not an oversight a later pass should "fix" without also adding the
filtering.
"""

from typing import Any, Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# Module-level registry of every currently-connected copilot-stream socket,
# across all `session_id`s. Populated/depopulated by `copilot_stream` below;
# read (as a snapshot) by `broadcast_json`. A plain `set` is safe here
# because this app runs single-worker (05-RESEARCH.md Pattern 4: Redis
# pub/sub is not justified at single-worker scale) -- multi-worker
# deployment would need a shared broadcast channel instead of this
# in-process registry.
_active_connections: Set[WebSocket] = set()


def active_connection_count() -> int:
    """Number of currently-registered sockets. Exists so a test can assert
    connect/disconnect/prune behaviour without reaching into the private
    `_active_connections` set directly."""
    return len(_active_connections)


async def broadcast_json(event: Dict[str, Any]) -> int:
    """Send `event` as JSON to every currently-connected socket.

    Iterates a snapshot (`list(_active_connections)`) rather than the live
    set, because a send failure below mutates `_active_connections` during
    the loop (via `dead`/`difference_update`) -- iterating the live set
    while mutating it would raise `RuntimeError: Set changed size during
    iteration`.

    Each socket's `send_json` is wrapped in its own `try`/`except`: a
    single stale or half-closed socket must never block delivery to every
    other connected client. The `except Exception` here is deliberate and
    broad, not a shortcut -- a half-closed socket surfaces as several
    different exception types across ASGI servers/transports (closed
    connection, broken pipe, cancelled task, etc.), and this function's
    job is "deliver to everyone still listening," not "diagnose exactly
    why one socket is gone."

    Returns the number of sockets the frame was actually sent to, so a
    caller (or a test) can distinguish "nobody was listening" (0) from
    "the send itself failed" (a dead socket, pruned, not counted).
    """
    dead: Set[WebSocket] = set()
    sent = 0
    for ws in list(_active_connections):
        try:
            await ws.send_json(event)
            sent += 1
        except Exception:
            dead.add(ws)
    _active_connections.difference_update(dead)
    return sent


@router.websocket("/api/copilot/stream/{session_id}")
async def copilot_stream(
    websocket: WebSocket,
    session_id: str,  # noqa: not validated against `sessions` until a future phase (C2 RBAC now covers HTTP routes only, not this socket)
) -> None:
    await websocket.accept()
    _active_connections.add(websocket)
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
    finally:
        # Runs in addition to the `except WebSocketDisconnect: return`
        # above, not instead of it -- a disconnect, a cancellation, and an
        # unexpected exception must all deregister this socket so
        # `broadcast_json` never tries to send to it again.
        _active_connections.discard(websocket)
