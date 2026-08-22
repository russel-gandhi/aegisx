import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import AssuranceCard from '../components/AssuranceCard'
import {
  fetchAssuranceCards,
  fetchEvidenceGraph,
  type AssuranceCardsResponse,
} from '../lib/api'

const SYSTEM_OPTIONS = [
  { id: 'GXP-MFG-DEMO-01', label: 'GXP-MFG-DEMO-01 (NovaSynth MES)' },
  { id: 'BUS-IT-DEMO-02', label: 'BUS-IT-DEMO-02 (non-GxP)' },
]

type LoadState = 'loading' | 'error' | 'ready'

// This route is a deliberate, user-approved Phase 4 addition beyond Bible
// Section 11's nine pages -- it exists because the full Copilot chat that
// will eventually host this card (D-04) does not land until Phase 6.
// Routed to SENT-7-05 for Bible reconciliation.
export default function FindingInvestigation() {
  const [systemId, setSystemId] = useState(SYSTEM_OPTIONS[0].id)
  const [state, setState] = useState<LoadState>('loading')
  const [data, setData] = useState<AssuranceCardsResponse | null>(null)

  // Bible Section 14.3's Finding -> Evidence -> Verification -> Blast
  // Radius exposure tree, third branch: a lookup from a card's evidence id
  // (a raw domain primary key, e.g. "PE-2024-01") to the matching
  // evidence-graph node's id (critical finding 7), so each card can link
  // straight to its own blast radius rather than Blast Radius sitting as
  // an unrelated standalone feature.
  const [evidenceNodeIndex, setEvidenceNodeIndex] = useState<Record<string, string>>({})

  useEffect(() => {
    let cancelled = false

    fetchAssuranceCards(systemId)
      .then((response) => {
        if (cancelled) return
        setData(response)
        setState('ready')
      })
      .catch(() => {
        if (cancelled) return
        setState('error')
      })

    return () => {
      cancelled = true
    }
  }, [systemId])

  useEffect(() => {
    let cancelled = false

    fetchEvidenceGraph(systemId)
      .then((response) => {
        if (cancelled) return
        const index: Record<string, string> = {}
        for (const node of response.nodes) {
          index[node.entity_id] = node.node_id
        }
        setEvidenceNodeIndex(index)
      })
      .catch(() => {
        // Strictly optional (critical finding 8, D-02): a failed or
        // unpopulated evidence-graph fetch must never block the cards
        // themselves, EVID-03's required content -- it only means no
        // Blast Radius links render this pass. No page-level error state.
        if (cancelled) return
        setEvidenceNodeIndex({})
      })

    return () => {
      cancelled = true
    }
  }, [systemId])

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-100">Evidence Investigation</h1>
      <p className="mt-2 max-w-2xl text-slate-400">
        Each card&apos;s confidence was computed deterministically against the system&apos;s own
        database records and the OPA policy engine -- not by the model that wrote the claim
        (EVID-03, Bible Section 1.3).
      </p>

      <div className="mt-4">
        <label htmlFor="findings-system" className="text-sm text-slate-400">
          System
        </label>
        <select
          id="findings-system"
          className="ml-2 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm text-slate-100"
          value={systemId}
          onChange={(e) => {
            setState('loading')
            setData(null)
            setSystemId(e.target.value)
          }}
        >
          {SYSTEM_OPTIONS.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-6 space-y-4">
        {state === 'loading' && <p className="text-slate-400">Loading assurance cards...</p>}
        {state === 'error' && (
          <p className="text-red-400">
            Error loading assurance cards. Confirm the backend is running and reachable.
          </p>
        )}
        {state === 'ready' && data && data.cards.length === 0 && (
          <p className="text-slate-400">
            {`Every deterministic check for ${systemId} currently passes -- no findings to review.`}
          </p>
        )}
        {state === 'ready' &&
          data &&
          data.cards.map((card) => (
            <div key={card.finding_id}>
              <AssuranceCard card={card} />
              {/* Bible Section 14.3 UI constraint: Blast Radius reached
                  from the finding investigation experience rather than
                  presented as an unrelated standalone feature -- this is
                  the third exposure-tree branch (Finding -> Evidence ->
                  Verification -> Blast Radius). Rendered beside the card,
                  not inside it, so AssuranceCard.tsx stays exactly as
                  reusable as plan 04-03 built it for Phase 6 (D-04). */}
              {card.evidence_ids.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-3">
                  {card.evidence_ids
                    .filter((evidenceId) => evidenceNodeIndex[evidenceId] !== undefined)
                    .map((evidenceId) => (
                      <Link
                        key={evidenceId}
                        to={`/blast-radius?node=${encodeURIComponent(evidenceNodeIndex[evidenceId])}`}
                        className="text-sm text-sky-400 underline hover:text-sky-300"
                      >
                        {`Blast Radius: ${evidenceId}`}
                      </Link>
                    ))}
                </div>
              )}
            </div>
          ))}
      </div>
    </div>
  )
}
