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
      <div className="card p-4">
        <p className="text-sm text-ink-faint">Click a node on the graph to see its detail.</p>
      </div>
    )
  }

  const propertyEntries = Object.entries(node.properties)

  return (
    <div
      className="card p-4"
      data-testid="node-detail-panel"
    >
      <h2 className="eyebrow">{node.node_type}</h2>
      <p className="mt-0.5 font-mono text-[13px] text-ink">{node.entity_id}</p>
      {propertyEntries.length === 0 ? (
        <p className="mt-3 text-sm text-ink-faint">No properties recorded for this node.</p>
      ) : (
        <dl className="mt-3 space-y-1.5 text-sm">
          {propertyEntries.map(([key, value]) => (
            <div key={key} className="flex gap-2">
              <dt className="text-ink-muted">{key}:</dt>
              <dd className="font-medium text-ink">{stringifyPropertyValue(value)}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  )
}
