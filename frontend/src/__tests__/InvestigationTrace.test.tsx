import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import InvestigationTrace, { TRACE_TOGGLE_LABEL } from '../components/InvestigationTrace'
import type { InvestigationStage } from '../lib/api'

const SIX_STAGES: InvestigationStage[] = [
  { stage_id: 'understanding', label: 'Understanding question', status: 'complete', detail: null },
  { stage_id: 'searching', label: 'Searching knowledge', status: 'complete', detail: '12 candidates' },
  { stage_id: 'combining', label: 'Combining semantic and keyword evidence', status: 'complete', detail: null },
  { stage_id: 'reranking', label: 'Reranking candidates', status: 'complete', detail: null },
  { stage_id: 'evaluating', label: 'Evaluating evidence', status: 'complete', detail: null },
  { stage_id: 'preparing', label: 'Preparing assessment', status: 'skipped', detail: null },
]

describe('InvestigationTrace -- six-stage rendering', () => {
  it('renders six rows in the response order with each stage label, once opened', () => {
    render(<InvestigationTrace stages={SIX_STAGES} />)
    fireEvent.click(screen.getByTestId('investigation-trace-toggle'))

    const rows = SIX_STAGES.map((stage) =>
      screen.getByTestId(`investigation-trace-row-${stage.stage_id}`),
    )
    expect(rows).toHaveLength(6)
    rows.forEach((row, index) => {
      expect(row.textContent).toContain(SIX_STAGES[index].label)
    })
  })
})

describe('InvestigationTrace -- complete vs skipped styling', () => {
  it('renders a complete stage with the emerald glyph and a bright label', () => {
    render(<InvestigationTrace stages={SIX_STAGES} />)
    fireEvent.click(screen.getByTestId('investigation-trace-toggle'))

    const glyph = screen.getByTestId('investigation-trace-glyph-understanding')
    expect(glyph.textContent).toBe('✓')
    expect(glyph.className).toContain('text-emerald-600')
  })

  it('renders a skipped stage with the neutral dash glyph and a dimmed label, never styled as an error', () => {
    render(<InvestigationTrace stages={SIX_STAGES} />)
    fireEvent.click(screen.getByTestId('investigation-trace-toggle'))

    const glyph = screen.getByTestId('investigation-trace-glyph-preparing')
    expect(glyph.textContent).toBe('-')
    expect(glyph.className).toContain('text-slate-500')
    expect(glyph.className).not.toContain('red')
  })
})

describe('InvestigationTrace -- detail subtext', () => {
  it('renders detail as subtext when present and omits it entirely when null', () => {
    render(<InvestigationTrace stages={SIX_STAGES} />)
    fireEvent.click(screen.getByTestId('investigation-trace-toggle'))

    expect(screen.getByText('12 candidates')).toBeInTheDocument()
    const noDetailRow = screen.getByTestId('investigation-trace-row-understanding')
    expect(noDetailRow.querySelector('p')).toBeNull()
  })
})

describe('InvestigationTrace -- empty stage array', () => {
  it('renders nothing given an empty stage array', () => {
    const { container } = render(<InvestigationTrace stages={[]} />)
    expect(container.firstChild).toBeNull()
  })
})

describe('InvestigationTrace -- collapsed by default', () => {
  it('is collapsed behind the toggle button by default and expands on click', () => {
    render(<InvestigationTrace stages={SIX_STAGES} />)
    expect(screen.getByText(TRACE_TOGGLE_LABEL)).toBeInTheDocument()
    expect(screen.queryByTestId('investigation-trace-row-understanding')).toBeNull()

    fireEvent.click(screen.getByTestId('investigation-trace-toggle'))
    expect(screen.getByTestId('investigation-trace-row-understanding')).toBeInTheDocument()
  })
})

describe('InvestigationTrace -- fade-in stagger', () => {
  it('applies transition-opacity duration-200 with a 40ms-per-row inline stagger', () => {
    render(<InvestigationTrace stages={SIX_STAGES} />)
    fireEvent.click(screen.getByTestId('investigation-trace-toggle'))

    const row0 = screen.getByTestId('investigation-trace-row-understanding')
    const row1 = screen.getByTestId('investigation-trace-row-searching')
    expect(row0.className).toContain('transition-opacity')
    expect(row0.className).toContain('duration-200')
    expect(row0.style.transitionDelay).toBe('0ms')
    expect(row1.style.transitionDelay).toBe('40ms')
  })
})

describe('InvestigationTrace -- no timer advances a stage', () => {
  it('holds no setTimeout/setInterval that changes stage status after mount', () => {
    const source = InvestigationTrace.toString()
    expect(source).not.toMatch(/setTimeout|setInterval/)
  })
})
