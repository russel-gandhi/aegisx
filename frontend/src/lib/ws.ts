/**
 * WebSocket client for /api/copilot/stream/{session_id} (SENT-1-08, UI-01).
 *
 * Wire contract, matching backend/app/ws/copilot.py exactly:
 *   - On connect: {"event": "connected", "session_id": <string>}
 *   - Per echoed frame: {"event": "echo", "payload": <string>}
 *
 * A discriminated union on `event` rather than a loose record matters
 * because Phase 5 adds a proposal-push frame and Phase 6 adds agent-state
 * frames to this same stream -- a union makes each addition a
 * compile-time prompt to handle the new case; a loose record makes it a
 * runtime surprise.
 */

export interface ConnectedFrame {
  event: 'connected'
  session_id: string
}

export interface EchoFrame {
  event: 'echo'
  payload: string
}

export type CopilotStreamFrame = ConnectedFrame | EchoFrame

export interface CopilotStreamHandlers {
  onFrame: (frame: CopilotStreamFrame) => void
  onError?: (error: unknown) => void
  onOpen?: () => void
  onClose?: () => void
}

export interface CopilotStreamHandle {
  close: () => void
  send: (data: string) => void
}

// Resolved from a Vite env var with a default correct for local
// development. Keeping this out of .env.example is deliberate -- that is
// a cross-cutting file BRANCHING.md SS5 requires be changed in its own
// separate PR, and this plan does not touch it.
const DEFAULT_WS_BASE = 'ws://127.0.0.1:8000'

function resolveWsBase(): string {
  const base = import.meta.env.VITE_COPILOT_WS_BASE
  return typeof base === 'string' && base.length > 0 ? base : DEFAULT_WS_BASE
}

export function connectCopilotStream(
  sessionId: string,
  handlers: CopilotStreamHandlers,
): CopilotStreamHandle {
  const url = `${resolveWsBase()}/api/copilot/stream/${sessionId}`
  const socket = new WebSocket(url)

  socket.onopen = () => {
    handlers.onOpen?.()
  }

  socket.onmessage = (event: MessageEvent) => {
    // A try/catch here is load-bearing: an exception thrown inside
    // `onmessage` does not close the socket but does abort that handler
    // invocation, so an unguarded parse would turn one malformed frame
    // into a connection that looks alive and silently stops delivering.
    try {
      const frame = JSON.parse(event.data as string) as CopilotStreamFrame
      handlers.onFrame(frame)
    } catch (error) {
      handlers.onError?.(error)
    }
  }

  socket.onerror = (event: Event) => {
    handlers.onError?.(event)
  }

  socket.onclose = () => {
    handlers.onClose?.()
  }

  return {
    close: () => socket.close(),
    send: (data: string) => socket.send(data),
  }
}
