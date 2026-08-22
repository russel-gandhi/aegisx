/**
 * REST client for the evidence-graph and assurance-card backend contracts
 * (SENT-3-01/GRAPH-03; SENT-3-05/EVID-03).
 *
 * Mirrors `backend/app/routes/evidence_graph.py` exactly:
 *   - GET  /api/systems/{system_id}/evidence-graph -> EvidenceGraphResponse
 *   - POST /api/systems/{system_id}/evidence-graph/rebuild -> EvidenceGraphRebuildResponse
 *
 * And `backend/app/routes/findings.py` (plan 04-03):
 *   - GET  /api/systems/{system_id}/assurance-cards -> AssuranceCardsResponse
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

// Phase 4 (EVID-03, D-04): Assurance Card contract, mirroring
// `backend/app/schemas.py`'s DeterministicCheck/AssuranceCard/
// AssuranceCardsResponse field for field.
export interface DeterministicCheckData {
  check_name: string
  passed: boolean
  db_record_found: boolean
  opa_corroborated: boolean
  opa_rule_ids: string[]
}

export interface AssuranceCardData {
  finding_id: string
  claim: string
  evidence_ids: string[]
  regulatory_citations: string[]
  deterministic_check: DeterministicCheckData
  confidence: string
  alcoa_score: Record<string, boolean>
  model_attribution: string
}

export interface AssuranceCardsResponse {
  system_id: string
  cards: AssuranceCardData[]
}

export function fetchAssuranceCards(systemId: string): Promise<AssuranceCardsResponse> {
  return apiGet<AssuranceCardsResponse>(
    `/api/systems/${encodeURIComponent(systemId)}/assurance-cards`,
  )
}
