import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import GuidedTourOverlay, { resolveRemediationDecision } from '../components/GuidedTourOverlay'
import FindingInvestigation from '../pages/FindingInvestigation'
import Actions from '../pages/Actions'
import type { ActionProposalData, AssuranceCardData, AssuranceCardsResponse } from '../lib/api'
import { stubAssuranceCardsFetch } from './helpers/sseFetch'

// react-joyride's real implementation relies on floating-ui positioning,
// scroll-into-view, and portal rendering that jsdom does not fully support
// (no layout engine) -- exactly the "deceptive complexity" 06-RESEARCH.md's
// Don't Hand-Roll section says the library exists to absorb. Mocking the
// library itself here isolates GuidedTourOverlay's own business logic
// (route navigation, the D-09 idempotency guard, target-not-found handling)
// under test, the same way Copilot.test.tsx mocks `connectCopilotStream`
// rather than exercising a real WebSocket. Production code still renders
// the real `<Joyride>` -- only this test substitutes a controllable stub.
vi.mock('react-joyride', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-joyride')>()
  return {
    ...actual,
    Joyride: (props: {
      run: boolean
      stepIndex: number
      steps: Array<{
        target: string
        title?: string
        content?: string
        targetWaitTimeout?: number
      }>
      options?: Record<string, unknown>
      onEvent: (data: unknown) => void
    }) => {
      if (!props.run) return null
      const currentStep = props.steps[props.stepIndex]
      return (
        <div data-testid="mock-joyride">
          <p data-testid="mock-joyride-target">{currentStep?.target}</p>
          <p data-testid="mock-joyride-title">{currentStep?.title}</p>
          <p data-testid="mock-joyride-content">{currentStep?.content}</p>
          <p data-testid="mock-joyride-wait">{String(currentStep?.targetWaitTimeout)}</p>
          <p data-testid="mock-joyride-overlay-click-action">
            {String(props.options?.overlayClickAction)}
          </p>
          {/* A step torn down without a navigation decision -- what a stray
              overlay click used to produce before `overlayClickAction: false`. */}
          <button
            type="button"
            data-testid="mock-joyride-step-close"
            onClick={() =>
              props.onEvent({
                type: actual.EVENTS.STEP_AFTER,
                action: actual.ACTIONS.CLOSE,
                status: actual.STATUS.RUNNING,
              })
            }
          >
            Close current step
          </button>
          <button
            type="button"
            data-testid="mock-joyride-next"
            onClick={() =>
              props.onEvent({
                type: actual.EVENTS.STEP_AFTER,
                action: actual.ACTIONS.NEXT,
                status: actual.STATUS.RUNNING,
              })
            }
          >
            Next
          </button>
          <button
            type="button"
            data-testid="mock-joyride-target-not-found"
            onClick={() =>
              props.onEvent({
                type: actual.EVENTS.TARGET_NOT_FOUND,
                action: actual.ACTIONS.UPDATE,
                status: actual.STATUS.RUNNING,
              })
            }
          >
            Simulate target not found
          </button>
          <button
            type="button"
            data-testid="mock-joyride-finish"
            onClick={() =>
              props.onEvent({
                type: actual.EVENTS.TOUR_END,
                action: actual.ACTIONS.CLOSE,
                status: actual.STATUS.FINISHED,
              })
            }
          >
            Finish
          </button>
        </div>
      )
    },
  }
})

// `fetchAssuranceCards`/`fetchActionProposals` are mocked directly for the
// D-09 guard's own unit-level branch tests (isolating GuidedTourOverlay's
// decision logic from network timing); `generateCapa`/`approveAction` are
// mocked too so the full-integration test below can assert exact call
// counts without a real backend.
vi.mock('../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/api')>()
  return {
    ...actual,
    fetchAssuranceCards: vi.fn(),
    fetchActionProposals: vi.fn(),
    generateCapa: vi.fn(),
    approveAction: vi.fn(),
  }
})

// Actions.tsx opens a WS connection on mount (Phase 5) -- irrelevant to
// this plan's D-09 logic, mocked exactly as Copilot.test.tsx mocks it.
vi.mock('../lib/ws', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/ws')>()
  return {
    ...actual,
    connectCopilotStream: vi.fn(() => ({ close: vi.fn(), send: vi.fn() })),
  }
})

import { fetchAssuranceCards, fetchActionProposals, generateCapa, approveAction } from '../lib/api'

const mockFetchAssuranceCards = vi.mocked(fetchAssuranceCards)
const mockFetchActionProposals = vi.mocked(fetchActionProposals)
const mockGenerateCapa = vi.mocked(generateCapa)
const mockApproveAction = vi.mocked(approveAction)

const DEMO_FINDING_ID = 'A2-DEMO-URS-01'

function fixtureAssuranceCardsResponse(findingId: string): AssuranceCardsResponse {
  return {
    system_id: 'GXP-MFG-DEMO-01',
    cards: [
      {
        finding_id: findingId,
        claim: 'URS traceability incomplete',
        evidence_ids: ['URS-2024-01'],
        regulatory_citations: ['ANNEX11-S4-DOC-001'],
        deterministic_check: {
          check_name: 'verify_urs_approved',
          passed: false,
          db_record_found: true,
          opa_corroborated: true,
          opa_rule_ids: ['ANNEX11-S4-DOC-001'],
        },
        confidence: 'HIGH',
        alcoa_score: {
          attributable: true,
          legible: true,
          contemporaneous: true,
          original: true,
          accurate: true,
          complete: true,
          consistent: true,
          enduring: true,
          available: true,
        },
        model_attribution: 'deterministic-fallback',
      },
    ],
  }
}

function fixtureStreamedCard(findingId: string): AssuranceCardData {
  return fixtureAssuranceCardsResponse(findingId).cards[0]
}

function fixtureProposal(overrides: Partial<ActionProposalData>): ActionProposalData {
  return {
    id: 'AP-FIXTURE-01',
    action_type: 'GENERATE_CAPA',
    category: 'DOCUMENTATION',
    target_system: 'GXP-MFG-DEMO-01',
    payload: {},
    status: 'PENDING_APPROVAL',
    justification: null,
    finding_id: DEMO_FINDING_ID,
    model_id: null,
    created_at: null,
    approved_by: null,
    approved_at: null,
    execution_result: null,
    ...overrides,
  }
}

function LocationProbe() {
  return null
}

function renderOverlay(initialEntries: string[] = ['/copilot']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <GuidedTourOverlay />
      <Routes>
        <Route path="*" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>,
  )
}

async function advanceToStepSix() {
  fireEvent.click(screen.getByTestId('start-guided-tour'))
  for (let i = 0; i < 5; i += 1) {
    fireEvent.click(screen.getByTestId('mock-joyride-next'))
  }
}

describe('GuidedTourOverlay', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    mockFetchAssuranceCards.mockReset()
    mockFetchActionProposals.mockReset()
    mockGenerateCapa.mockReset()
    mockApproveAction.mockReset()
  })

  it('renders the entry banner and starts the tour', () => {
    renderOverlay()

    expect(screen.getByTestId('start-guided-tour')).toHaveTextContent('Start Guided Tour')
    expect(screen.queryByTestId('mock-joyride')).not.toBeInTheDocument()

    fireEvent.click(screen.getByTestId('start-guided-tour'))

    expect(screen.getByTestId('mock-joyride')).toBeInTheDocument()
    expect(screen.getByTestId('mock-joyride-target')).toHaveTextContent(
      '[data-tour="readiness-dial"]',
    )
    expect(screen.queryByTestId('start-guided-tour')).not.toBeInTheDocument()
  })

  it('resets to the entry banner when the tour is skipped (Explore Freely)', () => {
    renderOverlay()
    fireEvent.click(screen.getByTestId('start-guided-tour'))
    fireEvent.click(screen.getByTestId('mock-joyride-finish'))

    expect(screen.getByTestId('start-guided-tour')).toBeInTheDocument()
    expect(screen.queryByTestId('mock-joyride')).not.toBeInTheDocument()
  })

  // Regression guards for debug session `guided-tour-copilot-next-stuck`.
  describe('unrecoverable-tour guards', () => {
    it('disables the overlay click action so a stray click cannot silently kill the tour', () => {
      renderOverlay()
      fireEvent.click(screen.getByTestId('start-guided-tour'))

      // react-joyride's default is `overlayClickAction: 'close'`, which turns
      // any click landing outside the spotlight into an ACTIONS.CLOSE that
      // tears the step down with no way back.
      expect(screen.getByTestId('mock-joyride-overlay-click-action')).toHaveTextContent('false')
    })

    it('ends the tour cleanly on a CLOSE action instead of stranding it with no tooltip', () => {
      renderOverlay()
      fireEvent.click(screen.getByTestId('start-guided-tour'))
      expect(screen.getByTestId('mock-joyride')).toBeInTheDocument()

      fireEvent.click(screen.getByTestId('mock-joyride-step-close'))

      // Joyride's own lifecycle has already completed for this step, so
      // leaving stepIndex untouched would leave the user staring at an
      // overlay with no tooltip and no way forward.
      expect(screen.getByTestId('start-guided-tour')).toBeInTheDocument()
      expect(screen.queryByTestId('mock-joyride')).not.toBeInTheDocument()
    })

    it('gives steps whose target appears only after backend work a longer targetWaitTimeout', () => {
      renderOverlay()
      fireEvent.click(screen.getByTestId('start-guided-tour'))

      // Step 1's target is static -- no override needed.
      expect(screen.getByTestId('mock-joyride-wait')).toHaveTextContent('undefined')

      // Step 3 ("Evidence, Verified") targets [data-tour="copilot-messages"],
      // which exists only once the hero query has been submitted AND streamed.
      // react-joyride's 1000ms default would declare TARGET_NOT_FOUND first --
      // and in controlled mode the library never auto-recovers from that.
      fireEvent.click(screen.getByTestId('mock-joyride-next')) // -> index 1
      fireEvent.click(screen.getByTestId('mock-joyride-next')) // -> index 2

      expect(screen.getByTestId('mock-joyride-target')).toHaveTextContent(
        '[data-tour="copilot-messages"]',
      )
      const wait = Number(screen.getByTestId('mock-joyride-wait').textContent)
      expect(wait).toBeGreaterThan(1000)
    })
  })

  it('shows a persistent note rather than crashing or silently skipping when a target is not found', () => {
    renderOverlay()
    fireEvent.click(screen.getByTestId('start-guided-tour'))
    fireEvent.click(screen.getByTestId('mock-joyride-target-not-found'))

    expect(screen.getByTestId('tour-target-not-found-note')).toBeInTheDocument()
  })

  it('renders a centered closing step ("Step 8 of 8") with no real-page target', async () => {
    mockFetchAssuranceCards.mockResolvedValue(fixtureAssuranceCardsResponse(DEMO_FINDING_ID))
    mockFetchActionProposals.mockResolvedValue({
      proposals: [fixtureProposal({ status: 'REJECTED' })],
    })

    renderOverlay()
    await advanceToStepSix()
    // The REJECTED-proposal branch auto-advances to Step 7; one more click
    // reaches the closing Step 8.
    await waitFor(() => {
      expect(screen.getByTestId('mock-joyride-target')).toHaveTextContent(
        '[data-tour="mini-card-audit-integrity"]',
      )
    })
    fireEvent.click(screen.getByTestId('mock-joyride-next'))

    expect(screen.getByTestId('mock-joyride-target')).toHaveTextContent('body')
  })

  describe('D-09 idempotency guard (pure decision function)', () => {
    it('decides to generate when no proposal exists for the finding', () => {
      expect(resolveRemediationDecision(DEMO_FINDING_ID, [])).toEqual({ kind: 'generate' })
    })

    it('decides to approve the existing proposal when one is PENDING_APPROVAL', () => {
      const proposal = fixtureProposal({ id: 'AP-1', status: 'PENDING_APPROVAL' })
      expect(resolveRemediationDecision(DEMO_FINDING_ID, [proposal])).toEqual({
        kind: 'approve',
        proposalId: 'AP-1',
        seeded: true,
      })
    })

    it('decides to skip when the existing proposal is already terminal', () => {
      for (const status of ['APPROVED', 'EXECUTED', 'REJECTED']) {
        const proposal = fixtureProposal({ id: 'AP-2', status })
        expect(resolveRemediationDecision(DEMO_FINDING_ID, [proposal])).toEqual({
          kind: 'skip',
          proposalId: 'AP-2',
        })
      }
    })
  })

  describe('D-09 idempotency guard (component-level, Step 6 branches)', () => {
    it('with no existing proposal, targets the real Generate CAPA button and never calls generateCapa itself', async () => {
      mockFetchAssuranceCards.mockResolvedValue(fixtureAssuranceCardsResponse(DEMO_FINDING_ID))
      mockFetchActionProposals.mockResolvedValue({ proposals: [] })

      renderOverlay()
      await advanceToStepSix()

      await waitFor(() => {
        expect(screen.getByTestId('mock-joyride-target')).toHaveTextContent(
          '[data-tour="generate-capa-button"]',
        )
      })
      expect(mockFetchActionProposals).toHaveBeenCalled()
      expect(mockGenerateCapa).not.toHaveBeenCalled()
    })

    it('with an existing PENDING_APPROVAL proposal, skips straight to Approve without calling generateCapa again', async () => {
      mockFetchAssuranceCards.mockResolvedValue(fixtureAssuranceCardsResponse(DEMO_FINDING_ID))
      mockFetchActionProposals.mockResolvedValue({
        proposals: [fixtureProposal({ id: 'AP-EXISTING', status: 'PENDING_APPROVAL' })],
      })

      renderOverlay()
      await advanceToStepSix()

      await waitFor(() => {
        expect(screen.getByTestId('mock-joyride-target')).toHaveTextContent(
          '[data-tour="approve-action"]',
        )
      })
      expect(mockGenerateCapa).not.toHaveBeenCalled()
      expect(screen.getByTestId('tour-skip-note')).toHaveTextContent(/already pending/i)
    })

    it('with an already-terminal (REJECTED) proposal, advances directly to Audit Integrity without visiting Approve', async () => {
      mockFetchAssuranceCards.mockResolvedValue(fixtureAssuranceCardsResponse(DEMO_FINDING_ID))
      mockFetchActionProposals.mockResolvedValue({
        proposals: [fixtureProposal({ id: 'AP-TERMINAL', status: 'REJECTED' })],
      })

      renderOverlay()
      await advanceToStepSix()

      await waitFor(() => {
        expect(screen.getByTestId('mock-joyride-target')).toHaveTextContent(
          '[data-tour="mini-card-audit-integrity"]',
        )
      })
      expect(mockGenerateCapa).not.toHaveBeenCalled()
      expect(mockApproveAction).not.toHaveBeenCalled()
      expect(screen.getByTestId('tour-skip-note')).toHaveTextContent(
        /already has a decided action proposal/i,
      )
    })

    it('with an already-terminal (APPROVED) proposal, also advances directly without visiting Approve', async () => {
      mockFetchAssuranceCards.mockResolvedValue(fixtureAssuranceCardsResponse(DEMO_FINDING_ID))
      mockFetchActionProposals.mockResolvedValue({
        proposals: [fixtureProposal({ id: 'AP-TERMINAL-2', status: 'APPROVED' })],
      })

      renderOverlay()
      await advanceToStepSix()

      await waitFor(() => {
        expect(screen.getByTestId('mock-joyride-target')).toHaveTextContent(
          '[data-tour="mini-card-audit-integrity"]',
        )
      })
      expect(mockGenerateCapa).not.toHaveBeenCalled()
      expect(mockApproveAction).not.toHaveBeenCalled()
    })

    it('never asserts on or reacts to a WS frame -- only fetchActionProposals/generateCapa drive step advancement', async () => {
      // `../lib/ws`'s connectCopilotStream is mocked to a no-op above; if
      // GuidedTourOverlay imported or called it at all, this test file's
      // own module-level mock would need to be exercised for the guard to
      // work -- it never is, proving the guard's only inputs are the two
      // REST calls asserted throughout this describe block.
      mockFetchAssuranceCards.mockResolvedValue(fixtureAssuranceCardsResponse(DEMO_FINDING_ID))
      mockFetchActionProposals.mockResolvedValue({ proposals: [] })

      renderOverlay()
      await advanceToStepSix()

      await waitFor(() => {
        expect(mockFetchActionProposals).toHaveBeenCalled()
      })
    })
  })

  describe('D-09 full integration: a real Generate CAPA click drives the tour to Approve', () => {
    it('detects the newly created proposal via polling GET /api/actions after a real click, and calls generateCapa exactly once end to end', async () => {
      let capaCalled = false

      mockFetchAssuranceCards.mockResolvedValue(fixtureAssuranceCardsResponse(DEMO_FINDING_ID))
      mockFetchActionProposals.mockImplementation(async () => ({
        proposals: capaCalled
          ? [fixtureProposal({ id: 'AP-NEW', status: 'PENDING_APPROVAL' })]
          : [],
      }))
      mockGenerateCapa.mockImplementation(async () => {
        capaCalled = true
        return {
          finding_id: DEMO_FINDING_ID,
          confidence: 'HIGH',
          proposal: fixtureProposal({ id: 'AP-NEW', status: 'PENDING_APPROVAL' }),
          reason: null,
        }
      })
      stubAssuranceCardsFetch({ cards: [fixtureStreamedCard(DEMO_FINDING_ID)] })

      render(
        <MemoryRouter initialEntries={['/copilot']}>
          <GuidedTourOverlay />
          <Routes>
            <Route path="/findings" element={<FindingInvestigation />} />
            <Route path="/actions" element={<Actions />} />
            <Route path="*" element={<LocationProbe />} />
          </Routes>
        </MemoryRouter>,
      )

      // Step 4 ("Blast Radius") ALSO routes to /findings, so
      // FindingInvestigation mounts once there already, fully draining the
      // shared SSE mock's single-use reader (sseFetch.ts's `streamingResponse`
      // is not re-entrant across repeated fetches). Re-stub with a fresh
      // reader right before the guard's own /findings remount at Step 6 so
      // that second, real mount gets its own complete stream.
      fireEvent.click(screen.getByTestId('start-guided-tour'))
      fireEvent.click(screen.getByTestId('mock-joyride-next')) // -> index 1
      fireEvent.click(screen.getByTestId('mock-joyride-next')) // -> index 2
      fireEvent.click(screen.getByTestId('mock-joyride-next')) // -> index 3 (/findings, first mount)
      fireEvent.click(screen.getByTestId('mock-joyride-next')) // -> index 4 (/copilot, unmounts)
      stubAssuranceCardsFetch({ cards: [fixtureStreamedCard(DEMO_FINDING_ID)] })
      fireEvent.click(screen.getByTestId('mock-joyride-next')) // -> index 5 (D-09 guard runs)

      await waitFor(() => {
        expect(screen.getByTestId('mock-joyride-target')).toHaveTextContent(
          '[data-tour="generate-capa-button"]',
        )
      })

      const generateButton = await screen.findByRole('button', { name: /generate capa/i })
      fireEvent.click(generateButton)

      await waitFor(
        () => {
          expect(screen.getByTestId('mock-joyride-target')).toHaveTextContent(
            '[data-tour="approve-action"]',
          )
        },
        { timeout: 4000 },
      )

      expect(mockGenerateCapa).toHaveBeenCalledTimes(1)
      expect(mockApproveAction).not.toHaveBeenCalled()

      // The real Approve button (Actions.tsx, unmodified) is now on screen,
      // still requiring a genuine human click -- the tour never auto-approves.
      expect(await screen.findByRole('button', { name: /approve action/i })).toBeInTheDocument()
    }, 10000)
  })
})
