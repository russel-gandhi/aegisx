/**
 * REST client for the evidence-graph backend contract (SENT-3-01, GRAPH-03).
 *
 * Mirrors `backend/app/routes/evidence_graph.py` exactly:
 *   - GET  /api/systems/{system_id}/evidence-graph -> EvidenceGraphResponse
 *   - POST /api/systems/{system_id}/evidence-graph/rebuild -> EvidenceGraphRebuildResponse
 *
 * Follows `lib/ws.ts`'s conventions: a Vite env var with a default correct
 * for local development, kept out of `.env.example` (a cross-cutting file
 * BRANCHING.md §5 requires be changed in its own separate PR).
 */

const DEFAULT_API_BASE = 'http://127.0.0.1:8000'

function resolveApiBase(): string {
  const base = import.meta.env.VITE_API_BASE
  return typeof base === 'string' && base.length > 0 ? base : DEFAULT_API_BASE
}

export const API_BASE = resolveApiBase()

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`)
  if (!response.ok) {
    throw new Error(`GET ${path} failed with status ${response.status}`)
  }
  return (await response.json()) as T
}

export interface EvidenceGraphNode {
  node_id: string
  node_type: string
  entity_id: string
  properties: Record<string, unknown>
}

export interface EvidenceGraphEdge {
  source_id: string
  target_id: string
  relation_type: string
}

export interface EvidenceGraphResponse {
  system_id: string
  nodes: EvidenceGraphNode[]
  edges: EvidenceGraphEdge[]
}

export function fetchEvidenceGraph(systemId: string): Promise<EvidenceGraphResponse> {
  return apiGet<EvidenceGraphResponse>(
    `/api/systems/${encodeURIComponent(systemId)}/evidence-graph`,
  )
}
