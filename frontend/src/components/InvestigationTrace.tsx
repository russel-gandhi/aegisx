import { useEffect, useState } from 'react'
import type { InvestigationStage } from '../lib/api'

// Pure presentation, per D-10 and Bible Section 1.3: this component is a
// window onto server-trusted state, following EvidenceView.tsx's own
// module discipline. It performs no fetch, no arithmetic, and holds no
// timer that advances a stage or state that changes a stage's status after
// mount -- every glyph, label, and detail string is read from the `stages`
// prop and nothing else.
//
// This phase's investigate call is a single awaited request with no
// per-stage push channel, so the honest contract is one "Investigating…"
// state while in flight (owned by the parent, ChatMessage.tsx) and then
// the full stage sequence revealed from the response's own metadata. A
// stage-by-stage progress animation not backed by real server events would
// violate UI_SPEC.md §7.2/§9's rule against animating fake progress
// independently of the backend. Upgrading to live per-stage transitions
// later, if a real SSE channel is added for this path, is additive to this
// contract rather than a contradiction of it.
export interface InvestigationTraceProps {
  stages: InvestigationStage[]
}

export const TRACE_TOGGLE_LABEL = 'How AegisX searched'

export const STAGE_GLYPHS: Record<string, string> = {
  complete: '✓',
  skipped: '-',
}

function useMountedOnce(): boolean {
  const [mounted, setMounted] = useState(false)
  useEffect(() => {
    setMounted(true)
  }, [])
  return mounted
}

export default function InvestigationTrace({ stages }: InvestigationTraceProps) {
  const [open, setOpen] = useState(false)
  const mounted = useMountedOnce()

  if (stages.length === 0) {
    return null
  }

  return (
    <div data-testid="investigation-trace-panel" className="max-w-2xl">
      <button
        type="button"
        data-testid="investigation-trace-toggle"
        onClick={() => setOpen((prev) => !prev)}
        className="text-[13px] font-medium text-ink-faint hover:text-ink"
      >
        {TRACE_TOGGLE_LABEL}
      </button>

      {open && (
        <div className="mt-2 space-y-2 rounded-lg border border-white/[0.06] bg-black/15 p-3">
          {stages.map((stage, index) => {
            const glyph = STAGE_GLYPHS[stage.status] ?? '-'
            const isComplete = stage.status === 'complete'
            const glyphClass = isComplete ? 'text-mint' : 'text-ink-faint'
            const labelClass = isComplete ? 'text-ink' : 'text-ink-faint'
            return (
              <div
                key={stage.stage_id}
                data-testid={`investigation-trace-row-${stage.stage_id}`}
                className={`transition-opacity duration-200 ${mounted ? 'opacity-100' : 'opacity-0'}`}
                style={{ transitionDelay: `${index * 40}ms` }}
              >
                <span
                  data-testid={`investigation-trace-glyph-${stage.stage_id}`}
                  className={`mr-2 font-semibold ${glyphClass}`}
                >
                  {glyph}
                </span>
                <span className={`text-[13px] ${labelClass}`}>{stage.label}</span>
                {stage.detail !== null && (
                  <p className="mt-0.5 ml-6 text-[11.5px] text-ink-faint">{stage.detail}</p>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
