import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import EvidenceView, {
  WHY_SELECTED_PREFIX,
  INSUFFICIENT_EVIDENCE_COPY,
  VISIBLE_EVIDENCE_LIMIT,
} from '../components/EvidenceView'
import type { RetrievalEvidenceItem } from '../lib/api'

function fixtureItem(overrides: Partial<RetrievalEvidenceItem> = {}): RetrievalEvidenceItem {
  return {
    evidence_id: 'EVID-001',
    document_id: 'DOC-001',
    chunk_id: 'CHUNK-001',
    document_title: 'Fixture Validation Protocol',
    section: '3.2 Traceability',
    page: 5,
    content: 'Fixture chunk content.',
    retrieval_method: 'hybrid',
    dense_score: 0.71,
    bm25_score: 4.02,
    reranker_score: 0.88,
    parent_section: '3. Validation',
    graph_path: [],
    regulatory_citations: ['ANNEX11-S4-DOC-001'],
    evidence_type: 'document',
    why_selected: 'Matches the traceability requirement directly.',
    ...overrides,
  }
}

describe('EvidenceView -- insufficient evidence', () => {
  it('renders the insufficient-evidence copy and no evidence list', () => {
    render(
      <EvidenceView
        evidence={[]}
        evidenceSupport="INSUFFICIENT_EVIDENCE"
        insufficientEvidence
      />,
    )
    expect(screen.getByText(INSUFFICIENT_EVIDENCE_COPY)).toBeInTheDocument()
    expect(screen.queryByTestId('evidence-support-badge')).toBeNull()
    expect(screen.queryByTestId(/evidence-item-/)).toBeNull()
  })
})

describe('EvidenceView -- fixed section order', () => {
  it('renders SOURCE, SECTION/PAGE, RETRIEVAL METHOD, SCORES, and the why-selected line in order', () => {
    const item = fixtureItem()
    render(<EvidenceView evidence={[item]} evidenceSupport="HIGH" insufficientEvidence={false} />)

    const card = screen.getByTestId(`evidence-item-${item.evidence_id}`)
    const text = card.textContent ?? ''
    const sourceIdx = text.indexOf('SOURCE')
    const sectionIdx = text.indexOf('SECTION/PAGE')
    const methodIdx = text.indexOf('RETRIEVAL METHOD')
    const scoresIdx = text.indexOf('SCORES')
    const whyIdx = text.indexOf(WHY_SELECTED_PREFIX)

    expect(sourceIdx).toBeGreaterThanOrEqual(0)
    expect(sourceIdx).toBeLessThan(sectionIdx)
    expect(sectionIdx).toBeLessThan(methodIdx)
    expect(methodIdx).toBeLessThan(scoresIdx)
    expect(scoresIdx).toBeLessThan(whyIdx)
    expect(text).toContain(item.document_title)
  })
})

describe('EvidenceView -- missing fields shown as missing', () => {
  it('renders "no section" for a null section and "n/a" for a null page', () => {
    const item = fixtureItem({ section: null, page: null })
    render(<EvidenceView evidence={[item]} evidenceSupport="HIGH" insufficientEvidence={false} />)

    const card = screen.getByTestId(`evidence-item-${item.evidence_id}`)
    expect(card.textContent).toContain('no section')
    expect(card.textContent).toContain('n/a')
  })
})

describe('EvidenceView -- only server-sent scores render', () => {
  it('omits the keyword score row when bm25_score is null', () => {
    const item = fixtureItem({ bm25_score: null })
    render(<EvidenceView evidence={[item]} evidenceSupport="HIGH" insufficientEvidence={false} />)

    const card = screen.getByTestId(`evidence-item-${item.evidence_id}`)
    expect(card.textContent).not.toContain('Keyword')
    expect(card.textContent).toContain('Semantic 0.71')
    expect(card.textContent).toContain('Reranked 0.88')
  })
})

describe('EvidenceView -- evidence-support badge', () => {
  it('renders the correct label and style for a recognised band', () => {
    render(<EvidenceView evidence={[fixtureItem()]} evidenceSupport="HIGH" insufficientEvidence={false} />)
    const badge = screen.getByTestId('evidence-support-badge')
    expect(badge.textContent).toBe('High evidence support')
  })

  it('renders the raw string with neutral styling for an unrecognised band, never crashing or defaulting favorably', () => {
    render(
      <EvidenceView evidence={[fixtureItem()]} evidenceSupport="WEIRD_BAND" insufficientEvidence={false} />,
    )
    const badge = screen.getByTestId('evidence-support-badge')
    expect(badge.textContent).toBe('WEIRD_BAND')
    const panel = screen.getByTestId('evidence-view-panel')
    expect(panel.className).toContain('border-slate-700')
  })
})

describe('EvidenceView -- retrieval-method and evidence-type badges are neutral', () => {
  it('uses only slate-800/slate-300 classes for both badge kinds', () => {
    const item = fixtureItem()
    render(<EvidenceView evidence={[item]} evidenceSupport="HIGH" insufficientEvidence={false} />)

    const methodBadge = screen.getByTestId(`evidence-method-badge-${item.evidence_id}`)
    const typeBadge = screen.getByTestId(`evidence-type-badge-${item.evidence_id}`)
    expect(methodBadge.className).toContain('bg-slate-800')
    expect(methodBadge.className).toContain('text-slate-300')
    expect(typeBadge.className).toContain('bg-slate-800')
    expect(typeBadge.className).toContain('text-slate-300')
  })
})

describe('EvidenceView -- graph relationship items', () => {
  it('renders the "Graph relationship" type label and graph_path, with no page citation', () => {
    const item = fixtureItem({
      evidence_type: 'graph_relationship',
      retrieval_method: 'graph',
      graph_path: ['DOCUMENT:DOC-001', 'SYSTEM:GXP-MFG-DEMO-01'],
      section: null,
      page: null,
    })
    render(<EvidenceView evidence={[item]} evidenceSupport="HIGH" insufficientEvidence={false} />)

    const card = screen.getByTestId(`evidence-item-${item.evidence_id}`)
    expect(card.textContent).toContain('Graph relationship')
    expect(card.textContent).toContain('DOCUMENT:DOC-001')
    expect(card.textContent).not.toContain('SECTION/PAGE')
  })
})

describe('EvidenceView -- overflow backstop', () => {
  it('caps visible items at VISIBLE_EVIDENCE_LIMIT with a working "Show N more" expander, keeping all items in the DOM', () => {
    const items = Array.from({ length: 10 }, (_, i) =>
      fixtureItem({ evidence_id: `EVID-${i}`, document_title: `Fixture Doc ${i}` }),
    )
    render(<EvidenceView evidence={items} evidenceSupport="HIGH" insufficientEvidence={false} />)

    // All 10 present in the DOM throughout.
    items.forEach((item) => {
      expect(screen.getByTestId(`evidence-item-${item.evidence_id}`)).toBeInTheDocument()
    })

    const expander = screen.getByTestId('evidence-view-expander')
    expect(expander.textContent).toBe(`Show ${10 - VISIBLE_EVIDENCE_LIMIT} more`)

    // Exactly 5 visible (not collapsed) before clicking.
    const collapsedWrappers = items
      .slice(VISIBLE_EVIDENCE_LIMIT)
      .map((item) => screen.getByTestId(`evidence-item-${item.evidence_id}`).parentElement)
    collapsedWrappers.forEach((wrapper) => {
      expect(wrapper?.className).toContain('h-0')
    })

    fireEvent.click(expander)

    items.forEach((item) => {
      expect(screen.getByTestId(`evidence-item-${item.evidence_id}`)).toBeInTheDocument()
    })
    const expandedWrappers = items
      .slice(VISIBLE_EVIDENCE_LIMIT)
      .map((item) => screen.getByTestId(`evidence-item-${item.evidence_id}`).parentElement)
    expandedWrappers.forEach((wrapper) => {
      expect(wrapper?.className).not.toContain('h-0')
    })
  })
})

describe('EvidenceView -- pure presentation, no fetch/arithmetic/grading', () => {
  it('renders scores formatted to exactly 2 decimal places with no other arithmetic applied', () => {
    const item = fixtureItem({ dense_score: 0.7, bm25_score: 4, reranker_score: 0.885 })
    render(<EvidenceView evidence={[item]} evidenceSupport="HIGH" insufficientEvidence={false} />)
    const card = screen.getByTestId(`evidence-item-${item.evidence_id}`)
    expect(card.textContent).toContain('Semantic 0.70')
    expect(card.textContent).toContain('Keyword 4.00')
  })

  it('renders the model attribution subtext verbatim when provided', () => {
    render(
      <EvidenceView
        evidence={[fixtureItem()]}
        evidenceSupport="HIGH"
        insufficientEvidence={false}
        modelAttribution="gemini-2.5-flash"
      />,
    )
    expect(screen.getByText('Model: gemini-2.5-flash')).toBeInTheDocument()
  })
})
