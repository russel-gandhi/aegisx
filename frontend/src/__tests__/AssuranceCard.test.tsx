import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AppShell } from '../App'
import AssuranceCard from '../components/AssuranceCard'
import type { AssuranceCardData } from '../lib/api'

// One fixture, distinctive values per field so no assertion can pass on
// the wrong field (04-03-PLAN.md <behavior>).
// Note: fixture values deliberately avoid embedding the literal words
// "CLAIM" / "EVIDENCE" / "RULE" inside claim/evidence/citation text --
// those words are also the component's own section labels, and a fixture
// value containing one would make the single-match label assertions below
// ambiguous (two elements matching the same regex) rather than a true
// negative test failure.
const FIXTURE: AssuranceCardData = {
  finding_id: 'A2-ANNEX11-S11-PE-001-PE-2024-01',
  claim: 'FIXTURE-STATEMENT-the periodic evaluation is overdue for GXP-MFG-DEMO-01',
  evidence_ids: ['FIXTURE-RECORD-PE-2024-01'],
  regulatory_citations: ['FIXTURE-CITATION-ANNEX11-S11-PE-001'],
  deterministic_check: {
    check_name: 'FIXTURE-CHECKFN-verify_periodic_eval_current',
    passed: false,
    db_record_found: true,
    opa_corroborated: true,
    opa_rule_ids: ['FIXTURE-CITATION-ANNEX11-S11-PE-001'],
  },
  confidence: 'MEDIUM',
  alcoa_score: {
    attributable: false,
    legible: true,
    contemporaneous: false,
    original: false,
    accurate: true,
    complete: true,
    consistent: true,
    enduring: true,
    available: true,
  },
  model_attribution: 'FIXTURE-MODEL-ID-gemini-2.5-flash',
}

const INSUFFICIENT_EVIDENCE_FIXTURE: AssuranceCardData = {
  ...FIXTURE,
  finding_id: 'A2-ANNEX11-S11-PE-001-NO-RECORD',
  evidence_ids: [],
  confidence: 'INSUFFICIENT_EVIDENCE',
  deterministic_check: {
    ...FIXTURE.deterministic_check,
    db_record_found: false,
    opa_corroborated: false,
  },
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('AssuranceCard component', () => {
  it('renders all five EVID-03 section labels', () => {
    render(<AssuranceCard card={FIXTURE} />)
    expect(screen.getByText(/CLAIM/i)).toBeInTheDocument()
    expect(screen.getByText(/EVIDENCE/i)).toBeInTheDocument()
    expect(screen.getByText(/RULE/i)).toBeInTheDocument()
    expect(screen.getByText(/DETERMINISTIC CHECK/i)).toBeInTheDocument()
    expect(screen.getByText(/CONFIDENCE/i)).toBeInTheDocument()
  })

  it('renders every field value from the card prop', () => {
    render(<AssuranceCard card={FIXTURE} />)
    expect(screen.getByText(FIXTURE.claim)).toBeInTheDocument()
    for (const evidenceId of FIXTURE.evidence_ids) {
      expect(screen.getByText(new RegExp(evidenceId))).toBeInTheDocument()
    }
    for (const citation of FIXTURE.regulatory_citations) {
      expect(screen.getByText(new RegExp(citation))).toBeInTheDocument()
    }
    expect(
      screen.getByText(new RegExp(FIXTURE.deterministic_check.check_name)),
    ).toBeInTheDocument()
    expect(screen.getAllByText(new RegExp(FIXTURE.confidence)).length).toBeGreaterThan(0)
    expect(screen.getByText(new RegExp(FIXTURE.model_attribution))).toBeInTheDocument()
  })

  it('renders all nine ALCOA+ dimension names', () => {
    render(<AssuranceCard card={FIXTURE} />)
    for (const dimension of Object.keys(FIXTURE.alcoa_score)) {
      expect(screen.getByText(new RegExp(dimension, 'i'))).toBeInTheDocument()
    }
  })

  it('sets a data-confidence attribute equal to an INSUFFICIENT_EVIDENCE grade', () => {
    const { container } = render(<AssuranceCard card={INSUFFICIENT_EVIDENCE_FIXTURE} />)
    const root = container.querySelector('[data-confidence]')
    expect(root).not.toBeNull()
    expect(root?.getAttribute('data-confidence')).toBe('INSUFFICIENT_EVIDENCE')
    expect(screen.getByText(/INSUFFICIENT_EVIDENCE/)).toBeInTheDocument()
  })

  it('renders an explicit no-evidence message when evidence_ids is empty', () => {
    render(<AssuranceCard card={INSUFFICIENT_EVIDENCE_FIXTURE} />)
    expect(screen.getByText(/no evidence/i)).toBeInTheDocument()
  })

  it('makes no network call when rendered in isolation', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    render(<AssuranceCard card={FIXTURE} />)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

function stubFetchOnce(response: unknown, ok = true) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 500,
    json: async () => response,
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('/findings page', () => {
  it('renders two card regions for a two-card response', async () => {
    stubFetchOnce({
      system_id: 'GXP-MFG-DEMO-01',
      cards: [FIXTURE, INSUFFICIENT_EVIDENCE_FIXTURE],
    })

    const { container } = render(
      <MemoryRouter initialEntries={['/findings']}>
        <AppShell />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(container.querySelectorAll('[data-confidence]').length).toBe(2)
    })
  })

  it('renders an explicit all-checks-passing message for a zero-card response', async () => {
    stubFetchOnce({ system_id: 'GXP-MFG-DEMO-01', cards: [] })

    render(
      <MemoryRouter initialEntries={['/findings']}>
        <AppShell />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/pass/i)).toBeInTheDocument()
    })
  })

  it('renders a visible error message on a rejected fetch', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')))

    render(
      <MemoryRouter initialEntries={['/findings']}>
        <AppShell />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument()
    })
  })
})
