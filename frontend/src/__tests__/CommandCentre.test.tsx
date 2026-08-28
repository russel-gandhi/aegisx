import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import CommandCentre, {
  EMPTY_STATE_HEADING,
  EMPTY_STATE_BODY,
} from '../pages/CommandCentre'
import type {
  AssuranceCardData,
  AssuranceCardsResponse,
  SystemSignalsResponse,
  ActionProposalsResponse,
  ChainVerificationResponse,
} from '../lib/api'

// Mocks the four backing calls directly (mirrors __tests__/Copilot.test.tsx's
// `queryCopilot` mocking convention) -- CommandCentre uses the blocking
// `fetchAssuranceCards`/`fetchSystemSignals`/`fetchActionProposals`/
// `fetchChainVerification` contracts, not the SSE stream, so the
// stream-shaped `helpers/sseFetch.ts` builder does not apply here.
vi.mock('../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/api')>()
  return {
    ...actual,
    fetchAssuranceCards: vi.fn(),
    fetchSystemSignals: vi.fn(),
    fetchActionProposals: vi.fn(),
    fetchChainVerification: vi.fn(),
  }
})

import {
  fetchAssuranceCards,
  fetchSystemSignals,
  fetchActionProposals,
  fetchChainVerification,
} from '../lib/api'

const mockFetchAssuranceCards = vi.mocked(fetchAssuranceCards)
const mockFetchSystemSignals = vi.mocked(fetchSystemSignals)
const mockFetchActionProposals = vi.mocked(fetchActionProposals)
const mockFetchChainVerification = vi.mocked(fetchChainVerification)

function fixtureCard(overrides: Partial<AssuranceCardData>): AssuranceCardData {
  return {
    finding_id: 'A2-FIXTURE-01',
    claim: 'FIXTURE-CLAIM',
    evidence_ids: ['FIXTURE-EVID-01'],
    regulatory_citations: ['ANNEX11-S4-DOC-001'],
    deterministic_check: {
      check_name: 'verify_urs_approved',
      passed: false,
      db_record_found: true,
      opa_corroborated: false,
      opa_rule_ids: [],
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
    model_attribution: 'deterministic-fallback',
    ...overrides,
  }
}

function emptyCards(systemId: string): AssuranceCardsResponse {
  return { system_id: systemId, cards: [] }
}

function emptySignals(systemId: string): SystemSignalsResponse {
  return {
    system_id: systemId,
    overdue_access_reviews: 0,
    overdue_suppliers: 0,
    overdue_supplier_names: [],
  }
}

const EMPTY_ACTIONS: ActionProposalsResponse = { proposals: [] }
const VERIFIED_CHAIN: ChainVerificationResponse = {
  status: 'VERIFIED',
  events_checked: 10,
  broken_at_index: null,
  event_id: null,
}

beforeEach(() => {
  mockFetchAssuranceCards.mockReset()
  mockFetchSystemSignals.mockReset()
  mockFetchActionProposals.mockReset()
  mockFetchChainVerification.mockReset()

  // Sensible healthy-and-empty defaults, overridable per test.
  mockFetchAssuranceCards.mockImplementation((systemId: string) =>
    Promise.resolve(emptyCards(systemId)),
  )
  mockFetchSystemSignals.mockImplementation((systemId: string) =>
    Promise.resolve(emptySignals(systemId)),
  )
  mockFetchActionProposals.mockResolvedValue(EMPTY_ACTIONS)
  mockFetchChainVerification.mockResolvedValue(VERIFIED_CHAIN)
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('CommandCentre readiness dial and mini-cards 1/2 (D-06, D-07)', () => {
  it('computes a 75% dial and card counts of 1 from one failing check per system', async () => {
    mockFetchAssuranceCards.mockImplementation((systemId: string) => {
      if (systemId === 'GXP-MFG-DEMO-01') {
        return Promise.resolve({
          system_id: systemId,
          cards: [
            fixtureCard({
              finding_id: 'A2-URS',
              deterministic_check: {
                check_name: 'verify_urs_approved',
                passed: false,
                db_record_found: true,
                opa_corroborated: false,
                opa_rule_ids: [],
              },
            }),
          ],
        })
      }
      return Promise.resolve({
        system_id: systemId,
        cards: [
          fixtureCard({
            finding_id: 'A2-PE',
            deterministic_check: {
              check_name: 'verify_periodic_eval_current',
              passed: false,
              db_record_found: true,
              opa_corroborated: true,
              opa_rule_ids: ['ANNEX11-S11-PE-001'],
            },
          }),
        ],
      })
    })

    render(<CommandCentre />)

    await waitFor(() => {
      expect(screen.getByTestId('readiness-dial')).toHaveAttribute('data-percent', '75')
    })
    const cards = screen.getAllByTestId('health-mini-card')
    expect(cards[0].textContent).toContain('1 open')
    expect(cards[1].textContent).toContain('1 open')
  })

  it('narrows the dial to a single system 4-check denominator when selected', async () => {
    mockFetchAssuranceCards.mockImplementation((systemId: string) => {
      if (systemId === 'GXP-MFG-DEMO-01') {
        return Promise.resolve({ system_id: systemId, cards: [fixtureCard({})] })
      }
      return Promise.resolve(emptyCards(systemId))
    })

    render(<CommandCentre />)
    await waitFor(() => {
      expect(screen.getByTestId('readiness-dial')).toHaveAttribute('data-percent', '88')
    })

    fireEvent.change(screen.getByLabelText('System'), {
      target: { value: 'GXP-MFG-DEMO-01' },
    })

    await waitFor(() => {
      expect(screen.getByTestId('readiness-dial')).toHaveAttribute('data-percent', '75')
    })
  })
})

describe('CommandCentre partial-failure and empty-state handling', () => {
  it('renders the partial-data note (not the empty state) when one system fails and the other succeeds', async () => {
    mockFetchAssuranceCards.mockImplementation((systemId: string) => {
      if (systemId === 'GXP-MFG-DEMO-01') {
        return Promise.reject(new Error('network down'))
      }
      return Promise.resolve(emptyCards(systemId))
    })

    render(<CommandCentre />)

    await waitFor(() => {
      expect(screen.getByTestId('partial-data-note')).toBeInTheDocument()
    })
    expect(screen.queryByText(EMPTY_STATE_HEADING)).toBeNull()
  })

  it('renders the empty state only when every call across both systems fails', async () => {
    mockFetchAssuranceCards.mockRejectedValue(new Error('network down'))
    mockFetchSystemSignals.mockRejectedValue(new Error('network down'))

    render(<CommandCentre />)

    await waitFor(() => {
      expect(screen.getByText(EMPTY_STATE_HEADING)).toBeInTheDocument()
    })
    expect(screen.getByText(EMPTY_STATE_BODY)).toBeInTheDocument()
  })

  it('renders a dismissible aggregate-error banner on a global-call failure, and hides it on dismiss', async () => {
    mockFetchActionProposals.mockRejectedValue(new Error('network down'))

    render(<CommandCentre />)

    await waitFor(() => {
      expect(screen.getByTestId('aggregate-error-banner')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(screen.queryByTestId('aggregate-error-banner')).toBeNull()
  })
})

describe('CommandCentre mini-card independence (loading/error per card)', () => {
  it('keeps cards 1/2 in their own loading state while assurance calls are still in-flight, independent of the other cards', async () => {
    mockFetchAssuranceCards.mockImplementation(() => new Promise(() => {}))

    render(<CommandCentre />)

    const cards = screen.getAllByTestId('health-mini-card')
    expect(cards[0]).toHaveAttribute('data-status', 'loading')
    expect(cards[1]).toHaveAttribute('data-status', 'loading')

    await waitFor(() => {
      expect(screen.getAllByTestId('health-mini-card')[2]).toHaveAttribute('data-status', 'ready')
      expect(screen.getAllByTestId('health-mini-card')[3]).toHaveAttribute('data-status', 'ready')
    })
  })

  it('marks card 4 (Audit Trail Integrity) as error when only the chain-verification call fails, without affecting other cards', async () => {
    mockFetchChainVerification.mockRejectedValue(new Error('network down'))

    render(<CommandCentre />)

    await waitFor(() => {
      const cards = screen.getAllByTestId('health-mini-card')
      expect(cards[3]).toHaveAttribute('data-status', 'error')
      expect(cards[0]).toHaveAttribute('data-status', 'ready')
    })
  })
})

describe('CommandCentre mini-card #6 Supplier Qualification (D-07)', () => {
  it('explicitly names the overdue supplier "DataSync Solutions", not just a count', async () => {
    mockFetchSystemSignals.mockImplementation((systemId: string) => {
      if (systemId === 'GXP-MFG-DEMO-01') {
        return Promise.resolve({
          system_id: systemId,
          overdue_access_reviews: 1,
          overdue_suppliers: 1,
          overdue_supplier_names: ['DataSync Solutions'],
        })
      }
      return Promise.resolve(emptySignals(systemId))
    })

    render(<CommandCentre />)

    await waitFor(() => {
      expect(screen.getByText('DataSync Solutions')).toBeInTheDocument()
    })
  })
})

describe('CommandCentre system selector (D-06)', () => {
  it('renders exactly the 3 fixed options: All Systems, GXP-MFG-DEMO-01, BUS-IT-DEMO-02', () => {
    render(<CommandCentre />)
    const options = screen.getAllByRole('option')
    expect(options.map((o) => o.textContent)).toEqual([
      'All Systems',
      'GXP-MFG-DEMO-01',
      'BUS-IT-DEMO-02',
    ])
  })
})

describe('CommandCentre never reads the stale readiness_score seed column', () => {
  it('renders a live-computed percentage, not the static seed literal (61%/94%)', async () => {
    mockFetchAssuranceCards.mockImplementation((systemId: string) => Promise.resolve(emptyCards(systemId)))

    render(<CommandCentre />)

    await waitFor(() => {
      expect(screen.getByTestId('readiness-dial')).toHaveAttribute('data-percent', '100')
    })
    expect(screen.queryByText('61%')).toBeNull()
    expect(screen.queryByText('94%')).toBeNull()
  })
})
