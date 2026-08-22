import { ReactFlow, Background, Controls, type Node, type Edge } from '@xyflow/react'
import type { EvidenceGraphNode, EvidenceGraphEdge } from '../lib/api'

export interface EvidenceGraphCanvasProps {
  nodes: EvidenceGraphNode[]
  edges: EvidenceGraphEdge[]
  // Plan 04-05: click-through to a node's detail and blast radius. The
  // callback receives only the node id string, not the raw React Flow
  // event/node object -- the parent owns selection state, this component
  // still holds none of its own.
  onNodeClick?: (nodeId: string) => void
  selectedNodeId?: string | null
}

// D-05 scopes this phase to basic rendering -- a deterministic index-based
// grid, not a force-directed or dagre layout. Plan 04-05 may replace this
// with a real layout algorithm; this component's job here is only to
// prove the server-trusted data renders, never to invent a relationship
// (the graph edges are already-computed, real data by the time they reach
// this pure presentational component).
const COLUMN_STEP = 220
const ROW_STEP = 120
const COLUMNS = 6

function toFlowNodes(apiNodes: EvidenceGraphNode[], selectedNodeId?: string | null): Node[] {
  return apiNodes.map((n, i) => {
    const isSelected = n.node_id === selectedNodeId
    return {
      id: n.node_id,
      position: { x: (i % COLUMNS) * COLUMN_STEP, y: Math.floor(i / COLUMNS) * ROW_STEP },
      // label is the node id itself ("{node_type}:{entity_id}") -- combines
      // the type and entity id in one string and satisfies the acceptance
      // criterion that a node's rendered label contains its node_id.
      data: { label: n.node_id },
      // Selection indicator only (D-05): React Flow's own `selected` flag
      // plus a thicker border. No node-type colour coding beyond the
      // basic differentiation already present, and no Bible Section 10.3
      // pulse highlight -- both explicitly deferred to Phase 6.
      selected: isSelected,
      style: isSelected ? { borderWidth: 3 } : undefined,
    }
  })
}

function toFlowEdges(apiEdges: EvidenceGraphEdge[]): Edge[] {
  return apiEdges.map((e) => ({
    id: `${e.source_id}-${e.relation_type}-${e.target_id}`,
    source: e.source_id,
    target: e.target_id,
    label: e.relation_type,
  }))
}

// Pure presentation -- performs no fetch and no traversal. Renders
// already-computed, server-trusted data only (04-RESEARCH.md's
// Architectural Responsibility Map). `onNodeClick` and `selectedNodeId`
// are the only two things plan 04-05 adds; the component still owns no
// selection state and issues no request of its own.
export default function EvidenceGraphCanvas({
  nodes,
  edges,
  onNodeClick,
  selectedNodeId,
}: EvidenceGraphCanvasProps) {
  const flowNodes = toFlowNodes(nodes, selectedNodeId)
  const flowEdges = toFlowEdges(edges)

  return (
    // React Flow renders nothing inside a zero-height parent -- the fixed
    // height here is load-bearing, not decorative (mirrors
    // AgentTopologyCanvas.tsx).
    <div style={{ height: 480 }} className="w-full rounded-lg border border-slate-800 bg-slate-900">
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        fitView
        onNodeClick={onNodeClick ? (_event, node) => onNodeClick(node.id) : undefined}
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  )
}
