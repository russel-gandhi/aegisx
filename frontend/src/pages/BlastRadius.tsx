import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import EvidenceGraphCanvas from '../components/EvidenceGraphCanvas'
import NodeDetailPanel from '../components/NodeDetailPanel'
import BlastRadiusPanel from '../components/BlastRadiusPanel'
import {
  fetchEvidenceGraph,
  fetchBlastRadius,
  type EvidenceGraphResponse,
  type BlastRadiusResponse,
} from '../lib/api'

const SYSTEM_OPTIONS = [
  { id: 'GXP-MFG-DEMO-01', label: 'GXP-MFG-DEMO-01 (NovaSynth MES)' },
  { id: 'BUS-IT-DEMO-02', label: 'BUS-IT-DEMO-02 (non-GxP)' },
]

type LoadState = 'loading' | 'error' | 'ready'

export default function BlastRadius() {
  const [searchParams, setSearchParams] = useSearchParams()
  // Plan 06.1-08 (D-13): `?system=` is read only as an initial value and
  // validated against SYSTEM_OPTIONS, because a node id from one system's
  // graph 404s against another's -- which is what this file's own
  // `isFirstSystemChange` comment below already documents from the other
  // direction (system change clears the node selection).
  const [systemId, setSystemId] = useState(() => {
    const requested = searchParams.get('system')
    return SYSTEM_OPTIONS.some((option) => option.id === requested)
      ? (requested as string)
      : SYSTEM_OPTIONS[0].id
  })
  const [state, setState] = useState<LoadState>('loading')
  const [data, setData] = useState<EvidenceGraphResponse | null>(null)

  // Deep link (04-05 interface_contract): `?node=<url-encoded node id>`
  // pre-selects a node on mount, so a card's Blast Radius link
  // (FindingInvestigation.tsx) lands here with its impact summary already
  // displayed. `useSearchParams` decodes the value for us -- no manual
  // `decodeURIComponent` here would double-decode it.
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(() =>
    searchParams.get('node'),
  )
  const isFirstSystemChange = useRef(true)

  const [blastResult, setBlastResult] = useState<BlastRadiusResponse | null>(null)
  const [blastLoading, setBlastLoading] = useState(false)
  const [blastError, setBlastError] = useState<string | null>(null)

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

  // A node id from one system's graph is not present in another system's
  // graph and would 404 the blast-radius request -- clear the selection
  // when the system selector changes. Skips its very first run so a
  // deep-linked ?node= survives initial mount. `setSearchParams` is
  // deliberately excluded from the dependency array: react-router-dom
  // does not guarantee it is referentially stable across renders, and
  // this effect must fire only on a genuine `systemId` change -- not
  // every time `handleNodeClick`'s own `setSearchParams` call produces a
  // new function identity, which would otherwise immediately clear the
  // selection this same click just set.
  useEffect(() => {
    if (isFirstSystemChange.current) {
      isFirstSystemChange.current = false
      return
    }
    setSelectedNodeId(null)
    // Writes `?system=` (REMEDIATION-PLAN.md #5 / 06.1.1-RESEARCH.md D-08):
    // this page previously only read `?system=` on initial mount and never
    // wrote it back, so a shared/bookmarked URL went stale the moment
    // anyone changed the system selector. `node` is dropped here
    // deliberately -- a node id from the old system's graph doesn't exist
    // in the new one.
    setSearchParams({ system: systemId })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [systemId])

  useEffect(() => {
    if (selectedNodeId === null) {
      setBlastResult(null)
      setBlastError(null)
      setBlastLoading(false)
      return
    }

    let cancelled = false
    setBlastLoading(true)
    setBlastError(null)

    fetchBlastRadius(systemId, selectedNodeId)
      .then((response) => {
        if (cancelled) return
        setBlastResult(response)
        setBlastLoading(false)
      })
      .catch(() => {
        if (cancelled) return
        setBlastError(
          'Error loading the blast radius. Confirm the backend is running and reachable.',
        )
        setBlastLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [systemId, selectedNodeId])

  function handleNodeClick(nodeId: string) {
    setSelectedNodeId(nodeId)
    // Keeps `system` alongside `node` -- previously this overwrote the
    // whole query string with just `{node}`, so a node click silently
    // dropped `?system=` from the URL even after the fix above adds it on
    // selector change.
    setSearchParams({ system: systemId, node: nodeId })
  }

  const selectedNode = data?.nodes.find((n) => n.node_id === selectedNodeId) ?? null

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
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <EvidenceGraphCanvas
                nodes={data.nodes}
                edges={data.edges}
                onNodeClick={handleNodeClick}
                selectedNodeId={selectedNodeId}
              />
            </div>
            <div className="space-y-4">
              <NodeDetailPanel node={selectedNode} />
              <BlastRadiusPanel result={blastResult} loading={blastLoading} error={blastError} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
