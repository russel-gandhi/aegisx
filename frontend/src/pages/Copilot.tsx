import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useLocation } from 'react-router-dom'
import AgentTopologyCanvas, { type NodeStatusValue } from '../components/AgentTopologyCanvas'
import ChatMessage, { type ChatMessageData } from '../components/ChatMessage'
import { connectCopilotStream } from '../lib/ws'
import { queryCopilot, streamAssuranceCards } from '../lib/api'

// A value generated once per mount is sufficient for this plan's contract
// -- nothing yet correlates a session id with a server-side record. Real
// session issuance is Phase 5's job (C2 RBAC, SENT-4-01).
function generateSessionId(): string {
  return `copilot-${Math.random().toString(36).slice(2, 10)}`
}

// Phase 6 (D-01/D-04): the only two systems seeded for the demo. Task 1's
// hero-query shape requires BOTH a known system id substring AND the words
// "audit" and "ready" (tolerating a hyphen, per the behavior spec) --
// anything else (including a bare system id with no readiness question, or
// a readiness question about an unknown system) falls to the non-hero
// stub/response path.
const KNOWN_SYSTEM_IDS = ['GXP-MFG-DEMO-01', 'BUS-IT-DEMO-02']
const AUDIT_READY_PATTERN = /audit[-\s]+ready/i

export function matchHeroQuery(text: string): string | null {
  if (!AUDIT_READY_PATTERN.test(text)) {
    return null
  }
  const upper = text.toUpperCase()
  const systemId = KNOWN_SYSTEM_IDS.find((id) => upper.includes(id))
  return systemId ?? null
}

// 06-UI-SPEC.md Copywriting Contract, transcribed verbatim.
export const EMPTY_STATE_HEADING = "Ask about a system's audit readiness"
export const EMPTY_STATE_BODY =
  'Try: "Is GXP-MFG-DEMO-01 audit ready?" — Copilot verifies every claim against real database and policy state before showing it to you.'
export const STREAM_FAILURE_COPY =
  'The investigation stopped before finishing — check your connection and ask again.'
// D-04: rendered for a non-hero-query submit that `queryCopilot()` (real,
// `POST /api/copilot/query`, backed by the already-tested, zero-LLM
// `detect_injection()`) reports as NOT blocked -- an honest "not supported
// yet" response, never a fabricated compliance answer. Also the
// network/API-error degrade target (Task 2 <action>): a transport failure
// must never look like a fabricated compliance answer either.
export const UNRECOGNIZED_SHAPE_COPY =
  'I can only answer system-readiness questions right now, e.g. "Is GXP-MFG-DEMO-01 audit ready?" — try rephrasing around a known system id.'

// D-04: rendered when `queryCopilot()` reports `blocked: true` -- `reason`
// is `detect_injection()`'s own real return value, interpolated verbatim,
// never a generic block message (06-UI-SPEC.md Copywriting Contract).
export function injectionDetectedCopy(reason: string): string {
  return `This input was blocked by the C2 Policy & Safety Gateway (deterministic rule match: ${reason}) — not evaluated by any model. This is the same real, zero-LLM check every request passes through.`
}

export default function Copilot() {
  const location = useLocation()
  const [messages, setMessages] = useState<ChatMessageData[]>([])
  // Seam for 06-03's Guided Tour: pre-fills the textarea without
  // auto-submitting, so a later plan can navigate here with
  // `state: { prefillQuery: '...' }` and no further Copilot.tsx change.
  const [inputValue, setInputValue] = useState(
    () => (location.state as { prefillQuery?: string } | null)?.prefillQuery ?? '',
  )
  const [isStreaming, setIsStreaming] = useState(false)
  const [nodeStatus, setNodeStatus] = useState<Record<string, NodeStatusValue>>({})
  const [disconnected, setDisconnected] = useState(false)
  const sessionIdRef = useRef(generateSessionId())
  const controllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    // Kept for `action_proposal_created` frames only (Phase 5, 05-05) --
    // per 06-CONTEXT.md code_context, NOT repurposed for the hero-query
    // response path, which stays SSE (D-01). This page renders nothing
    // from this stream today; the live Approval Centre (pages/Actions.tsx)
    // is where a pushed proposal is actually consumed.
    const handle = connectCopilotStream(sessionIdRef.current, {
      onFrame: () => {
        // Intentional no-op -- see comment above.
      },
    })

    return () => {
      handle.close()
      controllerRef.current?.abort()
    }
  }, [])

  function runHeroQuery(systemId: string) {
    // Pitfall 3: never let two concurrent readers interleave cards into
    // the wrong bubble -- abort any in-flight stream before starting a
    // new one, exactly as FindingInvestigation.tsx's own effect does.
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller

    const assistantId = crypto.randomUUID()
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: 'assistant', kind: 'cards', status: 'investigating', cards: [] },
    ])
    setDisconnected(false)
    setIsStreaming(true)
    setNodeStatus({ A0: 'running', A2: 'running' })

    let sawFirstCard = false

    const failStream = () => {
      setDisconnected(true)
      setIsStreaming(false)
      setMessages((prev) =>
        prev.map((message) =>
          message.id === assistantId
            ? { ...message, kind: 'text', variant: 'error', text: STREAM_FAILURE_COPY }
            : message,
        ),
      )
    }

    streamAssuranceCards(
      systemId,
      {
        onCard: (card) => {
          if (!sawFirstCard) {
            sawFirstCard = true
            setNodeStatus((prev) => ({ ...prev, C1: 'running' }))
          }
          setMessages((prev) =>
            prev.map((message) =>
              message.id === assistantId
                ? { ...message, cards: [...(message.cards ?? []), card] }
                : message,
            ),
          )
        },
        onDone: () => {
          // Single terminal transition, not one per check (D-02).
          setNodeStatus({ A0: 'complete', A2: 'complete', C1: 'complete' })
          setIsStreaming(false)
          setMessages((prev) =>
            prev.map((message) =>
              message.id === assistantId ? { ...message, status: 'done' } : message,
            ),
          )
        },
        onError: () => {
          failStream()
        },
      },
      controller.signal,
    ).catch((error: unknown) => {
      // An aborted fetch (a second submit mid-stream, or this component's
      // unmount) rejects with an AbortError -- expected cancellation, never
      // the error state.
      if (error instanceof DOMException && error.name === 'AbortError') {
        return
      }
      failStream()
    })
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const trimmed = inputValue.trim()
    if (trimmed.length === 0 || isStreaming) {
      return
    }

    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: 'user', kind: 'text', text: trimmed },
    ])
    setInputValue('')

    const systemId = matchHeroQuery(trimmed)
    if (systemId !== null) {
      runHeroQuery(systemId)
      return
    }

    // D-04: fast and synchronous from the UI's perspective -- no
    // "Investigating…" placeholder needed, unlike the hero-query stream.
    queryCopilot(trimmed)
      .then((response) => {
        if (response.blocked) {
          setMessages((prev) => [
            ...prev,
            {
              id: crypto.randomUUID(),
              role: 'assistant',
              kind: 'text',
              variant: 'blocked',
              text: injectionDetectedCopy(response.reason ?? ''),
            },
          ])
          return
        }
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            kind: 'text',
            text: UNRECOGNIZED_SHAPE_COPY,
          },
        ])
      })
      .catch(() => {
        // Never let a transport failure look like a fabricated compliance
        // answer -- degrade to the same honest unrecognized-shape copy.
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            kind: 'text',
            text: UNRECOGNIZED_SHAPE_COPY,
          },
        ])
      })
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-100">Ask GxP Copilot</h1>
      <p className="mt-2 max-w-2xl text-slate-400">
        A natural-language chat interface backed by the C2 → A0 → [A1…A6] → C1 → A7 → C3 agent
        pipeline. The canvas below visualizes live agent execution state as a question moves
        through orchestration, evidence verification, and remediation.
      </p>

      <div className="mt-6">
        <AgentTopologyCanvas nodeStatus={nodeStatus} disconnected={disconnected} />
      </div>

      <div className="mt-6 rounded border border-slate-800 bg-slate-900/50 p-4">
        {messages.length === 0 ? (
          <div data-testid="copilot-empty-state">
            <p className="text-lg font-semibold text-slate-100">{EMPTY_STATE_HEADING}</p>
            <p className="mt-1 text-sm text-slate-400">{EMPTY_STATE_BODY}</p>
          </div>
        ) : (
          <div className="space-y-3" data-testid="copilot-messages">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="mt-4 flex items-end gap-2">
        <textarea
          value={inputValue}
          onChange={(event) => setInputValue(event.target.value)}
          disabled={isStreaming}
          placeholder='Ask e.g. "Is GXP-MFG-DEMO-01 audit ready?"'
          rows={2}
          className="max-h-40 min-h-[3rem] flex-1 overflow-y-auto rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={isStreaming || inputValue.trim().length === 0}
          className="rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isStreaming ? 'Investigating…' : 'Ask Copilot'}
        </button>
      </form>
    </div>
  )
}
