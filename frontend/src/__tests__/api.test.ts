import { describe, it, expect, vi, afterEach } from 'vitest'
import {
  apiUpload,
  uploadDocument,
  listDocuments,
  investigateCopilot,
  type DocumentUploadResult,
  type DocumentListResult,
  type CopilotInvestigateResult,
  type RetrievalEvidenceItem,
  type NavigationTarget,
} from '../lib/api'
import { jsonResponse } from './helpers/sseFetch'

// Direct contract coverage for plan 06.1-05 Task 1's api.ts additions:
// apiUpload / uploadDocument / listDocuments / investigateCopilot, plus a
// field-name-parity check for the new interfaces against fixture response
// objects shaped exactly like the backend's own Pydantic models
// (backend/app/schemas.py).

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('apiUpload', () => {
  it('POSTs multipart/form-data with file and system_id parts, identity headers, and no Content-Type header', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    const form = new FormData()
    form.append('file', new File(['hello'], 'urs.md'))
    form.append('system_id', 'GXP-MFG-DEMO-01')

    await apiUpload('/api/documents/upload', form)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/api/documents/upload')
    expect(init.method).toBe('POST')
    expect(init.body).toBe(form)
    const headers = init.headers as Record<string, string>
    expect(headers['X-User-Id']).toBeDefined()
    expect(headers['X-User-Role']).toBeDefined()
    expect(Object.keys(headers)).not.toContain('Content-Type')
  })

  it('rejects with an ApiError carrying the backend detail for a 415/413/404 response', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({ detail: 'Unsupported or content-mismatched file' }, { ok: false, status: 415 }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ detail: 'Upload exceeds the byte limit' }, { ok: false, status: 413 }),
      )
      .mockResolvedValueOnce(jsonResponse({ detail: 'Unknown system_id: X' }, { ok: false, status: 404 }))
    vi.stubGlobal('fetch', fetchMock)

    const form = new FormData()
    await expect(apiUpload('/api/documents/upload', form)).rejects.toMatchObject({
      status: 415,
      detail: 'Unsupported or content-mismatched file',
    })
    await expect(apiUpload('/api/documents/upload', form)).rejects.toMatchObject({
      status: 413,
      detail: 'Upload exceeds the byte limit',
    })
    await expect(apiUpload('/api/documents/upload', form)).rejects.toMatchObject({
      status: 404,
      detail: 'Unknown system_id: X',
    })
  })

  it('degrades through parseErrorDetail for a non-JSON error body rather than throwing a parse error', async () => {
    const brokenJsonResponse = {
      ok: false,
      status: 500,
      json: async () => {
        throw new SyntaxError('Unexpected token')
      },
      body: null,
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(brokenJsonResponse))

    const form = new FormData()
    await expect(apiUpload('/api/documents/upload', form)).rejects.toMatchObject({
      status: 500,
      detail: 'Request failed with status 500',
    })
  })
})

describe('uploadDocument', () => {
  it('builds a FormData with file and system_id and delegates to apiUpload', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        document_id: 'DOC-1',
        system_id: 'GXP-MFG-DEMO-01',
        title: 'urs.md',
        doc_type: 'MARKDOWN',
        chunk_count: 3,
        indexed_vector_count: 3,
        status: 'READY',
        failed_stage: null,
        duplicate: false,
        quarantined: false,
        quarantine_reason: null,
      } satisfies DocumentUploadResult),
    )
    vi.stubGlobal('fetch', fetchMock)

    const file = new File(['hello'], 'urs.md')
    const result = await uploadDocument(file, 'GXP-MFG-DEMO-01')

    expect(result.status).toBe('READY')
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const form = init.body as FormData
    expect(form.get('file')).toBe(file)
    expect(form.get('system_id')).toBe('GXP-MFG-DEMO-01')
  })
})

describe('listDocuments', () => {
  it('GETs /api/documents with no argument', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ system_id: null, documents: [] } satisfies DocumentListResult),
    )
    vi.stubGlobal('fetch', fetchMock)

    await listDocuments()

    const [url] = fetchMock.mock.calls[0] as [string]
    expect(url.endsWith('/api/documents')).toBe(true)
  })

  it('appends a URL-encoded ?system_id= query param when given a system id', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ system_id: 'GXP-MFG-DEMO-01', documents: [] } satisfies DocumentListResult),
    )
    vi.stubGlobal('fetch', fetchMock)

    await listDocuments('GXP-MFG-DEMO-01')

    const [url] = fetchMock.mock.calls[0] as [string]
    expect(url).toContain('/api/documents?system_id=GXP-MFG-DEMO-01')
  })
})

describe('investigateCopilot', () => {
  it('POSTs JSON {query, system_id} to /api/copilot/investigate and returns the parsed result', async () => {
    const fixture: CopilotInvestigateResult = {
      answer: 'FIXTURE-ANSWER',
      insufficient_evidence: false,
      blocked: false,
      blocked_reason: null,
      evidence: [],
      stages: [],
      findings: [],
      verification_results: {},
      evidence_support: 'HIGH',
      model_attribution: 'FIXTURE-MODEL',
      navigation_target: null,
    }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(fixture))
    vi.stubGlobal('fetch', fetchMock)

    const result = await investigateCopilot('Is GXP-MFG-DEMO-01 audit ready?', 'GXP-MFG-DEMO-01')

    expect(result).toEqual(fixture)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/api/copilot/investigate')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toEqual({
      query: 'Is GXP-MFG-DEMO-01 audit ready?',
      system_id: 'GXP-MFG-DEMO-01',
    })
  })
})

describe('interface field-name parity with backend/app/schemas.py', () => {
  it('RetrievalEvidenceItem declares all 16 Section 15.7 fields', () => {
    const fixture: RetrievalEvidenceItem = {
      evidence_id: 'EV-1',
      document_id: 'DOC-1',
      chunk_id: 'CHUNK-1',
      document_title: 'FIXTURE-TITLE',
      section: null,
      page: null,
      content: 'FIXTURE-CONTENT',
      retrieval_method: 'hybrid',
      dense_score: null,
      bm25_score: null,
      reranker_score: null,
      parent_section: null,
      graph_path: [],
      regulatory_citations: [],
      evidence_type: 'document',
      why_selected: 'FIXTURE-REASON',
    }
    expect(Object.keys(fixture).sort()).toEqual(
      [
        'evidence_id',
        'document_id',
        'chunk_id',
        'document_title',
        'section',
        'page',
        'content',
        'retrieval_method',
        'dense_score',
        'bm25_score',
        'reranker_score',
        'parent_section',
        'graph_path',
        'regulatory_citations',
        'evidence_type',
        'why_selected',
      ].sort(),
    )
  })

  it('NavigationTarget declares kind/target_id/label/system_id/reason with no address-bearing field', () => {
    const fixture: NavigationTarget = {
      kind: 'document',
      target_id: 'DOC-1',
      label: 'FIXTURE-LABEL',
      system_id: 'GXP-MFG-DEMO-01',
      reason: 'FIXTURE-REASON',
    }
    expect(Object.keys(fixture).sort()).toEqual(
      ['kind', 'target_id', 'label', 'system_id', 'reason'].sort(),
    )
  })
})
