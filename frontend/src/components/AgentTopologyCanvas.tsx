import { ReactFlow, Background, Controls, type Node, type Edge } from '@xyflow/react'

// Bible Section 1.2 topology, fixed: C2 → A0 → [A1…A6 via Send] → C1 → A7 → C3.
// Placeholder nodes are laid out in the real topology now (not three anonymous boxes) so
// Phase 6's live agent-state streaming replaces node *colours* only, not this component.
const SPECIALIST_IDS = ['A1', 'A2', 'A3', 'A4', 'A5', 'A6']

const nodes: Node[] = [
  { id: 'C2', position: { x: 0, y: 200 }, data: { label: 'C2\nPolicy & Safety Gateway' } },
  { id: 'A0', position: { x: 220, y: 200 }, data: { label: 'A0\nOrchestrator' } },
  ...SPECIALIST_IDS.map((id, i) => ({
    id,
    position: { x: 460, y: i * 80 },
    data: { label: id },
  })),
  { id: 'C1', position: { x: 700, y: 200 }, data: { label: 'C1\nEvidence & Grounding Verifier' } },
  { id: 'A7', position: { x: 920, y: 200 }, data: { label: 'A7\nRemediation' } },
  { id: 'C3', position: { x: 1140, y: 200 }, data: { label: 'C3\nAction Gateway' } },
]

const edges: Edge[] = [
  { id: 'e-c2-a0', source: 'C2', target: 'A0' },
  ...SPECIALIST_IDS.map((id) => ({ id: `e-a0-${id}`, source: 'A0', target: id })),
  ...SPECIALIST_IDS.map((id) => ({ id: `e-${id}-c1`, source: id, target: 'C1' })),
  { id: 'e-c1-a7', source: 'C1', target: 'A7' },
  { id: 'e-a7-c3', source: 'A7', target: 'C3' },
]

export default function AgentTopologyCanvas() {
  return (
    // React Flow renders nothing inside a zero-height parent — the fixed height here is
    // load-bearing, not decorative.
    <div style={{ height: 480 }} className="w-full rounded-lg border border-slate-800 bg-slate-900">
      <ReactFlow nodes={nodes} edges={edges} fitView>
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  )
}
