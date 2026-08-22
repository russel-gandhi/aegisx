import { useEffect, useState } from 'react'
import EvidenceGraphCanvas from '../components/EvidenceGraphCanvas'
import { fetchEvidenceGraph, type EvidenceGraphResponse } from '../lib/api'

const SYSTEM_OPTIONS = [
  { id: 'GXP-MFG-DEMO-01', label: 'GXP-MFG-DEMO-01 (NovaSynth MES)' },
  { id: 'BUS-IT-DEMO-02', label: 'BUS-IT-DEMO-02 (non-GxP)' },
]

type LoadState = 'loading' | 'error' | 'ready'

export default function BlastRadius() {
  const [systemId, setSystemId] = useState(SYSTEM_OPTIONS[0].id)
  const [state, setState] = useState<LoadState>('loading')
  const [data, setData] = useState<EvidenceGraphResponse | null>(null)

  useEffect(() => {
    let cancelled = false

    fetchEvidenceGraph(systemId)
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
      <h1 className="text-2xl font-semibold text-slate-100">Blast Radius</h1>
      <p className="mt-2 max-w-2xl text-slate-400">
        The graph below is built deterministically from live Postgres state by NetworkX -- no
        model ever invents, infers, or ranks a relationship shown here (Bible Section 1.3).
      </p>

      <div className="mt-4">
        <label htmlFor="blast-radius-system" className="text-sm text-slate-400">
          System
        </label>
        <select
          id="blast-radius-system"
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

      <div className="mt-6">
        {state === 'loading' && <p className="text-slate-400">Loading evidence graph...</p>}
        {state === 'error' && (
          <p className="text-red-400">
            Error loading the evidence graph. Confirm the backend is running and reachable.
          </p>
        )}
        {state === 'ready' && data && data.nodes.length === 0 && (
          <p className="text-slate-400">
            {`No cached evidence graph for ${systemId} yet. Run the rebuild endpoint first (POST /api/systems/${systemId}/evidence-graph/rebuild) -- the read endpoint never rebuilds on its own (D-02).`}
          </p>
        )}
        {state === 'ready' && data && data.nodes.length > 0 && (
          <EvidenceGraphCanvas nodes={data.nodes} edges={data.edges} />
        )}
      </div>

      {/* Plan 04-05 attaches the Blast Radius side panel and node-click
          impact-traversal handling here. Not built in this plan. */}
    </div>
  )
}
