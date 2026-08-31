// Pure, framework-agnostic graph traversal over an already-fetched
// EvidenceGraphResponse (REMEDIATION-PLAN.md #5 / 06.1.1-RESEARCH.md D-07).
//
// The backend's blast_radius() traversal is not re-exposed as a path --
// only as flat node-id sets (direct/indirect/affected_*). "Highlight the
// path from a downstream node back to the selected origin" is real,
// bounded client-side graph work over data the response already proves is
// small enough to render in one React Flow canvas (single-digit-to-low-
// dozens of nodes for the demo systems, per 06.1.1-RESEARCH.md). A plain
// BFS over an adjacency map is sufficient -- no graph library needed.
//
// Deliberately UI-free: no React, no fetch, no store. Building it this way
// makes it trivially unit-testable in isolation and reusable the moment
// any future feature needs client-side traversal (multi-hop expansion,
// "shortest path between two arbitrary nodes"), not just this one
// highlight feature.

import type { EvidenceGraphEdge } from './api'

export type Adjacency = Map<string, string[]>

// Edges are treated as undirected for path-finding purposes: "why is this
// node connected to the origin" is a reachability question, not a
// directionality one, and the graph already carries `relation_type` on
// each edge for a caller that wants direction back out of the endpoints
// this function returns.
export function buildAdjacency(edges: EvidenceGraphEdge[]): Adjacency {
  const adjacency: Adjacency = new Map()
  const addEdge = (from: string, to: string) => {
    const existing = adjacency.get(from)
    if (existing) {
      existing.push(to)
    } else {
      adjacency.set(from, [to])
    }
  }
  for (const edge of edges) {
    addEdge(edge.source_id, edge.target_id)
    addEdge(edge.target_id, edge.source_id)
  }
  return adjacency
}

// Returns the node ids along the shortest path from `fromNodeId` to
// `toNodeId`, inclusive of both endpoints, or `null` if no path exists (the
// two nodes are in disconnected components) or either id is absent from
// the adjacency map. Returns `[fromNodeId]` when the two ids are equal.
export function shortestPath(
  adjacency: Adjacency,
  fromNodeId: string,
  toNodeId: string,
): string[] | null {
  if (fromNodeId === toNodeId) {
    return adjacency.has(fromNodeId) ? [fromNodeId] : null
  }
  if (!adjacency.has(fromNodeId) || !adjacency.has(toNodeId)) {
    return null
  }

  const previous = new Map<string, string>()
  const visited = new Set<string>([fromNodeId])
  const queue: string[] = [fromNodeId]

  while (queue.length > 0) {
    const current = queue.shift() as string
    if (current === toNodeId) {
      const path: string[] = [toNodeId]
      let step = toNodeId
      while (step !== fromNodeId) {
        step = previous.get(step) as string
        path.push(step)
      }
      return path.reverse()
    }
    for (const neighbor of adjacency.get(current) ?? []) {
      if (!visited.has(neighbor)) {
        visited.add(neighbor)
        previous.set(neighbor, current)
        queue.push(neighbor)
      }
    }
  }
  return null
}

// Convenience set-builder for a caller that only needs "is this edge on
// the highlighted path", e.g. to style react-flow edges -- built from
// shortestPath's own node-id array rather than duplicating the traversal.
export function pathEdgeKeys(path: string[]): Set<string> {
  const keys = new Set<string>()
  for (let i = 0; i < path.length - 1; i += 1) {
    keys.add(`${path[i]}->${path[i + 1]}`)
    keys.add(`${path[i + 1]}->${path[i]}`)
  }
  return keys
}
