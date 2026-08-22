import { useEffect, useState } from 'react'
import AssuranceCard from '../components/AssuranceCard'
import { fetchAssuranceCards, type AssuranceCardsResponse } from '../lib/api'

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
          data.cards.map((card) => <AssuranceCard key={card.finding_id} card={card} />)}
      </div>

      {/* Plan 04-05 attaches the per-card Blast Radius link here. Not
          built in this plan. */}
    </div>
  )
}
