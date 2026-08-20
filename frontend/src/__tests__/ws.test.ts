import { createElement } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { connectCopilotStream } from '../lib/ws'
import Copilot from '../pages/Copilot'

// This file is .ts, not .tsx (per the plan's declared file_modified path),
// so component trees below are built with createElement rather than JSX.

/**
 * Stub WebSocket, substituted for globalThis.WebSocket so this suite runs
 * with no server and no new dependency. The backend-side proof already
 * lives in backend/tests/test_ws_echo.py and the end-to-end node check in
 * 02-07-PLAN.md's verification section; duplicating a real connection here
 * would make this suite require a running backend.
 */
class StubWebSocket {
  static instances: StubWebSocket[] = []

  url: string
  sentMessages: string[] = []
  closed = false
  onopen: (() => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onclose: (() => void) | null = null

  constructor(url: string) {
    this.url = url
    StubWebSocket.instances.push(this)
  }

  send(data: string) {
    this.sentMessages.push(data)
  }

  close() {
    this.closed = true
    this.onclose?.()
  }

  // Test helper: simulate a frame arriving from the server.
  emitMessage(data: string) {
    this.onmessage?.({ data } as MessageEvent)
  }
}

beforeEach(() => {
  StubWebSocket.instances = []
  vi.stubGlobal('WebSocket', StubWebSocket)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('connectCopilotStream', () => {
  it('builds the URL from the default base and the supplied session id', () => {
    connectCopilotStream('demo-session-1', { onFrame: vi.fn() })
    expect(StubWebSocket.instances).toHaveLength(1)
    expect(StubWebSocket.instances[0].url).toBe(
      'ws://127.0.0.1:8000/api/copilot/stream/demo-session-1',
    )
  })

  it('parses an incoming frame from JSON and dispatches it as a typed object', () => {
    const onFrame = vi.fn()
    connectCopilotStream('demo-session-1', { onFrame })
    const socket = StubWebSocket.instances[0]

    socket.emitMessage(JSON.stringify({ event: 'connected', session_id: 'demo-session-1' }))
    expect(onFrame).toHaveBeenCalledWith({ event: 'connected', session_id: 'demo-session-1' })

    socket.emitMessage(JSON.stringify({ event: 'echo', payload: 'test-event' }))
    expect(onFrame).toHaveBeenCalledWith({ event: 'echo', payload: 'test-event' })
  })

  it('reports a malformed, non-JSON frame through the error path rather than throwing', () => {
    const onFrame = vi.fn()
    const onError = vi.fn()
    connectCopilotStream('demo-session-1', { onFrame, onError })
    const socket = StubWebSocket.instances[0]

    expect(() => socket.emitMessage('not valid json {{{')).not.toThrow()
    expect(onError).toHaveBeenCalledTimes(1)
    expect(onFrame).not.toHaveBeenCalled()
  })

  it('exposes a close function on the returned handle, and calling it closes the socket', () => {
    const handle = connectCopilotStream('demo-session-1', { onFrame: vi.fn() })
    const socket = StubWebSocket.instances[0]

    expect(socket.closed).toBe(false)
    handle.close()
    expect(socket.closed).toBe(true)
  })

  it('is overridable through a Vite environment variable', () => {
    vi.stubEnv('VITE_COPILOT_WS_BASE', 'wss://deployed.example.com')
    connectCopilotStream('demo-session-1', { onFrame: vi.fn() })
    expect(StubWebSocket.instances[0].url).toBe(
      'wss://deployed.example.com/api/copilot/stream/demo-session-1',
    )
  })
})

describe('Copilot page WebSocket lifecycle', () => {
  it('opens exactly one connection on mount and closes it on unmount, and renders received frames', async () => {
    const { unmount } = render(
      createElement(MemoryRouter, { initialEntries: ['/copilot'] }, createElement(Copilot)),
    )

    expect(StubWebSocket.instances).toHaveLength(1)
    const socket = StubWebSocket.instances[0]

    socket.onopen?.()
    socket.emitMessage(JSON.stringify({ event: 'connected', session_id: 'x' }))
    // The page sends 'test-event' back in response to the connected frame.
    expect(socket.sentMessages).toContain('test-event')

    socket.emitMessage(JSON.stringify({ event: 'echo', payload: 'test-event' }))

    await waitFor(() => {
      expect(screen.getByTestId('ws-status')).toHaveTextContent('connected')
    })
    expect(screen.getByTestId('ws-frames').textContent).toContain('echo: test-event')

    expect(socket.closed).toBe(false)
    unmount()
    expect(socket.closed).toBe(true)
    expect(StubWebSocket.instances).toHaveLength(1)
  })
})
