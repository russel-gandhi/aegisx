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

// One node_type -> accent colour mapping, the single source of truth for
// "what a node means visually" (REMEDIATION-PLAN.md #5). Exported so any
// other view that renders these node types (a detail panel, a legend) can
// reuse the exact same mapping instead of a second component independently
// deciding what a node type looks like. A type not in this table (an
// entity kind added later without a matching design decision) falls back
// to the neutral colour rather than silently rendering unstyled.
export const NODE_TYPE_COLORS: Record<string, string> = {
  SYSTEM: '#38d7ff', // --color-accent-2
  REQUIREMENT: '#9a7bff', // --color-violet
  TEST_CASE: '#2fd889', // --color-mint
  RISK: '#ff5449', // --color-red
  CHANGE: '#ffb020', // --color-amber
  CONTROL: '#ff8a3d', // --color-orange
  DOCUMENT: 'rgba(243, 245, 251, 0.5)', // --color-ink-faint-ish
}
const NODE_TYPE_COLOR_DEFAULT = 'rgba(243, 245, 251, 0.35)'

export function nodeAccentColor(nodeType: string): string {
  return NODE_TYPE_COLORS[nodeType] ?? NODE_TYPE_COLOR_DEFAULT
}

// Prefers a human-readable field already present on the node's own
// properties (whichever the domain table actually populates) over the raw
// "{node_type}:{entity_id}" id string. Every existing fixture/seed record
// in this codebase has no such field yet, so this always falls back to the
// id today -- the fallback, not the preference, is what every current
// caller actually exercises, which is why this doesn't require a schema
// change to add: it activates automatically the day a domain table starts
// populating a title/name-shaped property.
function humanReadableLabel(n: EvidenceGraphNode): string {
  const props = n.properties as Record<string, unknown>
  const candidate = props?.title ?? props?.name
  return typeof candidate === 'string' && candidate.trim().length > 0
    ? candidate
    : n.node_id
}

function toFlowNodes(apiNodes: EvidenceGraphNode[], selectedNodeId?: string | null): Node[] {
  return apiNodes.map((n, i) => {
    const isSelected = n.node_id === selectedNodeId
    const accent = nodeAccentColor(n.node_type)
    return {
      id: n.node_id,
      position: { x: (i % COLUMNS) * COLUMN_STEP, y: Math.floor(i / COLUMNS) * ROW_STEP },
      // Human-readable label when the node's own properties carry one
      // (title/name/description); otherwise the raw node_id, exactly as
      // before -- every current fixture takes this path, so existing
      // assertions on node_id appearing in the rendered text are
      // unaffected (REMEDIATION-PLAN.md #5).
      data: { label: humanReadableLabel(n) },
      // Selection indicator (thicker border) plus a node_type-derived
      // accent colour via `nodeAccentColor` -- one shared source of truth
      // instead of the canvas and any future detail view each deciding
      // independently what a node type means visually.
      selected: isSelected,
      style: {
        borderWidth: isSelected ? 3 : 1,
        borderColor: accent,
        borderStyle: 'solid',
      },
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
    <div style={{ height: 480 }} className="w-full overflow-hidden rounded-xl border border-white/[0.08] bg-[#080b13]">
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        fitView
        // Hides React Flow's own attribution watermark, which the MIT
        // license permits removing via this exact prop
        // (06.1.1-RESEARCH.md D-05: confirmed missing, one-line fix).
        proOptions={{ hideAttribution: true }}
        onNodeClick={onNodeClick ? (_event, node) => onNodeClick(node.id) : undefined}
      >
        <Background color="rgba(255,255,255,0.08)" />
        <Controls />
      </ReactFlow>
    </div>
  )
}
