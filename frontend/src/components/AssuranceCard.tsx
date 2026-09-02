import type { AssuranceCardData } from '../lib/api'

// Pure presentation, per EVID-03 and Bible Section 1.3: this component is a
// window onto server-trusted state. It performs no fetch, no arithmetic, no
// grading, and holds no fallback that would let a missing server field be
// replaced by a client-invented one -- a client-side default here would be
// exactly the LLM-generated-UI failure mode the requirement forbids. Every
// rendered value reads from the `card` prop and nothing else.
export interface AssuranceCardProps {
  card: AssuranceCardData
}

const CONFIDENCE_STYLES: Record<string, string> = {
  HIGH: 'border-l-mint',
  MEDIUM: 'border-l-amber',
  LOW: 'border-l-orange',
  INSUFFICIENT_EVIDENCE: 'border-l-red',
}

const CONFIDENCE_BADGE_STYLES: Record<string, string> = {
  HIGH: 'badge-mint',
  MEDIUM: 'badge-amber',
  LOW: 'badge-orange',
  INSUFFICIENT_EVIDENCE: 'badge-red',
}

const ALCOA_LABELS: Record<string, string> = {
  attributable: 'Attributable',
  legible: 'Legible',
  contemporaneous: 'Contemporaneous',
  original: 'Original',
  accurate: 'Accurate',
  complete: 'Complete',
  consistent: 'Consistent',
  enduring: 'Enduring',
  available: 'Available',
}

function SectionLabel({ children }: { children: string }) {
  return <p className="text-[11px] font-bold tracking-[0.08em] text-ink-faint uppercase">{children}</p>
}

// Rendered, in this fixed order, the union of EVID-03's five required
// sections and Bible Section 11.2's field list: CLAIM, EVIDENCE, RULE,
// DETERMINISTIC CHECK, CONFIDENCE, then the ALCOA+ nine-dimension grid and
// the model attribution line.
export default function AssuranceCard({ card }: AssuranceCardProps) {
  const borderStyle = CONFIDENCE_STYLES[card.confidence] ?? 'border-l-white/20'
  const badgeStyle = CONFIDENCE_BADGE_STYLES[card.confidence] ?? 'badge-neutral'
  const alcoaTrue = Object.values(card.alcoa_score).filter(Boolean).length

  return (
    <div
      data-testid="assurance-card"
      data-confidence={card.confidence}
      className={`card border-l-[3px] p-5 ${borderStyle}`}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="font-mono text-[11px] text-ink-faint">{card.finding_id}</p>
        <div className="text-right">
          <SectionLabel>Confidence</SectionLabel>
          <span className={`badge mt-1 ${badgeStyle}`}>{card.confidence}</span>
        </div>
      </div>

      <div className="mt-3">
        <SectionLabel>Claim</SectionLabel>
        <p className="mt-1 text-[14px] leading-relaxed text-ink">{card.claim}</p>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <SectionLabel>Evidence</SectionLabel>
          {card.evidence_ids.length === 0 ? (
            <p className="mt-1 text-[13px] text-ink-muted">
              No evidence record exists for this finding -- A2 emitted a no-record marker
              rather than fabricating an identifier.
            </p>
          ) : (
            <ul className="mt-1 space-y-0.5 font-mono text-[12.5px] text-ink">
              {card.evidence_ids.map((evidenceId) => (
                <li key={evidenceId}>{evidenceId}</li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <SectionLabel>Rule</SectionLabel>
          <ul className="mt-1 space-y-0.5 font-mono text-[12.5px] text-ink">
            {card.regulatory_citations.map((citation) => (
              <li key={citation}>{citation}</li>
            ))}
          </ul>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-white/[0.06] bg-black/20 p-3">
        <SectionLabel>Deterministic check</SectionLabel>
        <p className="mt-1 font-mono text-[12.5px] text-ink">{card.deterministic_check.check_name}</p>
        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-ink-muted">
          <span>
            Database record found:{' '}
            <span className="font-medium text-ink">
              {card.deterministic_check.db_record_found ? 'Yes' : 'No'}
            </span>
          </span>
          <span>
            OPA corroborated:{' '}
            <span className="font-medium text-ink">
              {card.deterministic_check.opa_corroborated ? 'Yes' : 'No'}
            </span>
          </span>
        </div>
      </div>

      <div className="mt-4 border-t border-white/[0.07] pt-3">
        <div className="flex items-center justify-between">
          <SectionLabel>ALCOA+ data integrity</SectionLabel>
          <span className="text-[11px] font-semibold text-ink-faint">{alcoaTrue}/9</span>
        </div>
        <div className="mt-2 grid grid-cols-3 gap-1.5 sm:grid-cols-3">
          {Object.entries(card.alcoa_score).map(([dimension, value]) => (
            <span
              key={dimension}
              className={`flex items-center gap-1 rounded-md px-1.5 py-1 text-[10.5px] ${
                value ? 'text-mint' : 'text-ink-faint'
              }`}
            >
              <span className={`h-1 w-1 shrink-0 rounded-full ${value ? 'bg-mint' : 'bg-white/20'}`} />
              {ALCOA_LABELS[dimension] ?? dimension}
            </span>
          ))}
        </div>
      </div>

      <p className="mt-4 font-mono text-[11px] text-ink-faint">Model: {card.model_attribution}</p>
    </div>
  )
}
