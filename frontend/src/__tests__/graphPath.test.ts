import { describe, it, expect } from 'vitest'
import { buildAdjacency, shortestPath, pathEdgeKeys } from '../lib/graphPath'
import type { EvidenceGraphEdge } from '../lib/api'

const EDGES: EvidenceGraphEdge[] = [
  { source_id: 'A', target_id: 'B', relation_type: 'RELATES_TO' },
  { source_id: 'B', target_id: 'C', relation_type: 'RELATES_TO' },
  { source_id: 'C', target_id: 'D', relation_type: 'RELATES_TO' },
  { source_id: 'A', target_id: 'E', relation_type: 'RELATES_TO' },
]

describe('buildAdjacency', () => {
  it('is undirected: each edge appears in both endpoints neighbor lists', () => {
    const adjacency = buildAdjacency(EDGES)
    expect(adjacency.get('A')).toEqual(expect.arrayContaining(['B', 'E']))
    expect(adjacency.get('B')).toEqual(expect.arrayContaining(['A', 'C']))
  })

  it('returns an empty adjacency for an empty edge list', () => {
    expect(buildAdjacency([]).size).toBe(0)
  })
})

describe('shortestPath', () => {
  it('finds the direct shortest path over multiple hops', () => {
    const adjacency = buildAdjacency(EDGES)
    expect(shortestPath(adjacency, 'A', 'D')).toEqual(['A', 'B', 'C', 'D'])
  })

  it('returns the single-node path when from and to are the same known node', () => {
    const adjacency = buildAdjacency(EDGES)
    expect(shortestPath(adjacency, 'A', 'A')).toEqual(['A'])
  })

  it('returns null for the same node id when it is not in the graph at all', () => {
    const adjacency = buildAdjacency(EDGES)
    expect(shortestPath(adjacency, 'ZZZ', 'ZZZ')).toBeNull()
  })

  it('returns null when either endpoint is absent from the graph', () => {
    const adjacency = buildAdjacency(EDGES)
    expect(shortestPath(adjacency, 'A', 'NOT-A-NODE')).toBeNull()
    expect(shortestPath(adjacency, 'NOT-A-NODE', 'A')).toBeNull()
  })

  it('returns null for two nodes in disconnected components', () => {
    const adjacency = buildAdjacency([
      { source_id: 'X', target_id: 'Y', relation_type: 'RELATES_TO' },
      { source_id: 'Z', target_id: 'W', relation_type: 'RELATES_TO' },
    ])
    expect(shortestPath(adjacency, 'X', 'W')).toBeNull()
  })

  it('finds the shorter of two possible routes', () => {
    // A-B-C-D is 3 hops; adding a direct A-D edge makes that the shortest.
    const adjacency = buildAdjacency([...EDGES, { source_id: 'A', target_id: 'D', relation_type: 'RELATES_TO' }])
    expect(shortestPath(adjacency, 'A', 'D')).toEqual(['A', 'D'])
  })
})

describe('pathEdgeKeys', () => {
  it('produces both directions for every consecutive pair on the path', () => {
    const keys = pathEdgeKeys(['A', 'B', 'C'])
    expect(keys.has('A->B')).toBe(true)
    expect(keys.has('B->A')).toBe(true)
    expect(keys.has('B->C')).toBe(true)
    expect(keys.has('C->B')).toBe(true)
    expect(keys.has('A->C')).toBe(false)
  })

  it('returns an empty set for a single-node path', () => {
    expect(pathEdgeKeys(['A']).size).toBe(0)
  })
})
