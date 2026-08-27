import { ReactFlow, Background, Controls, type Node, type Edge } from '@xyflow/react'

// Bible Section 1.2 topology, fixed: C2 → A0 → [A1…A6 via Send] → C1 → A7 → C3.
// Placeholder nodes are laid out in the real topology now (not three anonymous boxes) so
// Phase 6's live agent-state streaming replaces node *colours* only, not this component.
const SPECIALIST_IDS = ['A1', 'A2', 'A3', 'A4', 'A5', 'A6']

const NODE_IDS = ['C2', 'A0', ...SPECIALIST_IDS, 'C1', 'A7', 'C3']

const NODE_POSITIONS: Record<string, { x: number; y: number }> = {
  C2: { x: 0, y: 200 },
  A0: { x: 220, y: 200 },
  ...Object.fromEntries(SPECIALIST_IDS.map((id, i) => [id, { x: 460, y: i * 80 }])),
  C1: { x: 700, y: 200 },
  A7: { x: 920, y: 200 },
  C3: { x: 1140, y: 200 },
}

const NODE_LABELS: Record<string, string> = {
  C2: 'C2\nPolicy & Safety Gateway',
  A0: 'A0\nOrchestrator',
  ...Object.fromEntries(SPECIALIST_IDS.map((id) => [id, id])),
  C1: 'C1\nEvidence & Grounding Verifier',
  A7: 'A7\nRemediation',
  C3: 'C3\nAction Gateway',
}

const edges: Edge[] = [
  { id: 'e-c2-a0', source: 'C2', target: 'A0' },
  ...SPECIALIST_IDS.map((id) => ({ id: `e-a0-${id}`, source: 'A0', target: id })),
  ...SPECIALIST_IDS.map((id) => ({ id: `e-${id}-c1`, source: id, target: 'C1' })),
  { id: 'e-c1-a7', source: 'C1', target: 'A7' },
  { id: 'e-a7-c3', source: 'A7', target: 'C3' },
]

export type NodeStatusValue = 'waiting' | 'running' | 'complete'

// D-01: the hero-query route bypasses the compiled graph entirely, so these
// nodes never run for that query type in v1 -- dimmed regardless of what
// `nodeStatus` says, per 06-UI-SPEC.md's Color table (Assumption A3:
// C2 is dimmed for the same reason A1/A3-A6 are).
const DIMMED_NODE_IDS = new Set(['C2', 'A1', 'A3', 'A4', 'A5', 'A6', 'A7', 'C3'])

// 06-UI-SPEC.md Color table, transcribed verbatim.
const STATUS_CLASSES: Record<NodeStatusValue, string> = {
  waiting: 'border-slate-700 bg-slate-800',
  running: 'border-amber-600 bg-amber-950/40',
  complete: 'border-emerald-600 bg-emerald-950/40',
}

export interface AgentTopologyCanvasProps {
  // Absent node ids default to 'waiting' -- this IS the pre-query loading
  // state (06-UI-SPEC.md UI Considerations), no separate spinner overlay.
  nodeStatus?: Record<string, NodeStatusValue>
  // D-01/06-UI-SPEC.md error row: on an SSE disconnect mid-query, the
  // caller stops updating `nodeStatus` and sets this true -- this
  // component takes no action to revert colors itself, it only renders
  // the banner and leaves nodes at whatever `nodeStatus` last held.
  disconnected?: boolean
}

function buildNodes(nodeStatus: Record<string, NodeStatusValue>): Node[] {
  return NODE_IDS.map((id) => {
    const status = nodeStatus[id] ?? 'waiting'
    const classNames = [STATUS_CLASSES[status], 'transition-colors', 'duration-300']
    if (DIMMED_NODE_IDS.has(id)) {
      classNames.push('opacity-40')
    }
    return {
      id,
      position: NODE_POSITIONS[id],
      data: { label: NODE_LABELS[id] },
      className: classNames.join(' '),
    }
  })
}

export default function AgentTopologyCanvas({
  nodeStatus = {},
  disconnected = false,
}: AgentTopologyCanvasProps) {
  const nodes = buildNodes(nodeStatus)

  return (
    <div>
      {disconnected && (
        <p
          data-testid="topology-disconnected-banner"
          className="mb-2 rounded border border-red-700 bg-red-950/40 p-2 text-sm text-red-300"
        >
          Live agent state disconnected — the topology below reflects the last known state. Ask
          again to reconnect.
        </p>
      )}
      {/* React Flow renders nothing inside a zero-height parent — the fixed height here is
          load-bearing, not decorative. */}
      <div style={{ height: 480 }} className="w-full rounded-lg border border-slate-800 bg-slate-900">
        <ReactFlow nodes={nodes} edges={edges} fitView>
          <Background />
          <Controls />
        </ReactFlow>
      </div>
      {/* D-03's literal required note -- do not paraphrase. */}
      <p className="mt-2 text-xs text-slate-500">A1, A3–A6 not yet implemented (v2)</p>
    </div>
  )
}
