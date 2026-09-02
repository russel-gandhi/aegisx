import { useEffect, useMemo, useState } from 'react'
import { fetchAssuranceCards, type AssuranceCardData } from '../lib/api'

// Bible Section 11.3: "Presents a filterable matrix of all identified
// compliance findings. The Evidence Confidence Heat Map cross-references
// GxP requirements against existing evidence types (Documents, Test
// Records, Access Reviews), color-coding cells to instantly reveal
// systemic compliance gaps." Every row comes from the real, already-built
// `GET /api/systems/{id}/assurance-cards` endpoint (same data Command
// Centre and the Copilot use) -- this page adds filtering and a
// client-side grouping for the heat map, never a new compliance judgment.
const SYSTEM_IDS = ['GXP-MFG-DEMO-01', 'BUS-IT-DEMO-02'] as const
type SystemId = (typeof SYSTEM_IDS)[number]

type CallStatus = 'loading' | 'ready' | 'error'

const CONFIDENCE_LEVELS = ['HIGH', 'MEDIUM', 'LOW', 'UNVERIFIED'] as const
type Confidence = (typeof CONFIDENCE_LEVELS)[number]

// Deterministic-check-name -> evidence-type grouping (Bible 11.3's own
// three example categories, extended for the checks this build actually
// runs). Purely a display grouping over `deterministic_check.check_name`,
// already computed server-side -- this classifies, it never re-judges.
const EVIDENCE_TYPE_BY_CHECK: Record<string, string> = {
  verify_urs_approved: 'Documents',
  verify_no_stale_documents: 'Documents',
  verify_test_traceability: 'Test Records',
  verify_periodic_eval_current: 'Periodic Review',
}

function evidenceTypeFor(card: AssuranceCardData): string {
  const known = EVIDENCE_TYPE_BY_CHECK[card.deterministic_check.check_name]
  if (known) return known
  const citation = card.regulatory_citations[0] ?? ''
  if (citation.includes('S12-ACC')) return 'Access Reviews'
  if (citation.includes('S13-INC')) return 'Incidents'
  if (citation.includes('RSK')) return 'Risk Assessments'
  if (citation.includes('S10-CHG')) return 'Change Control'
  return 'Other'
}

function ConfidencePill({ confidence }: { confidence: string }) {
  const tone =
    confidence === 'HIGH'
      ? 'bg-red-950/50 text-red-400 border-red-800'
      : confidence === 'MEDIUM'
        ? 'bg-orange-950/50 text-orange-400 border-orange-800'
        : confidence === 'LOW'
          ? 'bg-amber-950/50 text-amber-400 border-amber-800'
          : 'bg-slate-800 text-slate-400 border-slate-700'
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${tone}`}>
      {confidence}
    </span>
  )
}

// Cell intensity scales with count, not a fixed palette lookup -- a heat
// map with only 2-8 findings total (this dataset's real scale) still
// needs visible differentiation between "1 finding" and "3 findings" in
// the same cell, which a flat threshold table can't give.
function heatCellClasses(count: number, max: number): string {
  if (count === 0) return 'bg-slate-900/40 text-slate-600'
  const intensity = max > 0 ? count / max : 0
  if (intensity > 0.66) return 'bg-red-900/70 text-red-100 font-semibold'
  if (intensity > 0.33) return 'bg-orange-900/60 text-orange-100 font-semibold'
  return 'bg-amber-900/40 text-amber-100'
}

export default function AuditReadiness() {
  const [systemId, setSystemId] = useState<SystemId>('GXP-MFG-DEMO-01')
  const [status, setStatus] = useState<CallStatus>('loading')
  const [cards, setCards] = useState<AssuranceCardData[]>([])
  const [confidenceFilter, setConfidenceFilter] = useState<Confidence | 'ALL'>('ALL')
  const [evidenceTypeFilter, setEvidenceTypeFilter] = useState<string>('ALL')

  useEffect(() => {
    let cancelled = false
    setStatus('loading')
    fetchAssuranceCards(systemId)
      .then((res) => {
        if (cancelled) return
        setCards(res.cards)
        setStatus('ready')
      })
      .catch(() => {
        if (cancelled) return
        setStatus('error')
      })
    return () => {
      cancelled = true
    }
  }, [systemId])

  const evidenceTypes = useMemo(
    () => Array.from(new Set(cards.map(evidenceTypeFor))).sort(),
    [cards],
  )

  const heatMap = useMemo(() => {
    const grid: Record<string, Record<string, number>> = {}
    for (const type of evidenceTypes) {
      grid[type] = Object.fromEntries(CONFIDENCE_LEVELS.map((c) => [c, 0]))
    }
    for (const card of cards) {
      const type = evidenceTypeFor(card)
      const confidence = card.confidence as Confidence
      if (grid[type] && confidence in grid[type]) {
        grid[type][confidence] += 1
      }
    }
    return grid
  }, [cards, evidenceTypes])

  const maxCellCount = useMemo(
    () => Math.max(0, ...Object.values(heatMap).flatMap((row) => Object.values(row))),
    [heatMap],
  )

  const filteredCards = cards.filter((card) => {
    if (confidenceFilter !== 'ALL' && card.confidence !== confidenceFilter) return false
    if (evidenceTypeFilter !== 'ALL' && evidenceTypeFor(card) !== evidenceTypeFilter) return false
    return true
  })

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-100">Audit Readiness</h1>
      <p className="mt-2 max-w-2xl text-slate-400">
        Every open compliance finding for this system, independently verified against real
        database records and OPA/Rego policy evaluation.
      </p>

      <div className="mt-4">
        <label htmlFor="audit-readiness-system" className="text-sm text-slate-400">
          System
        </label>
        <select
          id="audit-readiness-system"
          className="ml-2 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm text-slate-100"
          value={systemId}
          onChange={(e) => setSystemId(e.target.value as SystemId)}
        >
          {SYSTEM_IDS.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
      </div>

      {status === 'loading' && <p className="mt-8 text-sm text-slate-400">Loading findings&hellip;</p>}
      {status === 'error' && (
        <p className="mt-8 text-sm text-red-400">Couldn&rsquo;t load assurance data. Refresh to retry.</p>
      )}

      {status === 'ready' && (
        <>
          <div className="mt-8">
            <p className="text-lg font-semibold text-slate-100">Evidence Confidence Heat Map</p>
            <p className="mt-1 text-sm text-slate-400">
              Open findings by evidence type and confidence level. Darker cells mean more findings
              share that combination.
            </p>
            {cards.length === 0 ? (
              <p className="mt-4 text-sm text-slate-500">No open findings for this system.</p>
            ) : (
              <div className="mt-4 overflow-x-auto rounded-lg border border-slate-800">
                <table className="w-full min-w-[560px] border-collapse text-sm">
                  <thead>
                    <tr>
                      <th className="border-b border-slate-800 bg-slate-900/60 px-4 py-2 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                        Evidence Type
                      </th>
                      {CONFIDENCE_LEVELS.map((c) => (
                        <th
                          key={c}
                          className="border-b border-slate-800 bg-slate-900/60 px-4 py-2 text-center text-xs font-medium uppercase tracking-wide text-slate-500"
                        >
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {evidenceTypes.map((type) => (
                      <tr key={type}>
                        <td className="border-b border-slate-800/60 bg-slate-900 px-4 py-3 font-medium text-slate-200 last:border-0">
                          {type}
                        </td>
                        {CONFIDENCE_LEVELS.map((c) => {
                          const count = heatMap[type]?.[c] ?? 0
                          return (
                            <td
                              key={c}
                              className={`border-b border-slate-800/60 px-4 py-3 text-center transition-colors last:border-0 ${heatCellClasses(count, maxCellCount)}`}
                            >
                              {count > 0 ? count : '—'}
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="mt-10">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <p className="text-lg font-semibold text-slate-100">
                Findings Matrix <span className="text-sm font-normal text-slate-500">({filteredCards.length})</span>
              </p>
              <div className="flex flex-wrap items-center gap-3">
                <select
                  aria-label="Filter by confidence"
                  className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm text-slate-100"
                  value={confidenceFilter}
                  onChange={(e) => setConfidenceFilter(e.target.value as Confidence | 'ALL')}
                >
                  <option value="ALL">All confidence levels</option>
                  {CONFIDENCE_LEVELS.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
                <select
                  aria-label="Filter by evidence type"
                  className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm text-slate-100"
                  value={evidenceTypeFilter}
                  onChange={(e) => setEvidenceTypeFilter(e.target.value)}
                >
                  <option value="ALL">All evidence types</option>
                  {evidenceTypes.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="mt-4 space-y-3">
              {filteredCards.length === 0 && (
                <p className="text-sm text-slate-500">No findings match the current filters.</p>
              )}
              {filteredCards.map((card) => (
                <div
                  key={card.finding_id}
                  data-testid="finding-row"
                  className="rounded-lg border border-slate-800 bg-slate-900 p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full border border-slate-700 bg-slate-800/60 px-2 py-0.5 text-xs text-slate-400">
                          {evidenceTypeFor(card)}
                        </span>
                        {card.regulatory_citations.map((cite) => (
                          <span key={cite} className="font-mono text-xs text-slate-500">
                            {cite}
                          </span>
                        ))}
                      </div>
                      <p className="mt-2 text-sm text-slate-200">{card.claim}</p>
                    </div>
                    <ConfidencePill confidence={card.confidence} />
                  </div>
                  <div className="mt-3 flex flex-wrap gap-4 border-t border-slate-800 pt-3 text-xs text-slate-500">
                    <span>
                      DB record: <span className="text-slate-300">{card.deterministic_check.db_record_found ? 'found' : 'missing'}</span>
                    </span>
                    <span>
                      OPA corroborated:{' '}
                      <span className="text-slate-300">{card.deterministic_check.opa_corroborated ? 'yes' : 'no'}</span>
                    </span>
                    <span>
                      Model: <span className="text-slate-300">{card.model_attribution}</span>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
