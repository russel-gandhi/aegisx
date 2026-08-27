import { useEffect, useState } from 'react'
import type { AssuranceCardData } from '../lib/api'
import AssuranceCard from './AssuranceCard'

// Phase 6 (UI-04, D-01/D-04/D-05): one entry per turn in the Copilot chat.
// `kind: 'cards'` is the hero-query path (D-01/D-05) -- `cards` accumulates
// as `AssuranceCard`s stream in, one at a time, never all-at-once.
// `kind: 'text'` covers everything else: the user's own echoed input, the
// unrecognized-shape stub/response (D-04), an injection-blocked response
// (`variant: 'blocked'`), and a stream-failure message (`variant: 'error'`).
export interface ChatMessageData {
  id: string
  role: 'user' | 'assistant'
  kind: 'text' | 'cards'
  text?: string
  cards?: AssuranceCardData[]
  variant?: 'default' | 'error' | 'blocked'
  status?: 'investigating' | 'done'
}

export interface ChatMessageProps {
  message: ChatMessageData
}

// Reused verbatim from 06-UI-SPEC.md's Color table: injection-blocked and
// stream-failure responses share the same destructive treatment.
const DESTRUCTIVE_BUBBLE_STYLE = 'border-red-700 bg-red-950/40 text-slate-100'
const DEFAULT_ASSISTANT_BUBBLE_STYLE = 'border-slate-800 bg-slate-900/50 text-slate-100'
const USER_BUBBLE_STYLE = 'border-slate-700 bg-slate-800 text-slate-100'

// 06-UI-SPEC.md Animation Contract: "Chat message, on arrival -- Fade-in
// ... `transition-opacity duration-200` from `opacity-0` to `opacity-100`
// ... decorative only, must not delay content readability." Content is
// always rendered immediately; only the opacity class lags one paint
// behind mount, via this hook, so the animation never gates readability.
function useFadeIn(): boolean {
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    setVisible(true)
  }, [])
  return visible
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const visible = useFadeIn()
  const opacityClass = visible ? 'opacity-100' : 'opacity-0'

  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div
          data-testid="chat-message-user"
          className={`max-w-2xl rounded-lg border px-4 py-2 text-sm transition-opacity duration-200 ${USER_BUBBLE_STYLE} ${opacityClass}`}
        >
          {message.text}
        </div>
      </div>
    )
  }

  if (message.kind === 'cards') {
    const cards = message.cards ?? []
    return (
      <div className="flex justify-start">
        <div
          data-testid="chat-message-assistant"
          data-kind="cards"
          className={`max-w-2xl space-y-4 rounded-lg border px-4 py-3 text-sm transition-opacity duration-200 ${DEFAULT_ASSISTANT_BUBBLE_STYLE} ${opacityClass}`}
        >
          {message.status === 'investigating' && cards.length === 0 && (
            <p className="text-slate-400">Investigating…</p>
          )}
          {message.status === 'done' && cards.length === 0 && (
            <p className="text-slate-400">
              Every deterministic check currently passes -- no findings to review.
            </p>
          )}
          {cards.map((card) => (
            <AssuranceCard key={card.finding_id} card={card} />
          ))}
        </div>
      </div>
    )
  }

  const bubbleStyle =
    message.variant === 'error' || message.variant === 'blocked'
      ? DESTRUCTIVE_BUBBLE_STYLE
      : DEFAULT_ASSISTANT_BUBBLE_STYLE

  return (
    <div className="flex justify-start">
      <div
        data-testid="chat-message-assistant"
        data-kind="text"
        data-variant={message.variant ?? 'default'}
        className={`max-w-2xl whitespace-pre-wrap rounded-lg border px-4 py-2 text-sm transition-opacity duration-200 ${bubbleStyle} ${opacityClass}`}
      >
        {message.text}
      </div>
    </div>
  )
}
