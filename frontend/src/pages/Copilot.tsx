import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useLocation } from 'react-router-dom'
import AgentTopologyCanvas, { type NodeStatusValue } from '../components/AgentTopologyCanvas'
import ChatMessage, { type ChatMessageData } from '../components/ChatMessage'
import { connectCopilotStream } from '../lib/ws'
import { investigateCopilot, streamAssuranceCards } from '../lib/api'

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

// Phase 06.1 (plan 06.1-06, D-07): the system selector offered for a
// free-text (non-hero-query) investigation. Same two demo systems as the
// hero-query path's KNOWN_SYSTEM_IDS, kept as a separate export per the
// plan's own artifact list rather than reusing KNOWN_SYSTEM_IDS directly --
// the hero-query gate and this selector are independent contracts that
// happen to share the same seeded values today.
export const COPILOT_SYSTEM_IDS = ['GXP-MFG-DEMO-01', 'BUS-IT-DEMO-02']

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
// Phase 06.1 (plan 06.1-06): the free-text investigate path's transport-
// failure copy, reusing STREAM_FAILURE_COPY's exact string -- the same
// honest degrade target the hero-query stream already uses, so a failure
// never looks like a fabricated compliance answer regardless of which path
// produced it.
export const INVESTIGATE_FAILURE_COPY = STREAM_FAILURE_COPY

// Legacy export only, retained so nothing that imports it breaks -- no
// longer reachable from handleSubmit as of plan 06.1-06 (D-07). Any free
// text that does not match the hero-query fast path now reaches the real
// graph via investigateCopilot() instead of this canned fallback.
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
  const [selectedSystemId, setSelectedSystemId] = useState(COPILOT_SYSTEM_IDS[0])
  // Phase 06.1 plan 06.1-08 (D-13): tracks which assistant messages have had
  // their pending auto-navigate cancelled -- keyed by message id so
  // cancellation is permanent for that message and never re-arms. Exists
  // because WCAG 2.2.1 (Timing Adjustable) requires a non-essential timing
  // limit to be cancellable; "Stay here" and typing in the composer are the
  // two cancel triggers.
  const [navigationCancelled, setNavigationCancelled] = useState<Record<string, boolean>>({})
  const [nodeStatus, setNodeStatus] = useState<Record<string, NodeStatusValue>>({})
  const [disconnected, setDisconnected] = useState(false)
  const sessionIdRef = useRef(generateSessionId())
  const controllerRef = useRef<AbortController | null>(null)
  const messagesContainerRef = useRef<HTMLDivElement | null>(null)

  // 06-UI-SPEC.md UI Considerations, "overflow" row: the message list
  // scrolls inside a fixed-height panel and auto-scrolls to bottom on
  // every new message (including a card arriving mid-stream) -- never a
  // growing-forever page. Runs after every `messages` change, including
  // in-place mutations to the last message's own `cards`/`text` field.
  useEffect(() => {
    const container = messagesContainerRef.current
    if (container === null) {
      return
    }
    container.scrollTop = container.scrollHeight
  }, [messages])

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

    // D-07: any non-hero-query free text now reaches the real graph via
    // investigateCopilot(), replacing the old canned not-supported-yet
    // fallback. An "Investigating…" placeholder mirrors the hero-query
    // stream's own in-flight treatment (ChatMessage.tsx's `kind:
    // 'investigation'` branch), and input/send stay disabled for the
    // whole request via the same `isStreaming` flag the hero path uses.
    const assistantId = crypto.randomUUID()
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: 'assistant', kind: 'investigation', status: 'investigating' },
    ])
    setIsStreaming(true)

    investigateCopilot(trimmed, selectedSystemId)
      .then((response) => {
        setIsStreaming(false)
        if (response.blocked) {
          // Unchanged from Phase 6: the destructive-styled bubble with
          // C2's own real reason string, now sourced from
          // investigateCopilot's blocked_reason field.
          setMessages((prev) =>
            prev.map((message) =>
              message.id === assistantId
                ? {
                    ...message,
                    kind: 'text',
                    variant: 'blocked',
                    text: injectionDetectedCopy(response.blocked_reason ?? ''),
                  }
                : message,
            ),
          )
          return
        }
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId
              ? { ...message, kind: 'investigation', status: 'done', investigation: response }
              : message,
          ),
        )
      })
      .catch(() => {
        // A transport/5xx failure must never look like a fabricated
        // compliance answer -- degrade to the same honest failure copy
        // the hero-query stream uses.
        setIsStreaming(false)
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId
              ? { ...message, kind: 'text', variant: 'error', text: INVESTIGATE_FAILURE_COPY }
              : message,
          ),
        )
      })
  }

  // Phase 06.1 plan 06.1-08 (D-13): auto-navigation applies only to the
  // newest assistant message -- an older investigation message re-rendered
  // or scrolled back into view arms nothing.
  const latestAssistantId =
    [...messages].reverse().find((message) => message.role === 'assistant')?.id ?? null

  return (
    <div>
      <p className="eyebrow">Ask Copilot</p>
      <h1 className="mt-1 text-[28px] font-bold text-ink">Ask GxP Copilot</h1>
      <p className="mt-2 max-w-2xl text-[13.5px] text-ink-muted">
        Questions are answered from the indexed knowledge base with inspectable evidence -- every
        answer names the source document, section/page, and retrieval method behind it, backed by
        the C2 → A0 → [A1…A6] → C1 → A7 → C3 agent pipeline. The canvas below visualizes live
        agent execution state for a system-readiness question.
      </p>

      <div className="mt-4 flex items-center gap-2">
        <label htmlFor="copilot-system" className="text-sm text-ink-muted">
          System
        </label>
        <select
          id="copilot-system"
          className="input-field"
          value={selectedSystemId}
          onChange={(event) => setSelectedSystemId(event.target.value)}
        >
          {COPILOT_SYSTEM_IDS.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
      </div>

      {/*
        The composer sits immediately below the system selector, above the
        topology canvas -- not below it. React Flow's canvas captures the
        scroll wheel for zoom/pan while the cursor is over it, which traps a
        mouse-wheel scroll attempt and makes anything placed below the
        (480px-tall) canvas awkward to reach. Asking a question is this
        page's primary action; it should never require fighting a graph's
        scroll capture to find the input box.

        The Guided Tour's `copilot-input` anchor sits on the FORM, not the
        textarea. react-joyride's overlay intercepts pointer events everywhere
        outside the spotlight cut-out, and only the spotlighted element stays
        interactive (v3 default `blockTargetInteraction: false`). Anchoring on
        the textarea alone left the "Ask Copilot" submit button underneath the
        overlay, so the tour step's own instruction ("submit it yourself") was
        physically impossible -- the click was swallowed, or worse, read as an
        overlay click that closed the step. The form wraps both controls, so
        spotlighting it keeps the whole submit affordance reachable.
      */}
      <form
        onSubmit={handleSubmit}
        data-tour="copilot-input"
        className="card mt-5 flex items-end gap-2 p-3"
      >
        <textarea
          value={inputValue}
          onChange={(event) => {
            // WCAG 2.2.1 Timing Adjustable: a user who has started typing
            // their next question has told us they are staying -- mark
            // navigationCancelled for the newest message the same way
            // "Stay here" does, before updating the input value.
            if (latestAssistantId !== null) {
              setNavigationCancelled((prev) => ({ ...prev, [latestAssistantId]: true }))
            }
            setInputValue(event.target.value)
          }}
          disabled={isStreaming}
          placeholder='Ask e.g. "Is GXP-MFG-DEMO-01 audit ready?"'
          rows={2}
          className="input-field max-h-40 min-h-[3rem] flex-1 resize-none overflow-y-auto border-0 bg-transparent disabled:cursor-not-allowed disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={isStreaming || inputValue.trim().length === 0}
          className="btn btn-success"
        >
          {isStreaming ? 'Investigating…' : 'Ask Copilot'}
        </button>
      </form>

      <div className="mt-6">
        <AgentTopologyCanvas nodeStatus={nodeStatus} disconnected={disconnected} />
      </div>

      <div className="card mt-6 p-4">
        {messages.length === 0 ? (
          <div data-testid="copilot-empty-state">
            <p className="text-lg font-semibold text-ink">{EMPTY_STATE_HEADING}</p>
            <p className="mt-1 text-sm text-ink-muted">{EMPTY_STATE_BODY}</p>
          </div>
        ) : (
          <div
            ref={messagesContainerRef}
            className="max-h-[32rem] space-y-3 overflow-y-auto"
            data-testid="copilot-messages"
            data-tour="copilot-messages"
          >
            {messages.map((message) => (
              <ChatMessage
                key={message.id}
                message={message}
                systemId={selectedSystemId}
                autoNavigateArmed={message.id === latestAssistantId && !navigationCancelled[message.id]}
                onNavigationCancelled={() =>
                  setNavigationCancelled((prev) => ({ ...prev, [message.id]: true }))
                }
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
