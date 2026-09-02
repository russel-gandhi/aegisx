import { describe, it, expect } from 'vitest'
import { screen, fireEvent, render, type RenderResult } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactElement } from 'react'
import EvidenceView, {
  WHY_SELECTED_PREFIX,
  INSUFFICIENT_EVIDENCE_COPY,
  VISIBLE_EVIDENCE_LIMIT,
} from '../components/EvidenceView'
import type { RetrievalEvidenceItem } from '../lib/api'

const FIXTURE_SYSTEM_ID = 'GXP-MFG-DEMO-01'

// EvidenceView now renders react-router <Link>s (D-13) -- every render in
// this file goes through this helper so a MemoryRouter ancestor is always
// present. A single change to the helper, not to each test.
function renderWithRouter(ui: ReactElement): RenderResult {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

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
    renderWithRouter(
      <EvidenceView
        evidence={[]}
        evidenceSupport="INSUFFICIENT_EVIDENCE"
        insufficientEvidence
        systemId={FIXTURE_SYSTEM_ID}
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
    renderWithRouter(
      <EvidenceView
        evidence={[item]}
        evidenceSupport="HIGH"
        insufficientEvidence={false}
        systemId={FIXTURE_SYSTEM_ID}
      />,
    )

    const card = screen.getByTestId(`evidence-item-${item.evidence_id}`)
    // 2026-09-02 UI overhaul: section labels moved from literal ALL-CAPS
    // markup to Title Case text with a CSS-only `uppercase` transform
    // (still visually renders as caps -- jsdom's textContent reads the raw
    // markup, not the CSS transform). Case-insensitive search preserves
    // this test's real intent -- order -- without depending on markup
    // casing that's now a presentation detail, not the contract.
    const text = card.textContent ?? ''
    const upperText = text.toUpperCase()
    const sourceIdx = upperText.indexOf('SOURCE')
    const sectionIdx = upperText.indexOf('SECTION/PAGE')
    const methodIdx = upperText.indexOf('RETRIEVAL METHOD')
    const scoresIdx = upperText.indexOf('SCORES')
    const whyIdx = upperText.indexOf(WHY_SELECTED_PREFIX.toUpperCase())

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
    renderWithRouter(
      <EvidenceView
        evidence={[item]}
        evidenceSupport="HIGH"
        insufficientEvidence={false}
        systemId={FIXTURE_SYSTEM_ID}
      />,
    )

    const card = screen.getByTestId(`evidence-item-${item.evidence_id}`)
    expect(card.textContent).toContain('no section')
    expect(card.textContent).toContain('n/a')
  })
})

describe('EvidenceView -- only server-sent scores render', () => {
  it('omits the keyword score row when bm25_score is null', () => {
    const item = fixtureItem({ bm25_score: null })
    renderWithRouter(
      <EvidenceView
        evidence={[item]}
        evidenceSupport="HIGH"
        insufficientEvidence={false}
        systemId={FIXTURE_SYSTEM_ID}
      />,
    )

    const card = screen.getByTestId(`evidence-item-${item.evidence_id}`)
    expect(card.textContent).not.toContain('Keyword')
    expect(card.textContent).toContain('Semantic 0.71')
    expect(card.textContent).toContain('Reranked 0.88')
  })
})

describe('EvidenceView -- evidence-support badge', () => {
  it('renders the correct label and style for a recognised band', () => {
    renderWithRouter(
      <EvidenceView
        evidence={[fixtureItem()]}
        evidenceSupport="HIGH"
        insufficientEvidence={false}
        systemId={FIXTURE_SYSTEM_ID}
      />,
    )
    const badge = screen.getByTestId('evidence-support-badge')
    expect(badge.textContent).toBe('High evidence support')
  })

  it('renders the raw string with neutral styling for an unrecognised band, never crashing or defaulting favorably', () => {
    renderWithRouter(
      <EvidenceView
        evidence={[fixtureItem()]}
        evidenceSupport="WEIRD_BAND"
        insufficientEvidence={false}
        systemId={FIXTURE_SYSTEM_ID}
      />,
    )
    const badge = screen.getByTestId('evidence-support-badge')
    expect(badge.textContent).toBe('WEIRD_BAND')
    const panel = screen.getByTestId('evidence-view-panel')
    // 2026-09-02 UI overhaul: the neutral fallback token changed shape
    // (Tailwind slate literal -> the new design system's neutral token),
    // but the underlying contract this test guards is unchanged -- an
    // unrecognised band must never accidentally pick up a semantic
    // (mint/amber/orange/red) color, staying visually neutral instead.
    expect(panel.className).not.toMatch(/mint|amber|orange|(?<!bg-)red/)
    expect(panel.className).toContain('border-white/15')
  })
})

describe('EvidenceView -- retrieval-method and evidence-type badges are neutral', () => {
  it('uses only the neutral badge class for both badge kinds, never an accent hue', () => {
    const item = fixtureItem()
    renderWithRouter(
      <EvidenceView
        evidence={[item]}
        evidenceSupport="HIGH"
        insufficientEvidence={false}
        systemId={FIXTURE_SYSTEM_ID}
      />,
    )

    const methodBadge = screen.getByTestId(`evidence-method-badge-${item.evidence_id}`)
    const typeBadge = screen.getByTestId(`evidence-type-badge-${item.evidence_id}`)
    expect(methodBadge.className).toContain('badge-neutral')
    expect(methodBadge.className).not.toMatch(/badge-(blue|mint|amber|orange|red|violet)/)
    expect(typeBadge.className).toContain('badge-neutral')
    expect(typeBadge.className).not.toMatch(/badge-(blue|mint|amber|orange|red|violet)/)
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
    renderWithRouter(
      <EvidenceView
        evidence={[item]}
        evidenceSupport="HIGH"
        insufficientEvidence={false}
        systemId={FIXTURE_SYSTEM_ID}
      />,
    )

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
    renderWithRouter(
      <EvidenceView
        evidence={items}
        evidenceSupport="HIGH"
        insufficientEvidence={false}
        systemId={FIXTURE_SYSTEM_ID}
      />,
    )

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
    renderWithRouter(
      <EvidenceView
        evidence={[item]}
        evidenceSupport="HIGH"
        insufficientEvidence={false}
        systemId={FIXTURE_SYSTEM_ID}
      />,
    )
    const card = screen.getByTestId(`evidence-item-${item.evidence_id}`)
    expect(card.textContent).toContain('Semantic 0.70')
    expect(card.textContent).toContain('Keyword 4.00')
  })

  it('renders the model attribution subtext verbatim when provided', () => {
    renderWithRouter(
      <EvidenceView
        evidence={[fixtureItem()]}
        evidenceSupport="HIGH"
        insufficientEvidence={false}
        modelAttribution="gemini-2.5-flash"
        systemId={FIXTURE_SYSTEM_ID}
      />,
    )
    expect(screen.getByText('Model: gemini-2.5-flash')).toBeInTheDocument()
  })
})

describe('EvidenceView -- deep links (D-13, plan 06.1-08)', () => {
  it('renders a link with evidenceLinkLabel text for a document item that resolves to a href', () => {
    const item = fixtureItem({ evidence_type: 'document', document_id: 'DOC-A' })
    renderWithRouter(
      <EvidenceView
        evidence={[item]}
        evidenceSupport="HIGH"
        insufficientEvidence={false}
        systemId={FIXTURE_SYSTEM_ID}
      />,
    )
    const link = screen.getByTestId('evidence-item-link')
    expect(link.textContent).toBe('Open in Knowledge')
    expect(link.getAttribute('href')).toBe(
      `/knowledge?system=${FIXTURE_SYSTEM_ID}&document=DOC-A`,
    )
  })

  it('renders a link with evidenceLinkLabel text for a graph relationship item that resolves to a href', () => {
    const item = fixtureItem({
      evidence_type: 'graph_relationship',
      graph_path: ['DOCUMENT:DOC-A', 'RISK:RISK-7'],
      section: null,
      page: null,
    })
    renderWithRouter(
      <EvidenceView
        evidence={[item]}
        evidenceSupport="HIGH"
        insufficientEvidence={false}
        systemId={FIXTURE_SYSTEM_ID}
      />,
    )
    const link = screen.getByTestId('evidence-item-link')
    expect(link.textContent).toBe('Open in Blast Radius')
    expect(link.getAttribute('href')).toBe(
      `/blast-radius?system=${FIXTURE_SYSTEM_ID}&node=RISK%3ARISK-7`,
    )
  })

  it('renders no link and no disabled/placeholder affordance for an item whose evidenceHref is null', () => {
    const item = fixtureItem({ evidence_type: 'document', document_id: null as unknown as string })
    renderWithRouter(
      <EvidenceView
        evidence={[item]}
        evidenceSupport="HIGH"
        insufficientEvidence={false}
        systemId={FIXTURE_SYSTEM_ID}
      />,
    )
    expect(screen.queryByTestId('evidence-item-link')).toBeNull()
    const card = screen.getByTestId(`evidence-item-${item.evidence_id}`)
    expect(card.querySelector('button[disabled]')).toBeNull()
    expect(card.querySelector('[title]')).toBeNull()
  })

  it('carries no accent hue on the link -- neutral ink tokens only', () => {
    const item = fixtureItem({ evidence_type: 'document', document_id: 'DOC-A' })
    renderWithRouter(
      <EvidenceView
        evidence={[item]}
        evidenceSupport="HIGH"
        insufficientEvidence={false}
        systemId={FIXTURE_SYSTEM_ID}
      />,
    )
    const link = screen.getByTestId('evidence-item-link')
    expect(link.className).toContain('text-ink-muted')
    expect(link.className).not.toMatch(/text-(accent|mint|amber|orange|red|violet)/)
  })
})
