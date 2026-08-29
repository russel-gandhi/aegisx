import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { RetrievalEvidenceItem } from '../lib/api'
import { evidenceHref, evidenceLinkLabel } from '../lib/navigation'

// Pure presentation, per D-09/D-11 and Bible Section 1.3: this component is
// a window onto server-trusted state, extending AssuranceCard.tsx's own
// module discipline. It performs no fetch, no arithmetic beyond formatting
// a number to 2 decimal places, and no grading -- every value read from
// props reflects exactly what the server sent, and a missing server field
// is shown as missing (an explicit "no section" / "n/a"), never silently
// replaced by a client-invented default. A client-side default here would
// be precisely the failure mode D-09 forbids. Per D-13: each item's deep
// link address is built by lib/navigation.ts from server-sent identifiers,
// never taken from a server-sent URL, because this component renders
// content that originated in an uploaded document.
export interface EvidenceViewProps {
  evidence: RetrievalEvidenceItem[]
  evidenceSupport: string
  insufficientEvidence: boolean
  modelAttribution?: string
  systemId: string
}

// Reused verbatim from AssuranceCard.tsx's CONFIDENCE_STYLES, remapped to
// this component's four evidence-support band names (06.1-UI-SPEC.md Color
// table, "Evidence-support badge" rows).
export const EVIDENCE_SUPPORT_STYLES: Record<string, string> = {
  HIGH: 'border-emerald-700 bg-emerald-950/40',
  MODERATE: 'border-amber-700 bg-amber-950/40',
  LIMITED: 'border-orange-700 bg-orange-950/40',
  INSUFFICIENT_EVIDENCE: 'border-red-700 bg-red-950/40',
}

export const EVIDENCE_SUPPORT_LABELS: Record<string, string> = {
  HIGH: 'High evidence support',
  MODERATE: 'Moderate evidence support',
  LIMITED: 'Limited evidence support',
  INSUFFICIENT_EVIDENCE: 'Insufficient evidence',
}

// 06.1-UI-SPEC.md Color table: deliberately neutral slate-800/slate-300, no
// accent hue -- a provenance fact, not a quality signal.
export const RETRIEVAL_METHOD_LABELS: Record<string, string> = {
  semantic: 'Semantic',
  keyword: 'Keyword',
  hybrid: 'Hybrid',
  parent_context: 'Section context',
  graph: 'Graph',
}

export const EVIDENCE_TYPE_LABELS: Record<string, string> = {
  document: 'Document evidence',
  graph_relationship: 'Graph relationship',
}

export const WHY_SELECTED_PREFIX = 'Why this evidence was selected:'

// 06.1-UI-SPEC.md Copywriting Contract, transcribed verbatim.
export const INSUFFICIENT_EVIDENCE_COPY =
  'Insufficient evidence to answer this question. AegisX searched the indexed knowledge base ' +
  'and found nothing relevant enough to ground an answer — try rephrasing, or upload a document ' +
  'that covers this topic.'

export const VISIBLE_EVIDENCE_LIMIT = 5

function SectionLabel({ children }: { children: string }) {
  return (
    <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{children}</p>
  )
}

// Formatting to 2 decimal places is the only arithmetic this component
// performs -- the score itself is read verbatim from the server response.
function formatScore(label: string, value: number | null): string | null {
  if (value === null) {
    return null
  }
  return `${label} ${value.toFixed(2)}`
}

function EvidenceItem({ item, systemId }: { item: RetrievalEvidenceItem; systemId: string }) {
  const typeLabel = EVIDENCE_TYPE_LABELS[item.evidence_type] ?? item.evidence_type
  const methodLabel = RETRIEVAL_METHOD_LABELS[item.retrieval_method] ?? item.retrieval_method
  const isGraphRelationship = item.evidence_type === 'graph_relationship'
  const href = evidenceHref(item, systemId)
  const linkLabel = evidenceLinkLabel(item)

  const scores = [
    formatScore('Semantic', item.dense_score),
    formatScore('Keyword', item.bm25_score),
    formatScore('Reranked', item.reranker_score),
  ].filter((score): score is string => score !== null)

  return (
    <div
      data-testid={`evidence-item-${item.evidence_id}`}
      data-evidence-type={item.evidence_type}
      className="rounded border border-slate-800 bg-slate-900/50 p-4"
    >
      <span
        data-testid={`evidence-type-badge-${item.evidence_id}`}
        className="inline-block rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300"
      >
        {typeLabel}
      </span>

      <div className="mt-2">
        <SectionLabel>SOURCE</SectionLabel>
        <p className="mt-1 text-sm text-slate-100">{item.document_title}</p>
      </div>

      {!isGraphRelationship && (
        <div className="mt-2">
          <SectionLabel>SECTION/PAGE</SectionLabel>
          <p className="mt-1 text-sm text-slate-400">
            {item.section === null ? 'no section' : item.section} —{' '}
            {item.page === null ? 'n/a' : item.page}
          </p>
        </div>
      )}

      {isGraphRelationship && item.graph_path.length > 0 && (
        <div className="mt-2">
          <SectionLabel>GRAPH PATH</SectionLabel>
          <p className="mt-1 text-sm text-slate-400">{item.graph_path.join(' → ')}</p>
        </div>
      )}

      <div className="mt-2">
        <SectionLabel>RETRIEVAL METHOD</SectionLabel>
        <span
          data-testid={`evidence-method-badge-${item.evidence_id}`}
          className="mt-1 inline-block rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300"
        >
          {methodLabel}
        </span>
      </div>

      {scores.length > 0 && (
        <div className="mt-2">
          <SectionLabel>SCORES</SectionLabel>
          <p className="mt-1 text-sm text-slate-400">{scores.join(' · ')}</p>
        </div>
      )}

      <div className="mt-2">
        <p className="text-sm text-slate-400">
          {WHY_SELECTED_PREFIX} <span className="text-slate-300">{item.why_selected}</span>
        </p>
      </div>

      {href !== null && linkLabel !== null && (
        <div className="mt-2">
          <Link
            to={href}
            data-testid="evidence-item-link"
            className="text-slate-300 underline underline-offset-2 hover:text-slate-100"
          >
            {linkLabel}
          </Link>
        </div>
      )}
    </div>
  )
}

// EVIDENCE_SUPPORT_STYLES/EVIDENCE_SUPPORT_LABELS driven by `evidenceSupport`
// -- fixed section order per item: SOURCE -> SECTION/PAGE -> RETRIEVAL
// METHOD -> SCORES -> "Why this evidence was selected:", mirroring
// AssuranceCard's own fixed-section-order convention.
export default function EvidenceView({
  evidence,
  evidenceSupport,
  insufficientEvidence,
  modelAttribution,
  systemId,
}: EvidenceViewProps) {
  const [expanded, setExpanded] = useState(false)

  if (insufficientEvidence) {
    return (
      <div
        data-testid="evidence-view-panel"
        className="max-w-2xl rounded-lg border border-red-700 bg-red-950/40 p-4"
      >
        <p className="text-sm text-slate-100">{INSUFFICIENT_EVIDENCE_COPY}</p>
      </div>
    )
  }

  const badgeStyle = EVIDENCE_SUPPORT_STYLES[evidenceSupport] ?? 'border-slate-700 bg-slate-900/40'
  const badgeLabel = EVIDENCE_SUPPORT_LABELS[evidenceSupport] ?? evidenceSupport
  const hasOverflow = evidence.length > VISIBLE_EVIDENCE_LIMIT
  const hiddenCount = evidence.length - VISIBLE_EVIDENCE_LIMIT

  return (
    <div data-testid="evidence-view-panel" className={`max-w-2xl rounded-lg border p-4 ${badgeStyle}`}>
      <span
        data-testid="evidence-support-badge"
        className="inline-block rounded px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-slate-100"
      >
        {badgeLabel}
      </span>

      <div className="mt-3 space-y-3">
        {evidence.map((item, index) => {
          const isOverflowItem = hasOverflow && index >= VISIBLE_EVIDENCE_LIMIT
          const overflowClass =
            isOverflowItem && !expanded
              ? 'h-0 overflow-hidden opacity-0'
              : 'h-auto opacity-100'
          return (
            <div
              key={item.evidence_id}
              className={`transition-all duration-200 ${overflowClass}`}
              aria-hidden={false}
            >
              <EvidenceItem item={item} systemId={systemId} />
            </div>
          )
        })}
      </div>

      {hasOverflow && (
        <button
          type="button"
          data-testid="evidence-view-expander"
          onClick={() => setExpanded((prev) => !prev)}
          className="mt-3 text-sm text-slate-400 hover:text-slate-200"
        >
          {expanded ? 'Show fewer' : `Show ${hiddenCount} more`}
        </button>
      )}

      {modelAttribution !== undefined && (
        <p className="mt-3 text-xs text-slate-500">Model: {modelAttribution}</p>
      )}
    </div>
  )
}
