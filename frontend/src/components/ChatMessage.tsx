import { useEffect, useState } from 'react'
import type { AssuranceCardData, CopilotInvestigateResult } from '../lib/api'
import AssuranceCard from './AssuranceCard'
import AutoNavigateNotice from './AutoNavigateNotice'
import EvidenceView from './EvidenceView'
import InvestigationTrace from './InvestigationTrace'

// Phase 6 (UI-04, D-01/D-04/D-05) + Phase 06.1 plan 06 (RAG-06/RAG-07,
// D-07/D-09/D-10/D-11): one entry per turn in the Copilot chat.
// `kind: 'cards'` is the hero-query path (D-01/D-05) -- `cards` accumulates
// as `AssuranceCard`s stream in, one at a time, never all-at-once.
// `kind: 'investigation'` is the free-text real-graph path (06.1-06):
// renders a grounded answer, an "How AegisX searched" trace toggle, and an
// inspectable evidence list -- or, when the server reports
// `insufficient_evidence`, the honest insufficient-evidence copy in place
// of all three (D-09).
// `kind: 'text'` covers everything else: the user's own echoed input, the
// legacy unrecognized-shape stub/response, an injection-blocked response
// (`variant: 'blocked'`), and a stream-failure message (`variant: 'error'`).
export interface ChatMessageData {
  id: string
  role: 'user' | 'assistant'
  kind: 'text' | 'cards' | 'investigation'
  text?: string
  cards?: AssuranceCardData[]
  investigation?: CopilotInvestigateResult
  variant?: 'default' | 'error' | 'blocked'
  status?: 'investigating' | 'done'
}

export interface ChatMessageProps {
  message: ChatMessageData
  // Phase 06.1 plan 06.1-08 (D-13): the system id the page sent with the
  // request -- threaded down to EvidenceView's deep links and
  // AutoNavigateNotice's route resolution, never inferred from the
  // response.
  systemId: string
  autoNavigateArmed: boolean
  onNavigationCancelled?: () => void
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

export default function ChatMessage({
  message,
  systemId,
  autoNavigateArmed,
  onNavigationCancelled,
}: ChatMessageProps) {
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

  if (message.kind === 'investigation') {
    const investigating = message.status === 'investigating'
    const result = message.investigation

    return (
      <div className="flex justify-start">
        <div
          data-testid="chat-message-assistant"
          data-kind="investigation"
          className={`max-w-2xl space-y-3 rounded-lg border px-4 py-3 text-sm transition-opacity duration-200 ${DEFAULT_ASSISTANT_BUBBLE_STYLE} ${opacityClass}`}
        >
          {investigating && <p className="text-slate-400">Investigating…</p>}

          {!investigating && result !== undefined && (
            <>
              {result.insufficient_evidence ? (
                <EvidenceView
                  evidence={result.evidence}
                  evidenceSupport={result.evidence_support}
                  insufficientEvidence
                  systemId={systemId}
                />
              ) : (
                <>
                  <p className="whitespace-pre-wrap text-slate-100">{result.answer}</p>
                  <p className="text-xs text-slate-500">Model: {result.model_attribution}</p>
                  <InvestigationTrace stages={result.stages} />
                  <EvidenceView
                    evidence={result.evidence}
                    evidenceSupport={result.evidence_support}
                    insufficientEvidence={false}
                    systemId={systemId}
                  />
                </>
              )}
              <AutoNavigateNotice
                target={result.navigation_target}
                armed={autoNavigateArmed && !result.insufficient_evidence}
                onCancelled={onNavigationCancelled ?? (() => {})}
              />
            </>
          )}
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
