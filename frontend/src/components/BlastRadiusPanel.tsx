import type { BlastRadiusResponse } from '../lib/api'

// Bible Section 14.3 places all graph traversal in the deterministic
// Python/NetworkX tier (T-04-09). This component performs no traversal and
// no count recomputation -- every number rendered below is the `length` of
// a server-supplied array, and a client-side recount would be a second,
// unverified source of truth. The component issues no fetch of its own.
export interface BlastRadiusPanelProps {
  result: BlastRadiusResponse | null
  loading: boolean
  error: string | null
}

const NONE_MARKER = 'None'

function Section({ label, items }: { label: string; items: string[] }) {
  return (
    <div className="mt-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      {items.length === 0 ? (
        <p className="mt-1 text-sm text-slate-500">{NONE_MARKER}</p>
      ) : (
        <ul className="mt-1 text-sm text-slate-100">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function BlastRadiusPanel({ result, loading, error }: BlastRadiusPanelProps) {
  if (loading) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <p className="text-slate-400">Loading blast radius...</p>
      </div>
    )
  }

  if (error !== null) {
    return (
      <div className="rounded-lg border border-red-700 bg-red-950/40 p-4">
        <p className="text-red-400">{error}</p>
      </div>
    )
  }

  if (result === null) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <p className="text-sm text-slate-400">
          Select a node on the graph to see its blast radius.
        </p>
      </div>
    )
  }

  // Plan 04-04's route contract: an empty blast radius for a present,
  // terminal node (every SYSTEM sink, every isolated node) is a
  // successful 200 response, not an error -- render it as a real,
  // meaningful result.
  const allEmpty =
    result.direct_dependencies.length === 0 &&
    result.indirect_dependencies.length === 0 &&
    result.affected_requirements.length === 0 &&
    result.affected_tests.length === 0 &&
    result.affected_risks.length === 0 &&
    result.affected_changes.length === 0 &&
    result.affected_controls.length === 0 &&
    result.affected_systems.length === 0 &&
    result.potential_gxp_impact === 'NONE'

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4" data-testid="blast-radius-panel">
      <h2 className="text-lg font-semibold text-slate-100">Impact Summary</h2>

      {/* Bible Section 14.3's own four-line impact summary shape, in its
          own order -- each the length of a server-supplied array except
          the impact grade itself. */}
      <dl className="mt-2 text-sm text-slate-100">
        <div className="flex justify-between">
          <dt>Direct dependencies</dt>
          <dd>{result.direct_dependencies.length}</dd>
        </div>
        <div className="flex justify-between">
          <dt>Indirect dependencies</dt>
          <dd>{result.indirect_dependencies.length}</dd>
        </div>
        <div className="flex justify-between">
          <dt>Affected controls</dt>
          <dd>{result.affected_controls.length}</dd>
        </div>
        <div className="flex justify-between">
          <dt>Potential GxP impact</dt>
          <dd>{result.potential_gxp_impact}</dd>
        </div>
      </dl>

      {allEmpty && (
        <p className="mt-3 text-sm text-slate-400">
          No downstream impact -- this node has no dependents in the evidence graph.
        </p>
      )}

      <Section label="Affected requirements" items={result.affected_requirements} />
      <Section label="Affected tests" items={result.affected_tests} />
      <Section label="Affected risks" items={result.affected_risks} />
      <Section label="Affected changes" items={result.affected_changes} />
      <Section label="Affected systems" items={result.affected_systems} />

      <div className="mt-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Highest-impact downstream
        </p>
        <p className="mt-1 text-sm text-slate-100">
          {result.highest_impact_downstream ?? NONE_MARKER}
        </p>
      </div>
    </div>
  )
}
