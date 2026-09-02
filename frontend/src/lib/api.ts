/**
 * REST client for the evidence-graph, assurance-card, and action/approval
 * backend contracts (SENT-3-01/GRAPH-03; SENT-3-05/EVID-03;
 * SENT-4-03/04/05, REM-01..REM-04, SAFE-01).
 *
 * Mirrors `backend/app/routes/evidence_graph.py` exactly:
 *   - GET  /api/systems/{system_id}/evidence-graph -> EvidenceGraphResponse
 *   - POST /api/systems/{system_id}/evidence-graph/rebuild -> EvidenceGraphRebuildResponse
 *
 * And `backend/app/routes/findings.py` (plan 04-03; streaming sibling
 * added quick task 260826-p1q):
 *   - GET  /api/systems/{system_id}/assurance-cards -> AssuranceCardsResponse
 *   - GET  /api/systems/{system_id}/assurance-cards/stream -> text/event-stream
 *
 * And `backend/app/routes/actions.py` (plans 05-01/05-04/05-05):
 *   - POST /api/systems/{system_id}/findings/{finding_id}/generate-capa -> GenerateCapaResponse
 *   - GET  /api/actions -> ActionProposalsResponse
 *   - POST /api/actions/{proposal_id}/approve -> ActionProposalRecord
 *   - POST /api/actions/{proposal_id}/reject -> ActionProposalRecord
 *
 * And `backend/app/routes/copilot_query.py` (plan 06-01, Task 2, D-04):
 *   - POST /api/copilot/query -> CopilotQueryResponse
 *
 * And `backend/app/routes/system_signals.py` (plan 06-02, Task 1, D-07):
 *   - GET /api/systems/{system_id}/access-supplier-signals -> SystemSignalsResponse
 *
 * And `backend/app/routes/audit.py` (plan 05-03, this file's first caller
 * added plan 06-02, Task 2, D-07 mini-card #4):
 *   - GET /api/audit/verify -> ChainVerificationResponse
 *
 * And backend/app/routes/documents.py (plan 06.1-01/06.1-04): POST
 * /api/documents/upload -> DocumentUploadResult; GET /api/documents ->
 * DocumentListResult
 *
 * And backend/app/routes/copilot_query.py (plan 06.1-02, D-05): POST
 * /api/copilot/investigate -> CopilotInvestigateResult
 *
 * Follows `lib/ws.ts`'s conventions: a Vite env var with a default correct
 * for local development, kept out of `.env.example` (a cross-cutting file
 * BRANCHING.md §5 requires be changed in its own separate PR).
 */

import { identityHeaders } from './identity'

const DEFAULT_API_BASE = 'http://127.0.0.1:8000'

function resolveApiBase(): string {
  const base = import.meta.env.VITE_API_BASE
  return typeof base === 'string' && base.length > 0 ? base : DEFAULT_API_BASE
}

export const API_BASE = resolveApiBase()

// Carries the parsed FastAPI `detail` field separately from `message`, so
// a call site can distinguish a 403 (RBAC denial -- one UI-contract
// sentence) from a 5xx (a different sentence) rather than pattern-matching
// on `message` text.
export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (
      typeof body === 'object' &&
      body !== null &&
      'detail' in body &&
      typeof (body as { detail: unknown }).detail === 'string'
    ) {
      return (body as { detail: string }).detail
    }
  } catch {
    // Response body was not JSON (or had no `detail` field) -- fall
    // through to the generic status-only detail below.
  }
  return `Request failed with status ${response.status}`
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { headers: identityHeaders() })
  if (!response.ok) {
    const detail = await parseErrorDetail(response)
    throw new ApiError(response.status, detail, `GET ${path} failed with status ${response.status}`)
  }
  return (await response.json()) as T
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...identityHeaders(),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!response.ok) {
    const detail = await parseErrorDetail(response)
    throw new ApiError(response.status, detail, `POST ${path} failed with status ${response.status}`)
  }
  return (await response.json()) as T
}

// Phase 06.1 (plan 06.1-05, Task 1): multipart sibling of `apiPost`, for
// `POST /api/documents/upload`'s `multipart/form-data` body. Mirrors
// `apiPost` exactly -- same `response.ok` check, same `parseErrorDetail` +
// `ApiError` throw, same `(await response.json()) as T` return -- except
// the body is the caller's own `FormData` and NO `Content-Type` header is
// set: the browser derives the multipart boundary itself from the
// `FormData` instance, and setting `Content-Type` manually here would
// strip that boundary and break the request.
export async function apiUpload<T>(path: string, form: FormData): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { ...identityHeaders() },
    body: form,
  })
  if (!response.ok) {
    const detail = await parseErrorDetail(response)
    throw new ApiError(response.status, detail, `POST ${path} failed with status ${response.status}`)
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
  // 2026-09-02 production-incident remediation: fingerprint of the
  // policies/*.rego bundle this evaluation ran against. Optional (not
  // required in an object literal) so existing test fixtures that predate
  // this field keep compiling; a real API response always includes it.
  opa_bundle_hash?: string
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

// Streaming sibling of fetchAssuranceCards (quick task 260826-p1q). Mirrors
// backend/app/routes/findings.py's `_stream_cards` discriminated union on
// `event`, matching `lib/ws.ts`'s convention exactly.
export interface AssuranceCardFrame {
  event: 'card'
  card: AssuranceCardData
}

export interface AssuranceCardDoneFrame {
  event: 'done'
  system_id: string
  count: number
}

export interface AssuranceCardErrorFrame {
  event: 'error'
  detail: string
}

export type AssuranceCardStreamFrame =
  | AssuranceCardFrame
  | AssuranceCardDoneFrame
  | AssuranceCardErrorFrame

export interface AssuranceCardStreamHandlers {
  onCard: (card: AssuranceCardData) => void
  onDone: (systemId: string, count: number) => void
  onError: (detail: string) => void
}

/**
 * Streams assurance cards for `systemId` over SSE, reading the response
 * body with `fetch` + `body.getReader()` rather than `EventSource` -- the
 * browser `EventSource` API cannot set request headers at all, and this
 * route (like the blocking one) is read over `identityHeaders()` so it
 * stays RBAC-extensible (backend module docstring, Design Note 1).
 *
 * Buffers chunks and only parses frames terminated by a blank line ("\n\n")
 * -- a card's JSON can and will be split across two network chunks, so a
 * chunk is never parsed directly. Any complete trailing frame is flushed
 * when the reader reports done; an incomplete remainder is discarded.
 */
export async function streamAssuranceCards(
  systemId: string,
  handlers: AssuranceCardStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(
    `${API_BASE}/api/systems/${encodeURIComponent(systemId)}/assurance-cards/stream`,
    { headers: identityHeaders(), signal },
  )
  if (!response.ok) {
    const detail = await parseErrorDetail(response)
    throw new ApiError(
      response.status,
      detail,
      `GET assurance-cards/stream failed with status ${response.status}`,
    )
  }
  if (response.body === null) {
    throw new ApiError(0, 'empty stream body', 'assurance-cards/stream returned no body')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const dispatch = (rawFrame: string) => {
    const dataLine = rawFrame
      .split('\n')
      .find((line) => line.startsWith('data: '))
    if (dataLine === undefined) {
      return
    }
    const frame = JSON.parse(dataLine.slice('data: '.length)) as AssuranceCardStreamFrame
    if (frame.event === 'card') {
      handlers.onCard(frame.card)
    } else if (frame.event === 'done') {
      handlers.onDone(frame.system_id, frame.count)
    } else {
      handlers.onError(frame.detail)
    }
  }

  for (;;) {
    const { value, done } = await reader.read()
    if (done) {
      const remainder = buffer.trim()
      if (remainder.length > 0) {
        dispatch(remainder)
      }
      return
    }
    buffer += decoder.decode(value, { stream: true })
    let separatorIndex = buffer.indexOf('\n\n')
    while (separatorIndex !== -1) {
      const rawFrame = buffer.slice(0, separatorIndex)
      buffer = buffer.slice(separatorIndex + 2)
      if (rawFrame.trim().length > 0) {
        dispatch(rawFrame)
      }
      separatorIndex = buffer.indexOf('\n\n')
    }
  }
}

// Phase 4 (GRAPH-02, plan 04-05): Blast Radius contract, mirroring
// `backend/app/schemas.py`'s BlastRadiusResponse field for field (04-04's
// shipped model). One field per Bible Section 14.3 Graph Question.
export interface BlastRadiusResponse {
  system_id: string
  source_node_id: string
  direct_dependencies: string[]
  indirect_dependencies: string[]
  affected_requirements: string[]
  affected_tests: string[]
  affected_risks: string[]
  affected_changes: string[]
  affected_controls: string[]
  affected_systems: string[]
  potential_gxp_impact: string
  highest_impact_downstream: string | null
}

// `node_id` is a required query parameter on the backend (colon-bearing
// type-prefixed ids, e.g. "CHANGE:CR-2026-089", cannot be a bare path
// segment) -- `encodeURIComponent` applied to both arguments (critical
// finding 5).
export function fetchBlastRadius(systemId: string, nodeId: string): Promise<BlastRadiusResponse> {
  return apiGet<BlastRadiusResponse>(
    `/api/systems/${encodeURIComponent(systemId)}/blast-radius?node_id=${encodeURIComponent(nodeId)}`,
  )
}

// Phase 5 (REM-01..REM-04, SAFE-01, D-01..D-04): action-proposal /
// approval-workflow contract, mirroring `backend/app/schemas.py`'s
// ActionProposalRecord / ActionProposalsResponse / GenerateCapaResponse
// field for field. Nullable backend fields are `string | null`, never
// optional-and-defaulted -- a missing server field must stay visibly
// missing, never silently absent from the object shape.
export interface ActionProposalData {
  id: string
  action_type: string
  category: string
  target_system: string
  payload: Record<string, unknown>
  status: string
  justification: string | null
  finding_id: string | null
  model_id: string | null
  created_at: string | null
  approved_by: string | null
  approved_at: string | null
  execution_result: string | null
}

export interface ActionProposalsResponse {
  proposals: ActionProposalData[]
}

export interface GenerateCapaResponse {
  finding_id: string
  confidence: string
  proposal: ActionProposalData | null
  reason: string | null
}

export function fetchActionProposals(): Promise<ActionProposalsResponse> {
  return apiGet<ActionProposalsResponse>('/api/actions')
}

export function generateCapa(systemId: string, findingId: string): Promise<GenerateCapaResponse> {
  return apiPost<GenerateCapaResponse>(
    `/api/systems/${encodeURIComponent(systemId)}/findings/${encodeURIComponent(findingId)}/generate-capa`,
  )
}

export function approveAction(proposalId: string): Promise<ActionProposalData> {
  return apiPost<ActionProposalData>(`/api/actions/${encodeURIComponent(proposalId)}/approve`)
}

export function rejectAction(proposalId: string): Promise<ActionProposalData> {
  return apiPost<ActionProposalData>(`/api/actions/${encodeURIComponent(proposalId)}/reject`)
}

// Phase 6 (06-01 Task 2, D-04): Copilot non-hero-query contract, mirroring
// `backend/app/schemas.py`'s CopilotQueryRequest/CopilotQueryResponse field
// for field. `supported` is always `false` in v1 -- see
// `backend/app/routes/copilot_query.py`'s own module docstring.
export interface CopilotQueryResponse {
  supported: boolean
  blocked: boolean
  reason: string | null
}

export function queryCopilot(query: string): Promise<CopilotQueryResponse> {
  return apiPost<CopilotQueryResponse>('/api/copilot/query', { query })
}

// Phase 6 (06-02, Task 1, D-07 mini-cards #5/#6): access/supplier overdue
// signals contract, mirroring `backend/app/schemas.py`'s
// SystemSignalsResponse field for field.
export interface SystemSignalsResponse {
  system_id: string
  overdue_access_reviews: number
  overdue_suppliers: number
  overdue_supplier_names: string[]
}

export function fetchSystemSignals(systemId: string): Promise<SystemSignalsResponse> {
  return apiGet<SystemSignalsResponse>(
    `/api/systems/${encodeURIComponent(systemId)}/access-supplier-signals`,
  )
}

// Phase 6 (06-02, Task 2, D-07 mini-card #4): audit chain verification
// contract, mirroring `backend/app/schemas.py`'s ChainVerificationResponse
// field for field (05-03's shipped model; this is its first frontend
// caller).
export interface ChainVerificationResponse {
  status: string
  events_checked: number | null
  broken_at_index: number | null
  event_id: string | null
}

export function fetchChainVerification(): Promise<ChainVerificationResponse> {
  return apiGet<ChainVerificationResponse>('/api/audit/verify')
}

// Phase 06.1 (plan 06.1-05, Task 1): document ingestion + real-Copilot
// contracts, mirroring `backend/app/schemas.py`'s field set one-for-one --
// including nullability. A backend field typed `Optional[...] = None` is
// declared here as `| null` (never `?`), so a field the server sends as
// `null` stays visibly `null` in this type rather than silently degrading
// to `undefined`.

export interface DocumentUploadResult {
  document_id: string
  system_id: string
  title: string
  doc_type: string
  chunk_count: number
  indexed_vector_count: number
  status: string
  failed_stage: string | null
  duplicate: boolean
  quarantined: boolean
  quarantine_reason: string | null
}

export interface DocumentSummary {
  document_id: string
  title: string
  doc_type: string
  version: string | null
  system_id: string
  created_date: string | null
  chunk_count: number
  ingestion_status: string
  failed_stage: string | null
}

export interface DocumentListResult {
  system_id: string | null
  documents: DocumentSummary[]
}

// Bible Section 15.7's 16 named fields, transcribed one-for-one from
// `backend/app/schemas.py`'s `RetrievalEvidenceItem`. `retrieval_method` is
// one of "semantic" | "keyword" | "hybrid" | "parent_context" | "graph";
// `evidence_type` is one of "document" | "graph_relationship" -- both kept
// as `string` here (not a literal union) since the backend model itself
// declares them as plain `str`, and narrowing here would silently diverge
// from the source of truth.
export interface RetrievalEvidenceItem {
  evidence_id: string
  document_id: string
  chunk_id: string
  document_title: string
  section: string | null
  page: number | null
  content: string
  retrieval_method: string
  dense_score: number | null
  bm25_score: number | null
  reranker_score: number | null
  parent_section: string | null
  graph_path: string[]
  regulatory_citations: string[]
  evidence_type: string
  why_selected: string
}

export interface InvestigationStage {
  stage_id: string
  label: string
  status: string
  detail: string | null
}

// D-13: deliberately NO `url`/`href`/`path`/`link` field -- the destination
// address is assembled client-side (plan 06.1-08's route map) from `kind` +
// `target_id`, never sent by the server, so neither this backend nor an
// uploaded document's text can ever supply a navigable string. `kind` is a
// literal union (not `string`) because `NAVIGATION_KINDS` is a genuinely
// closed set on the backend (`field_validator` enforced), unlike
// `retrieval_method`/`evidence_type` above.
export interface NavigationTarget {
  kind: 'document' | 'graph_node'
  target_id: string
  label: string
  system_id: string
  reason: string
}

// Mirrors `backend/app/schemas.py`'s `AgentFinding` -- the same
// C1-verified-finding shape `AssuranceCardData` already carries a sibling
// view of, kept as its own type here (not reused) since the two Pydantic
// models are deliberately separate (schemas.py's own module docstring).
export interface CopilotFinding {
  finding_id: string
  claim: string
  regulatory_citations: string[]
  confidence_score: string
  evidence_ids: string[]
  alcoa_score: Record<string, boolean>
  model_attribution: string
}

export interface CopilotInvestigateResult {
  answer: string
  insufficient_evidence: boolean
  blocked: boolean
  blocked_reason: string | null
  evidence: RetrievalEvidenceItem[]
  stages: InvestigationStage[]
  findings: CopilotFinding[]
  verification_results: Record<string, unknown>
  evidence_support: string
  model_attribution: string
  navigation_target: NavigationTarget | null
}

export async function uploadDocument(file: File, systemId: string): Promise<DocumentUploadResult> {
  const form = new FormData()
  form.append('file', file)
  form.append('system_id', systemId)
  return apiUpload<DocumentUploadResult>('/api/documents/upload', form)
}

export async function listDocuments(systemId?: string): Promise<DocumentListResult> {
  return apiGet<DocumentListResult>(
    systemId ? `/api/documents?system_id=${encodeURIComponent(systemId)}` : '/api/documents',
  )
}

export async function investigateCopilot(query: string, systemId: string): Promise<CopilotInvestigateResult> {
  return apiPost<CopilotInvestigateResult>('/api/copilot/investigate', { query, system_id: systemId })
}

// Mirrors `backend/app/routes/suppliers.py`'s `SupplierRecord`/`SuppliersResponse`.
export interface SupplierRecord {
  supplier_id: string
  name: string
  status: string | null
  reassessment_due_date_ns: number | null
  is_overdue: boolean
  latest_assessment_result: string | null
  latest_assessment_date_ns: number | null
}

export interface SuppliersResponse {
  system_id: string
  suppliers: SupplierRecord[]
}

export function fetchSuppliers(systemId: string): Promise<SuppliersResponse> {
  return apiGet<SuppliersResponse>(`/api/systems/${encodeURIComponent(systemId)}/suppliers`)
}

// Mirrors `backend/app/routes/trust_centre.py`'s `LLMProviderInfo`/`TrustCentreResponse`.
export interface LLMProviderInfo {
  provider_key: string
  provider: string
  model: string
  use_for: string[]
  requires_api_key: boolean
}

export interface TrustCentreResponse {
  llm_cascade: LLMProviderInfo[]
  embedding_provider: LLMProviderInfo
  opa_policy_files: string[]
  opa_policy_count: number
  // 2026-09-02 production-incident remediation: honest, non-hardcoded
  // "policy bundle version" for the Trust Centre. Optional for the same
  // fixture-compatibility reason as DeterministicCheckData.opa_bundle_hash.
  opa_policy_bundle_hash?: string
}

export function fetchTrustCentre(): Promise<TrustCentreResponse> {
  return apiGet<TrustCentreResponse>('/api/trust-centre')
}
