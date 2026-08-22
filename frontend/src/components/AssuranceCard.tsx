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
  HIGH: 'border-emerald-700 bg-emerald-950/40',
  MEDIUM: 'border-amber-700 bg-amber-950/40',
  LOW: 'border-orange-700 bg-orange-950/40',
  INSUFFICIENT_EVIDENCE: 'border-red-700 bg-red-950/40',
}

const CONFIDENCE_BADGE_STYLES: Record<string, string> = {
  HIGH: 'bg-emerald-700 text-emerald-50',
  MEDIUM: 'bg-amber-700 text-amber-50',
  LOW: 'bg-orange-700 text-orange-50',
  INSUFFICIENT_EVIDENCE: 'bg-red-700 text-red-50',
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
  return (
    <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{children}</p>
  )
}

// Rendered, in this fixed order, the union of EVID-03's five required
// sections and Bible Section 11.2's field list: CLAIM, EVIDENCE, RULE,
// DETERMINISTIC CHECK, CONFIDENCE, then the ALCOA+ nine-dimension grid and
// the model attribution line.
export default function AssuranceCard({ card }: AssuranceCardProps) {
  const borderStyle = CONFIDENCE_STYLES[card.confidence] ?? 'border-slate-700 bg-slate-900/40'
  const badgeStyle = CONFIDENCE_BADGE_STYLES[card.confidence] ?? 'bg-slate-700 text-slate-50'

  return (
    <div
      data-testid="assurance-card"
      data-confidence={card.confidence}
      className={`rounded-lg border p-4 ${borderStyle}`}
    >
      <p className="text-sm text-slate-500">{card.finding_id}</p>

      <div className="mt-3">
        <SectionLabel>CLAIM</SectionLabel>
        <p className="mt-1 text-sm text-slate-100">{card.claim}</p>
      </div>

      <div className="mt-3">
        <SectionLabel>EVIDENCE</SectionLabel>
        {card.evidence_ids.length === 0 ? (
          <p className="mt-1 text-sm text-slate-400">
            No evidence record exists for this finding -- A2 emitted a no-record marker
            rather than fabricating an identifier.
          </p>
        ) : (
          <ul className="mt-1 text-sm text-slate-100">
            {card.evidence_ids.map((evidenceId) => (
              <li key={evidenceId}>{evidenceId}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-3">
        <SectionLabel>RULE</SectionLabel>
        <ul className="mt-1 text-sm text-slate-100">
          {card.regulatory_citations.map((citation) => (
            <li key={citation}>{citation}</li>
          ))}
        </ul>
      </div>

      <div className="mt-3">
        <SectionLabel>DETERMINISTIC CHECK</SectionLabel>
        <p className="mt-1 text-sm text-slate-100">{card.deterministic_check.check_name}</p>
        <p className="mt-1 text-sm text-slate-400">
          Database record found:{' '}
          <span className="text-slate-200">
            {card.deterministic_check.db_record_found ? 'yes' : 'no'}
          </span>
        </p>
        <p className="text-sm text-slate-400">
          OPA corroborated:{' '}
          <span className="text-slate-200">
            {card.deterministic_check.opa_corroborated ? 'yes' : 'no'}
          </span>
        </p>
      </div>

      <div className="mt-3">
        <SectionLabel>CONFIDENCE</SectionLabel>
        <span
          className={`mt-1 inline-block rounded px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${badgeStyle}`}
        >
          {card.confidence}
        </span>
      </div>

      <div className="mt-4 border-t border-slate-800 pt-3">
        <SectionLabel>ALCOA+</SectionLabel>
        <div className="mt-1 grid grid-cols-3 gap-x-3 gap-y-1 text-xs text-slate-300 sm:grid-cols-3">
          {Object.entries(card.alcoa_score).map(([dimension, value]) => (
            <span key={dimension}>
              {ALCOA_LABELS[dimension] ?? dimension}: {value ? 'yes' : 'no'}
            </span>
          ))}
        </div>
      </div>

      <p className="mt-3 text-xs text-slate-500">Model: {card.model_attribution}</p>
    </div>
  )
}
