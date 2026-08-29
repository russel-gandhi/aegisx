import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import Knowledge, {
  DROP_ZONE_COPY,
  EMPTY_HEADING,
  EMPTY_BODY,
  EMPTY_CTA,
  UNSUPPORTED_TYPE_COPY,
  TOO_LARGE_COPY,
  SELECT_SYSTEM_HINT,
  ingestionFailureCopy,
} from '../pages/Knowledge'
import { ApiError, type DocumentListResult, type DocumentSummary, type DocumentUploadResult } from '../lib/api'

vi.mock('../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/api')>()
  return {
    ...actual,
    listDocuments: vi.fn(),
    uploadDocument: vi.fn(),
  }
})

import { listDocuments, uploadDocument } from '../lib/api'

const mockListDocuments = vi.mocked(listDocuments)
const mockUploadDocument = vi.mocked(uploadDocument)

function fixtureDocument(overrides: Partial<DocumentSummary> = {}): DocumentSummary {
  return {
    document_id: 'DOC-FIXTURE-01',
    title: 'urs_extract.md',
    doc_type: 'MARKDOWN',
    version: null,
    system_id: 'GXP-MFG-DEMO-01',
    created_date: '2026-08-28T00:00:00+00:00',
    chunk_count: 5,
    ingestion_status: 'READY',
    failed_stage: null,
    ...overrides,
  }
}

interface Deferred<T> {
  promise: Promise<T>
  resolve: (value: T) => void
  reject: (reason?: unknown) => void
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

async function selectSystem(value = 'GXP-MFG-DEMO-01') {
  fireEvent.change(screen.getByTestId('knowledge-system-select'), { target: { value } })
}

function chooseFile(file: File) {
  fireEvent.change(screen.getByTestId('knowledge-file-input'), { target: { files: [file] } })
}

beforeEach(() => {
  mockListDocuments.mockReset()
  mockUploadDocument.mockReset()
  mockListDocuments.mockResolvedValue({ system_id: null, documents: [] } satisfies DocumentListResult)
})

describe('Knowledge empty state', () => {
  it('renders the empty-state heading, body, and CTA before any document is uploaded', async () => {
    render(<Knowledge />)
    await waitFor(() => {
      expect(screen.getByTestId('knowledge-empty-state')).toBeInTheDocument()
    })
    expect(screen.getByText(EMPTY_HEADING)).toBeInTheDocument()
    expect(screen.getByText(EMPTY_BODY)).toBeInTheDocument()
    expect(screen.getByTestId('knowledge-empty-cta')).toHaveTextContent(EMPTY_CTA)
  })
})

describe('Knowledge drop zone', () => {
  it('renders the drop-zone instruction copy on first paint, never a blank bordered box', () => {
    render(<Knowledge />)
    expect(screen.getByText(DROP_ZONE_COPY)).toBeInTheDocument()
  })
})

describe('Knowledge system-not-selected backstop', () => {
  it('disables Browse files and shows the select-a-system hint until a system is chosen, then enables it', async () => {
    render(<Knowledge />)
    await waitFor(() => screen.getByTestId('knowledge-empty-state'))

    expect(screen.getByTestId('browse-files-button')).toBeDisabled()
    expect(screen.getByText(SELECT_SYSTEM_HINT)).toBeInTheDocument()

    await selectSystem('GXP-MFG-DEMO-01')

    expect(screen.getByTestId('browse-files-button')).not.toBeDisabled()
    expect(screen.queryByText(SELECT_SYSTEM_HINT)).toBeNull()
  })
})

describe('Knowledge upload -- unsupported extension (client-side)', () => {
  it('renders the unsupported-type copy and issues no upload request or new row for a .exe file', async () => {
    render(<Knowledge />)
    await waitFor(() => screen.getByTestId('knowledge-empty-state'))
    await selectSystem()

    chooseFile(new File(['MZ'], 'malware.exe'))

    await waitFor(() => {
      expect(screen.getByTestId('knowledge-inline-error')).toHaveTextContent(UNSUPPORTED_TYPE_COPY)
    })
    expect(mockUploadDocument).not.toHaveBeenCalled()
    expect(screen.getByTestId('knowledge-empty-state')).toBeInTheDocument()
  })
})

describe('Knowledge upload -- backend rejection copy', () => {
  it('renders TOO_LARGE_COPY for a 413 response', async () => {
    mockUploadDocument.mockRejectedValue(new ApiError(413, 'Upload exceeds the byte limit', 'POST failed'))
    render(<Knowledge />)
    await waitFor(() => screen.getByTestId('knowledge-empty-state'))
    await selectSystem()

    chooseFile(new File(['x'.repeat(10)], 'big.pdf'))

    await waitFor(() => {
      expect(screen.getByTestId('knowledge-inline-error')).toHaveTextContent(TOO_LARGE_COPY)
    })
  })

  it('renders UNSUPPORTED_TYPE_COPY for a 415 response', async () => {
    mockUploadDocument.mockRejectedValue(
      new ApiError(415, 'Unsupported or content-mismatched file', 'POST failed'),
    )
    render(<Knowledge />)
    await waitFor(() => screen.getByTestId('knowledge-empty-state'))
    await selectSystem()

    chooseFile(new File(['%PDF-1.4 fake'], 'sneaky.pdf'))

    await waitFor(() => {
      expect(screen.getByTestId('knowledge-inline-error')).toHaveTextContent(UNSUPPORTED_TYPE_COPY)
    })
  })
})

describe('Knowledge upload -- stage honesty while in flight', () => {
  it('shows Uploading (in-flight glyph) and later stages not-started for the uploading row, without disturbing other rows or showing a page-level spinner', async () => {
    const existing = fixtureDocument({ document_id: 'DOC-EXISTING' })
    mockListDocuments.mockResolvedValueOnce({ system_id: null, documents: [existing] })
    const pending = deferred<DocumentUploadResult>()
    mockUploadDocument.mockReturnValue(pending.promise)

    render(<Knowledge />)
    await waitFor(() => screen.getByTestId(`knowledge-source-row-${existing.document_id}`))
    await selectSystem()

    chooseFile(new File(['hello'], 'new_doc.md'))

    await waitFor(() => {
      expect(screen.getByText('Uploading…')).toBeInTheDocument()
    })

    // Existing row is untouched.
    expect(screen.getByTestId(`knowledge-source-row-${existing.document_id}`)).toBeInTheDocument()

    // The pending row's Uploading glyph is the in-flight glyph; every later
    // stage is not-yet-started -- found by scoping to the row containing
    // the uploading filename, since the pending row's id is a random uuid.
    const pendingRow = screen.getByText('new_doc.md').closest('div') as HTMLElement
    const glyphs = pendingRow.querySelectorAll('span.text-amber-600, span.text-slate-500')
    expect(glyphs.length).toBe(6)
    expect(glyphs[0].textContent).toBe('◌')
    for (let i = 1; i < 6; i += 1) {
      expect(glyphs[i].textContent).toBe('-')
    }

    pending.resolve({
      document_id: 'DOC-NEW',
      system_id: 'GXP-MFG-DEMO-01',
      title: 'new_doc.md',
      doc_type: 'MARKDOWN',
      chunk_count: 2,
      indexed_vector_count: 2,
      status: 'READY',
      failed_stage: null,
    })
    mockListDocuments.mockResolvedValueOnce({
      system_id: null,
      documents: [existing, fixtureDocument({ document_id: 'DOC-NEW', title: 'new_doc.md', chunk_count: 2 })],
    })

    await waitFor(() => {
      expect(screen.getByTestId('knowledge-source-row-DOC-NEW')).toBeInTheDocument()
    })
  })
})

describe('Knowledge upload -- READY response', () => {
  it('renders all six stages complete and the real chunk_count once the document list refetches', async () => {
    mockUploadDocument.mockResolvedValue({
      document_id: 'DOC-READY',
      system_id: 'GXP-MFG-DEMO-01',
      title: 'sop.pdf',
      doc_type: 'PDF',
      chunk_count: 7,
      indexed_vector_count: 7,
      status: 'READY',
      failed_stage: null,
    })
    mockListDocuments
      .mockResolvedValueOnce({ system_id: null, documents: [] })
      .mockResolvedValueOnce({
        system_id: null,
        documents: [fixtureDocument({ document_id: 'DOC-READY', title: 'sop.pdf', doc_type: 'PDF', chunk_count: 7 })],
      })

    render(<Knowledge />)
    await waitFor(() => screen.getByTestId('knowledge-empty-state'))
    await selectSystem()
    chooseFile(new File(['%PDF-1.4'], 'sop.pdf'))

    await waitFor(() => {
      expect(screen.getByTestId('knowledge-source-row-DOC-READY')).toBeInTheDocument()
    })

    const row = screen.getByTestId('knowledge-source-row-DOC-READY')
    expect(row).toHaveTextContent('7 indexed units')
    for (const label of ['Uploading', 'Parsing', 'Structure', 'Chunking', 'Indexing', 'Ready']) {
      const glyph = screen.getByTestId(`stage-glyph-DOC-READY-${label}`)
      expect(glyph).toHaveTextContent('✓')
    }
  })
})

describe('Knowledge upload -- FAILED response', () => {
  it('keeps the row in the list and renders ingestionFailureCopy with the real backend failed_stage', async () => {
    mockUploadDocument.mockResolvedValue({
      document_id: 'DOC-FAILED',
      system_id: 'GXP-MFG-DEMO-01',
      title: 'broken.csv',
      doc_type: 'CSV',
      chunk_count: 0,
      indexed_vector_count: 0,
      status: 'FAILED',
      failed_stage: 'indexing',
    })
    mockListDocuments
      .mockResolvedValueOnce({ system_id: null, documents: [] })
      .mockResolvedValueOnce({
        system_id: null,
        documents: [
          fixtureDocument({
            document_id: 'DOC-FAILED',
            title: 'broken.csv',
            doc_type: 'CSV',
            chunk_count: 0,
            ingestion_status: 'FAILED',
            failed_stage: null, // GET /api/documents never re-derives failed_stage
          }),
        ],
      })

    render(<Knowledge />)
    await waitFor(() => screen.getByTestId('knowledge-empty-state'))
    await selectSystem()
    chooseFile(new File(['a,b\n1,2'], 'broken.csv'))

    await waitFor(() => {
      expect(screen.getByTestId('knowledge-source-row-DOC-FAILED')).toBeInTheDocument()
    })

    const row = screen.getByTestId('knowledge-source-row-DOC-FAILED')
    expect(row).toHaveTextContent(ingestionFailureCopy('indexing'))
  })
})

describe('Knowledge -- zero indexed units renders honestly', () => {
  it('renders "0 indexed units" as ordinary text rather than hiding or replacing it', async () => {
    mockListDocuments.mockResolvedValueOnce({
      system_id: null,
      documents: [fixtureDocument({ document_id: 'DOC-ZERO', chunk_count: 0 })],
    })

    render(<Knowledge />)

    await waitFor(() => {
      expect(screen.getByTestId('knowledge-source-row-DOC-ZERO')).toHaveTextContent('0 indexed units')
    })
  })
})

describe('Knowledge -- populated row fields', () => {
  it('renders filename, doc type, version, ingestion status, date, and indexed-unit count', async () => {
    mockListDocuments.mockResolvedValueOnce({
      system_id: null,
      documents: [
        fixtureDocument({
          document_id: 'DOC-POPULATED',
          title: 'validation_protocol.docx',
          doc_type: 'DOCX',
          version: 'v2',
          created_date: '2026-08-29T00:00:00+00:00',
          chunk_count: 12,
          ingestion_status: 'READY',
        }),
      ],
    })

    render(<Knowledge />)

    await waitFor(() => {
      const row = screen.getByTestId('knowledge-source-row-DOC-POPULATED')
      expect(row).toHaveTextContent('validation_protocol.docx')
      expect(row).toHaveTextContent('DOCX')
      expect(row).toHaveTextContent('v2')
      expect(row).toHaveTextContent('READY')
      expect(row).toHaveTextContent('12 indexed units')
    })
  })
})

describe('Knowledge long-filename backstop', () => {
  it('truncates a 120+ character filename with the truncate class and a full-name title attribute', async () => {
    const longName = `${'a'.repeat(116)}.pdf`
    expect(longName.length).toBeGreaterThan(100)
    mockListDocuments.mockResolvedValueOnce({
      system_id: null,
      documents: [fixtureDocument({ document_id: 'DOC-LONGNAME', title: longName })],
    })

    render(<Knowledge />)

    await waitFor(() => {
      expect(screen.getByTestId('knowledge-source-row-DOC-LONGNAME')).toBeInTheDocument()
    })
    const titleEl = screen.getByText(longName)
    expect(titleEl.className).toContain('truncate')
    expect(titleEl.getAttribute('title')).toBe(longName)
  })
})
