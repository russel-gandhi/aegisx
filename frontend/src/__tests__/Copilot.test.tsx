import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Copilot, {
  matchHeroQuery,
  injectionDetectedCopy,
  EMPTY_STATE_HEADING,
  EMPTY_STATE_BODY,
  STREAM_FAILURE_COPY,
  INVESTIGATE_FAILURE_COPY,
  COPILOT_SYSTEM_IDS,
} from '../pages/Copilot'
import type { AssuranceCardData, CopilotInvestigateResult } from '../lib/api'
import { stubAssuranceCardsFetch } from './helpers/sseFetch'

vi.mock('../lib/ws', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/ws')>()
  return {
    ...actual,
    connectCopilotStream: vi.fn(() => ({ close: vi.fn(), send: vi.fn() })),
  }
})

// Phase 06.1 plan 06.1-06 (D-07): `investigateCopilot` (real,
// `POST /api/copilot/investigate`, backed by the compiled C2->A0->[A1..A6]->
// C1->A7->C3 StateGraph) is mocked here at the HTTP boundary -- its own real
// server-side behavior (grounded synthesis, C2's injection block, D-09's
// insufficient-evidence gate) is covered by
// backend/tests/test_routes_copilot_investigate.py. `streamAssuranceCards`
// (the hero-query fast path, D-07's "may remain as an optimisation")
// is deliberately left real, driven instead via `stubAssuranceCardsFetch`'s
// global `fetch` stub -- the two paths use different transports (POST/JSON
// vs. a raw SSE `fetch`), so they can be mocked independently without one
// leaking into the other.
vi.mock('../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/api')>()
  return {
    ...actual,
    investigateCopilot: vi.fn(),
  }
})

import { investigateCopilot } from '../lib/api'

const mockInvestigateCopilot = vi.mocked(investigateCopilot)

const HERO_QUERY = 'Is GXP-MFG-DEMO-01 audit ready?'

function fixtureCard(overrides: Partial<AssuranceCardData>): AssuranceCardData {
  return {
    finding_id: 'A2-FIXTURE-01',
    claim: 'FIXTURE-CLAIM',
    evidence_ids: ['FIXTURE-EVID-01'],
    regulatory_citations: ['ANNEX11-S11-PE-001'],
    deterministic_check: {
      check_name: 'verify_periodic_eval_current',
      passed: false,
      db_record_found: true,
      opa_corroborated: true,
      opa_rule_ids: ['ANNEX11-S11-PE-001'],
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

function fixtureInvestigateResult(
  overrides: Partial<CopilotInvestigateResult> = {},
): CopilotInvestigateResult {
  return {
    answer: 'The Validation Protocol traces URS-042 to test case TC-017, which passed.',
    insufficient_evidence: false,
    blocked: false,
    blocked_reason: null,
    evidence: [
      {
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
      },
    ],
    stages: [
      { stage_id: 'understanding', label: 'Understanding question', status: 'complete', detail: null },
      { stage_id: 'searching', label: 'Searching knowledge', status: 'complete', detail: null },
      { stage_id: 'combining', label: 'Combining semantic and keyword evidence', status: 'complete', detail: null },
      { stage_id: 'reranking', label: 'Reranking candidates', status: 'complete', detail: null },
      { stage_id: 'evaluating', label: 'Evaluating evidence', status: 'complete', detail: null },
      { stage_id: 'preparing', label: 'Preparing assessment', status: 'complete', detail: null },
    ],
    findings: [],
    verification_results: {},
    evidence_support: 'HIGH',
    model_attribution: 'gemini-2.5-flash',
    navigation_target: null,
    ...overrides,
  }
}

function renderCopilot(initialEntries: Array<string | { pathname: string; state?: unknown }> = ['/copilot']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Copilot />
    </MemoryRouter>,
  )
}

async function submitQuery(text: string) {
  const textarea = screen.getByPlaceholderText(/Ask e.g/i)
  fireEvent.change(textarea, { target: { value: text } })
  fireEvent.click(screen.getByRole('button', { name: /Ask Copilot/i }))
}

beforeEach(() => {
  mockInvestigateCopilot.mockReset()
  // Default: a grounded, non-blocked, sufficient-evidence answer -- the
  // common case for any test that doesn't care about the exact response.
  mockInvestigateCopilot.mockResolvedValue(fixtureInvestigateResult())
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('matchHeroQuery', () => {
  it('matches a known system id with "audit ready"', () => {
    expect(matchHeroQuery('Is GXP-MFG-DEMO-01 audit ready?')).toBe('GXP-MFG-DEMO-01')
  })

  it('matches a second known system id and tolerates "audit-ready"', () => {
    expect(matchHeroQuery('Is BUS-IT-DEMO-02 audit-ready?')).toBe('BUS-IT-DEMO-02')
  })

  it('is case and spacing tolerant', () => {
    expect(matchHeroQuery('is gxp-mfg-demo-01   audit   ready')).toBe('GXP-MFG-DEMO-01')
  })

  it('returns null for unrelated input', () => {
    expect(matchHeroQuery("what's the weather")).toBeNull()
  })

  it('returns null when the system id is unknown even if audit-ready is present', () => {
    expect(matchHeroQuery('Is NO-SUCH-SYSTEM audit ready?')).toBeNull()
  })
})

describe('Copilot empty state', () => {
  it('renders the empty-state heading and body before the first message is sent', () => {
    renderCopilot()
    expect(screen.getByText(EMPTY_STATE_HEADING)).toBeInTheDocument()
    expect(screen.getByText(EMPTY_STATE_BODY)).toBeInTheDocument()
  })
})

describe('Copilot hero query', () => {
  it('renders a user bubble then accumulates AssuranceCards in arrival order', async () => {
    const cards = [
      fixtureCard({ finding_id: 'CARD-1', claim: 'FIXTURE-CLAIM-ONE' }),
      fixtureCard({ finding_id: 'CARD-2', claim: 'FIXTURE-CLAIM-TWO' }),
    ]
    stubAssuranceCardsFetch({ cards })

    renderCopilot()
    await submitQuery(HERO_QUERY)

    expect(screen.getByText(HERO_QUERY)).toBeInTheDocument()

    await waitFor(() => {
      const testIds = screen.getAllByTestId('assurance-card')
      expect(testIds.length).toBe(2)
    })
    const testIds = screen.getAllByTestId('assurance-card')
    expect(testIds[0].textContent).toContain('CARD-1')
    expect(testIds[1].textContent).toContain('CARD-2')
  })

  it('renders the "every check passes" line when the terminal frame reports count: 0', async () => {
    stubAssuranceCardsFetch({ cards: [] })

    renderCopilot()
    await submitQuery(HERO_QUERY)

    await waitFor(() => {
      expect(
        screen.getByText(/Every deterministic check currently passes/i),
      ).toBeInTheDocument()
    })
  })

  it('disables the input and toggles the button label while a hero-query stream is in-flight', async () => {
    stubAssuranceCardsFetch({ cards: [fixtureCard({})], chunkSize: 4 })

    renderCopilot()
    await submitQuery(HERO_QUERY)

    expect(screen.getByRole('button', { name: 'Investigating…' })).toBeDisabled()
    expect(screen.getByPlaceholderText(/Ask e.g/i)).toBeDisabled()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Ask Copilot' })).toBeInTheDocument()
    })
  })

  it('transitions AgentTopologyCanvas nodes to running on open, then complete on the terminal frame', async () => {
    stubAssuranceCardsFetch({ cards: [fixtureCard({})] })

    const { container } = renderCopilot()
    await submitQuery(HERO_QUERY)

    function findNode(id: string): Element {
      const node = Array.from(container.querySelectorAll('.react-flow__node')).find((el) =>
        el.textContent?.includes(id),
      )
      if (node === undefined) throw new Error(`node ${id} not found`)
      return node
    }

    await waitFor(() => {
      expect(findNode('A0').className).toContain('border-amber-600')
      expect(findNode('A2').className).toContain('border-amber-600')
    })

    await waitFor(() => {
      expect(findNode('A0').className).toContain('border-emerald-600')
      expect(findNode('A2').className).toContain('border-emerald-600')
      expect(findNode('C1').className).toContain('border-emerald-600')
    })
  })

  it('renders the stream-failure copy inline as the assistant turn on stream error', async () => {
    stubAssuranceCardsFetch({ cards: [], errorDetail: 'boom' })

    renderCopilot()
    await submitQuery(HERO_QUERY)

    await waitFor(() => {
      expect(screen.getByText(STREAM_FAILURE_COPY)).toBeInTheDocument()
    })
  })

  it('never surfaces the error state for an aborted stream (unmount mid-stream)', async () => {
    stubAssuranceCardsFetch({ cards: [fixtureCard({})], chunkSize: 4 })

    const { unmount } = renderCopilot()
    await submitQuery(HERO_QUERY)
    unmount()

    // No assertion throws / no error text was ever committed to a
    // detached tree -- the AbortError path must not attempt a state
    // update that would otherwise be caught as an error boundary/log.
    await new Promise((resolve) => setTimeout(resolve, 10))
  })

  it('disables the submit button for the whole in-flight duration, preventing a second submit via the UI', async () => {
    // The input/button-disable behavior (D-05, Copywriting Contract) is
    // itself the mechanism that prevents interleaved streams through the
    // UI -- `runHeroQuery`'s own `controllerRef.current?.abort()` guard
    // (mirroring FindingInvestigation.tsx's Pitfall 3 handling) is
    // defensive for any future non-UI trigger path, not reachable here.
    stubAssuranceCardsFetch({ cards: [fixtureCard({ finding_id: 'FIRST-STREAM' })], chunkSize: 4 })

    renderCopilot()
    await submitQuery(HERO_QUERY)

    expect(screen.queryByRole('button', { name: 'Ask Copilot' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Investigating…' })).toBeDisabled()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Ask Copilot' })).toBeInTheDocument()
    })
  })
})

describe('Copilot free-text investigation (plan 06.1-06, D-07: real investigateCopilot() call)', () => {
  it('calls investigateCopilot() with the submitted text and the selected system id for a non-matching submit', async () => {
    stubAssuranceCardsFetch({ cards: [] })
    renderCopilot()
    await submitQuery("what's traced to URS-042?")

    await waitFor(() => {
      expect(mockInvestigateCopilot).toHaveBeenCalledWith("what's traced to URS-042?", 'GXP-MFG-DEMO-01')
    })
  })

  it('shows the investigating placeholder and disables input/send while the request is in flight', async () => {
    stubAssuranceCardsFetch({ cards: [] })
    let resolveInvestigate: (value: CopilotInvestigateResult) => void = () => {}
    mockInvestigateCopilot.mockReturnValue(
      new Promise((resolve) => {
        resolveInvestigate = resolve
      }),
    )

    renderCopilot()
    await submitQuery("what's traced to URS-042?")

    const bubble = screen.getByTestId('chat-message-assistant')
    expect(bubble.textContent).toContain('Investigating…')
    expect(screen.getByRole('button', { name: 'Investigating…' })).toBeDisabled()
    expect(screen.getByPlaceholderText(/Ask e.g/i)).toBeDisabled()

    resolveInvestigate(fixtureInvestigateResult())
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Ask Copilot' })).toBeInTheDocument()
    })
  })

  it('renders the answer, model attribution, trace toggle, and evidence view in order on a grounded response', async () => {
    stubAssuranceCardsFetch({ cards: [] })
    const result = fixtureInvestigateResult()
    mockInvestigateCopilot.mockResolvedValue(result)
    renderCopilot()
    await submitQuery("what's traced to URS-042?")

    await waitFor(() => {
      expect(screen.getByText(result.answer)).toBeInTheDocument()
    })
    const bubble = screen.getByTestId('chat-message-assistant')
    const text = bubble.textContent ?? ''
    const answerIdx = text.indexOf(result.answer)
    const modelIdx = text.indexOf('gemini-2.5-flash')
    const traceIdx = text.indexOf('How AegisX searched')
    const evidenceIdx = text.indexOf('High evidence support')

    expect(answerIdx).toBeGreaterThanOrEqual(0)
    expect(answerIdx).toBeLessThan(modelIdx)
    expect(modelIdx).toBeLessThan(traceIdx)
    expect(traceIdx).toBeLessThan(evidenceIdx)
  })

  it('renders only the insufficient-evidence copy -- no answer, trace toggle, or full evidence list -- when insufficient_evidence is true', async () => {
    stubAssuranceCardsFetch({ cards: [] })
    mockInvestigateCopilot.mockResolvedValue(
      fixtureInvestigateResult({
        insufficient_evidence: true,
        evidence: [],
        evidence_support: 'INSUFFICIENT_EVIDENCE',
        answer: '',
      }),
    )
    renderCopilot()
    await submitQuery('what about an uncovered topic?')

    await waitFor(() => {
      expect(
        screen.getByText(/Insufficient evidence to answer this question/i),
      ).toBeInTheDocument()
    })
    expect(screen.queryByText('How AegisX searched')).toBeNull()
  })

  it('renders the destructive-styled bubble with the real blocked_reason when blocked is true', async () => {
    stubAssuranceCardsFetch({ cards: [] })
    const reason = 'entropy_threshold_exceeded'
    mockInvestigateCopilot.mockResolvedValue(
      fixtureInvestigateResult({ blocked: true, blocked_reason: reason }),
    )
    renderCopilot()
    await submitQuery('some suspicious input')

    await waitFor(() => {
      expect(screen.getByText(injectionDetectedCopy(reason))).toBeInTheDocument()
    })
    const bubble = screen.getByText(injectionDetectedCopy(reason))
    expect(bubble.getAttribute('data-variant')).toBe('blocked')
  })

  it('renders the investigate-failure copy (never a fabricated answer) when investigateCopilot() rejects', async () => {
    stubAssuranceCardsFetch({ cards: [] })
    mockInvestigateCopilot.mockRejectedValue(new Error('network down'))
    renderCopilot()
    await submitQuery("what's traced to URS-042?")

    await waitFor(() => {
      expect(screen.getByText(INVESTIGATE_FAILURE_COPY)).toBeInTheDocument()
    })
    expect(INVESTIGATE_FAILURE_COPY).toBe(STREAM_FAILURE_COPY)
  })

  it('offers a system selector defaulting to GXP-MFG-DEMO-01 and sends the selected value with the request', async () => {
    stubAssuranceCardsFetch({ cards: [] })
    renderCopilot()

    const select = screen.getByLabelText('System') as HTMLSelectElement
    expect(select.value).toBe(COPILOT_SYSTEM_IDS[0])

    fireEvent.change(select, { target: { value: 'BUS-IT-DEMO-02' } })
    await submitQuery("what's traced to URS-042?")

    await waitFor(() => {
      expect(mockInvestigateCopilot).toHaveBeenCalledWith(
        "what's traced to URS-042?",
        'BUS-IT-DEMO-02',
      )
    })
  })

  it('wraps a 2000-character answer inside the existing chat-bubble max-width without overflow', async () => {
    stubAssuranceCardsFetch({ cards: [] })
    const longAnswer = 'A'.repeat(2000)
    mockInvestigateCopilot.mockResolvedValue(fixtureInvestigateResult({ answer: longAnswer }))
    renderCopilot()
    await submitQuery("what's traced to URS-042?")

    await waitFor(() => {
      const bubble = screen.getByTestId('chat-message-assistant')
      expect(bubble.className).toContain('max-w-2xl')
      expect(bubble.textContent).toContain(longAnswer)
    })
  })
})

describe('Copilot message list auto-scroll (06-UI-SPEC.md overflow row)', () => {
  it('sets scrollTop to scrollHeight on the message container after a new message arrives', async () => {
    stubAssuranceCardsFetch({ cards: [] })
    const { container } = renderCopilot()
    await submitQuery("what's the weather")

    await waitFor(() => {
      const messagesEl = container.querySelector('[data-testid="copilot-messages"]') as HTMLElement
      expect(messagesEl).not.toBeNull()
    })

    const messagesEl = container.querySelector('[data-testid="copilot-messages"]') as HTMLElement
    // jsdom always reports scrollHeight as 0 (no real layout engine) --
    // this proves the effect fired and assigned scrollTop from
    // scrollHeight, not that jsdom itself scrolled a real viewport.
    expect(messagesEl.scrollTop).toBe(messagesEl.scrollHeight)
  })
})

describe('Copilot prefillQuery seam', () => {
  it('seeds the textarea from location.state.prefillQuery without auto-submitting', () => {
    stubAssuranceCardsFetch({ cards: [] })
    renderCopilot([{ pathname: '/copilot', state: { prefillQuery: HERO_QUERY } }])

    const textarea = screen.getByPlaceholderText(/Ask e.g/i) as HTMLTextAreaElement
    expect(textarea.value).toBe(HERO_QUERY)
    // No user bubble yet -- seeding the textarea must never auto-submit.
    expect(screen.queryByText(HERO_QUERY, { selector: '[data-testid="chat-message-user"]' })).toBeNull()
  })
})
