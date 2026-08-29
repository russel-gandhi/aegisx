import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Knowledge, { HIGHLIGHTED_ROW_STYLE } from '../pages/Knowledge'
import BlastRadius from '../pages/BlastRadius'
import type { DocumentListResult, DocumentSummary, EvidenceGraphResponse } from '../lib/api'

/**
 * D-13 deep-link landing (Phase 06.1, plan 06.1-08, Task 3): both
 * destinations a Copilot answer or an evidence citation can send a user to
 * honour the params the link sends, and degrade to the page's ordinary
 * default for a param that names nothing. One named test per <behavior>
 * bullet.
 *
 * Blast Radius bullets assert against which `system_id`/`node_id`
 * `fetchEvidenceGraph`/`fetchBlastRadius` were called with, not against
 * rendered graph internals, so these tests do not depend on React Flow
 * canvas rendering (per the plan's own guidance).
 */

vi.mock('../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/api')>()
  return {
    ...actual,
    listDocuments: vi.fn(),
    fetchEvidenceGraph: vi.fn(),
    fetchBlastRadius: vi.fn(),
  }
})

import { listDocuments, fetchEvidenceGraph, fetchBlastRadius } from '../lib/api'

const mockListDocuments = vi.mocked(listDocuments)
const mockFetchEvidenceGraph = vi.mocked(fetchEvidenceGraph)
const mockFetchBlastRadius = vi.mocked(fetchBlastRadius)

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

function emptyGraph(systemId: string): EvidenceGraphResponse {
  return { system_id: systemId, nodes: [], edges: [] }
}

beforeEach(() => {
  mockListDocuments.mockReset()
  mockFetchEvidenceGraph.mockReset()
  mockFetchBlastRadius.mockReset()
  mockListDocuments.mockResolvedValue({ system_id: null, documents: [] } satisfies DocumentListResult)
  mockFetchEvidenceGraph.mockImplementation((systemId: string) =>
    Promise.resolve(emptyGraph(systemId)),
  )
  mockFetchBlastRadius.mockResolvedValue({
    system_id: 'GXP-MFG-DEMO-01',
    source_node_id: 'RISK:RISK-7',
    direct_dependencies: [],
    indirect_dependencies: [],
    affected_requirements: [],
    affected_tests: [],
    affected_risks: [],
    affected_changes: [],
    affected_controls: [],
    affected_systems: [],
    potential_gxp_impact: 'LOW',
    highest_impact_downstream: null,
  })
})

function renderKnowledgeAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Knowledge />
    </MemoryRouter>,
  )
}

function renderBlastRadiusAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <BlastRadius />
    </MemoryRouter>,
  )
}

describe('Knowledge deep-link landing -- ?system= preselects the system selector', () => {
  it('preselects BUS-IT-DEMO-02 instead of the default (no selection)', async () => {
    renderKnowledgeAt('/knowledge?system=BUS-IT-DEMO-02')
    await waitFor(() => {
      expect(mockListDocuments).toHaveBeenCalled()
    })
    const select = screen.getByTestId('knowledge-system-select') as HTMLSelectElement
    expect(select.value).toBe('BUS-IT-DEMO-02')
  })
})

describe('Knowledge deep-link landing -- ?document= highlights the matching row', () => {
  it('renders the row for DOC-A with HIGHLIGHTED_ROW_STYLE and no other row highlighted', async () => {
    mockListDocuments.mockResolvedValueOnce({
      system_id: null,
      documents: [
        fixtureDocument({ document_id: 'DOC-A', title: 'urs_extract.md' }),
        fixtureDocument({ document_id: 'DOC-B', title: 'sop.pdf' }),
      ],
    })

    renderKnowledgeAt('/knowledge?system=GXP-MFG-DEMO-01&document=DOC-A')

    await waitFor(() => {
      expect(screen.getByTestId('knowledge-source-row-DOC-A')).toBeInTheDocument()
    })

    const highlightedRow = screen.getByTestId('knowledge-source-row-DOC-A')
    const otherRow = screen.getByTestId('knowledge-source-row-DOC-B')
    expect(highlightedRow.className).toContain(HIGHLIGHTED_ROW_STYLE)
    expect(otherRow.className).not.toContain(HIGHLIGHTED_ROW_STYLE)
  })
})

describe('Knowledge deep-link landing -- ?document= for an unknown id', () => {
  it('renders the source list normally with no row highlighted and no error state', async () => {
    mockListDocuments.mockResolvedValueOnce({
      system_id: null,
      documents: [fixtureDocument({ document_id: 'DOC-A', title: 'urs_extract.md' })],
    })

    renderKnowledgeAt('/knowledge?document=DOC-UNKNOWN')

    await waitFor(() => {
      expect(screen.getByTestId('knowledge-source-row-DOC-A')).toBeInTheDocument()
    })
    const row = screen.getByTestId('knowledge-source-row-DOC-A')
    expect(row.className).not.toContain(HIGHLIGHTED_ROW_STYLE)
    expect(screen.queryByText(/error/i)).toBeNull()
  })
})

describe('Knowledge deep-link landing -- ?system= not in KNOWLEDGE_SYSTEM_IDS', () => {
  it('is ignored, and the default (no selection) is used', async () => {
    renderKnowledgeAt('/knowledge?system=NOT-A-REAL-SYSTEM')
    await waitFor(() => {
      expect(mockListDocuments).toHaveBeenCalled()
    })
    const select = screen.getByTestId('knowledge-system-select') as HTMLSelectElement
    expect(select.value).toBe('')
  })
})

describe('Blast Radius deep-link landing -- ?system= loads that system\'s graph', () => {
  it('calls fetchEvidenceGraph with BUS-IT-DEMO-02, not the default system', async () => {
    renderBlastRadiusAt('/blast-radius?system=BUS-IT-DEMO-02')
    await waitFor(() => {
      expect(mockFetchEvidenceGraph).toHaveBeenCalledWith('BUS-IT-DEMO-02')
    })
    expect(mockFetchEvidenceGraph).not.toHaveBeenCalledWith('GXP-MFG-DEMO-01')
  })
})

describe('Blast Radius deep-link landing -- ?system=&?node= together', () => {
  it('loads the given system and arrives with the node already selected, surviving the system-change-clears-selection guard', async () => {
    renderBlastRadiusAt('/blast-radius?system=BUS-IT-DEMO-02&node=RISK%3ARISK-7')
    await waitFor(() => {
      expect(mockFetchEvidenceGraph).toHaveBeenCalledWith('BUS-IT-DEMO-02')
    })
    await waitFor(() => {
      expect(mockFetchBlastRadius).toHaveBeenCalledWith('BUS-IT-DEMO-02', 'RISK:RISK-7')
    })
  })
})

describe('Blast Radius deep-link landing -- ?system= not in SYSTEM_OPTIONS', () => {
  it('is ignored, and the default system is used', async () => {
    renderBlastRadiusAt('/blast-radius?system=NOT-A-REAL-SYSTEM')
    await waitFor(() => {
      expect(mockFetchEvidenceGraph).toHaveBeenCalledWith('GXP-MFG-DEMO-01')
    })
    expect(mockFetchEvidenceGraph).not.toHaveBeenCalledWith('NOT-A-REAL-SYSTEM')
  })
})

describe('Blast Radius deep-link landing -- ?node= with no ?system= (Phase 4 contract unchanged)', () => {
  it('loads the default system and still calls fetchBlastRadius with the deep-linked node', async () => {
    renderBlastRadiusAt('/blast-radius?node=RISK%3ARISK-7')
    await waitFor(() => {
      expect(mockFetchEvidenceGraph).toHaveBeenCalledWith('GXP-MFG-DEMO-01')
    })
    await waitFor(() => {
      expect(mockFetchBlastRadius).toHaveBeenCalledWith('GXP-MFG-DEMO-01', 'RISK:RISK-7')
    })
  })
})

describe('Deep-link params are initial values, not a lock', () => {
  it('Knowledge: changing the system selector by hand still works after landing on ?system=', async () => {
    renderKnowledgeAt('/knowledge?system=GXP-MFG-DEMO-01')
    await waitFor(() => {
      expect(mockListDocuments).toHaveBeenCalled()
    })
    const select = screen.getByTestId('knowledge-system-select') as HTMLSelectElement
    expect(select.value).toBe('GXP-MFG-DEMO-01')

    fireEvent.change(select, { target: { value: 'BUS-IT-DEMO-02' } })
    expect(select.value).toBe('BUS-IT-DEMO-02')
  })

  it('Blast Radius: changing the system selector by hand still works after landing on ?system=', async () => {
    renderBlastRadiusAt('/blast-radius?system=BUS-IT-DEMO-02')
    await waitFor(() => {
      expect(mockFetchEvidenceGraph).toHaveBeenCalledWith('BUS-IT-DEMO-02')
    })

    const systemSelect = screen.getByLabelText('System') as HTMLSelectElement
    expect(systemSelect.value).toBe('BUS-IT-DEMO-02')

    fireEvent.change(systemSelect, { target: { value: 'GXP-MFG-DEMO-01' } })

    await waitFor(() => {
      expect(mockFetchEvidenceGraph).toHaveBeenCalledWith('GXP-MFG-DEMO-01')
    })
  })
})
