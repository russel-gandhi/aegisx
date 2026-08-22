import type { EvidenceGraphNode } from '../lib/api'

// Pure presentation -- performs no fetch, holds no derived state. Renders
// exactly the node object it is handed by the parent's selection state
// (plan 04-05 interface_contract).
export interface NodeDetailPanelProps {
  node: EvidenceGraphNode | null
}

// Boolean and numeric property values are stringified explicitly so a
// `false` or `0` value renders visibly rather than disappearing behind a
// falsy-check-driven blank cell.
function stringifyPropertyValue(value: unknown): string {
  if (value === null || value === undefined) {
    return 'none'
  }
  if (typeof value === 'boolean') {
    return value ? 'true' : 'false'
  }
  if (typeof value === 'number') {
    return String(value)
  }
  return String(value)
}

export default function NodeDetailPanel({ node }: NodeDetailPanelProps) {
  if (node === null) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <p className="text-sm text-slate-400">Click a node on the graph to see its detail.</p>
      </div>
    )
  }

  const propertyEntries = Object.entries(node.properties)

  return (
    <div
      className="rounded-lg border border-slate-800 bg-slate-900 p-4"
      data-testid="node-detail-panel"
    >
      <h2 className="text-lg font-semibold text-slate-100">
        {node.node_type}: {node.entity_id}
      </h2>
      {propertyEntries.length === 0 ? (
        <p className="mt-2 text-sm text-slate-400">No properties recorded for this node.</p>
      ) : (
        <dl className="mt-2 text-sm text-slate-300">
          {propertyEntries.map(([key, value]) => (
            <div key={key} className="mt-1 flex gap-2">
              <dt className="font-medium text-slate-400">{key}:</dt>
              <dd className="text-slate-100">{stringifyPropertyValue(value)}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  )
}
