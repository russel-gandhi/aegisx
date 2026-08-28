/**
 * Regression guard for debug session `guided-tour-copilot-next-stuck`.
 *
 * The Guided Tour froze on Step 2 ("Ask a Real Question"). Root cause was a
 * STRUCTURAL one that no existing test could see: `GuidedTourOverlay.test.tsx`
 * mocks the whole `react-joyride` module, so its stub "Next" button always
 * emits a well-formed STEP_AFTER regardless of what is actually on the page.
 * The real library renders a full-screen overlay with a spotlight cut-out and
 * intercepts pointer events everywhere outside it -- only the spotlighted
 * element stays interactive (v3 default `blockTargetInteraction: false`).
 *
 * Step 2 spotlighted the textarea alone while its copy told the user to
 * "submit it yourself". The "Ask Copilot" submit button sat OUTSIDE the
 * cut-out, under the overlay, so the click was swallowed (or read as an
 * overlay click that closed the step). The query was never sent, so
 * `[data-tour="copilot-messages"]` -- which renders only when
 * `messages.length > 0` and is Step 3's target -- never existed, and Step 3
 * became unreachable.
 *
 * The invariant these tests protect is therefore about DOM CONTAINMENT, not
 * layout, which makes it fully checkable in jsdom: *a tour step's spotlight
 * target must contain every control that step instructs the user to operate.*
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Copilot from '../pages/Copilot'
import { TOUR_STEPS, HERO_QUERY_TEXT } from '../lib/tourSteps'
import { stubAssuranceCardsFetch } from './helpers/sseFetch'

vi.mock('../lib/ws', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/ws')>()
  return {
    ...actual,
    connectCopilotStream: vi.fn(() => ({ close: vi.fn(), send: vi.fn() })),
  }
})

// 0-based Joyride step indexes. Steps 2 and 5 in the Bible's 1-based numbering
// both drive the Copilot composer and both require a real submit click.
const STEP_ASK_A_REAL_QUESTION = 1
const STEP_EVIDENCE_VERIFIED = 2
const STEP_AI_SAFETY = 4

function renderCopilot() {
  return render(
    <MemoryRouter initialEntries={['/copilot']}>
      <Copilot />
    </MemoryRouter>,
  )
}

describe('Guided Tour target reachability (structural spotlight contract)', () => {
  beforeEach(() => {
    stubAssuranceCardsFetch({ cards: [] })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('Step 2 spotlights an element that CONTAINS the submit button the step tells the user to click', () => {
    renderCopilot()

    const target = document.querySelector(TOUR_STEPS[STEP_ASK_A_REAL_QUESTION].target)
    expect(target).not.toBeNull()

    const submit = screen.getByRole('button', { name: /ask copilot/i })

    // The regression: the target used to be the textarea, which does not
    // contain the submit button, leaving it under the pointer-blocking
    // overlay and making the step's required action impossible.
    expect(target!.contains(submit)).toBe(true)
  })

  it('Step 2 spotlights an element that also contains the textarea (both controls, not just one)', () => {
    renderCopilot()

    const target = document.querySelector(TOUR_STEPS[STEP_ASK_A_REAL_QUESTION].target)
    const textarea = screen.getByPlaceholderText(/audit ready/i)

    expect(target!.contains(textarea)).toBe(true)
  })

  it('Step 5 (AI Safety) reuses the composer target, so its jailbreak submit is reachable too', () => {
    renderCopilot()

    // Same defect class: Step 5 also asks the user to submit a query.
    expect(TOUR_STEPS[STEP_AI_SAFETY].target).toBe(
      TOUR_STEPS[STEP_ASK_A_REAL_QUESTION].target,
    )

    const target = document.querySelector(TOUR_STEPS[STEP_AI_SAFETY].target)
    const submit = screen.getByRole('button', { name: /ask copilot/i })
    expect(target!.contains(submit)).toBe(true)
  })

  it('the spotlight target is NOT the bare textarea (the exact shape that caused the freeze)', () => {
    renderCopilot()

    const target = document.querySelector(TOUR_STEPS[STEP_ASK_A_REAL_QUESTION].target)
    // Boundary neighbour: the adjacent-but-wrong anchor. A textarea can never
    // contain a sibling button, so anchoring here is always unreachable.
    expect(target!.tagName).not.toBe('TEXTAREA')
  })

  it("Step 3's target does not exist before submit, and DOES exist after -- so submitting is its only precondition", async () => {
    renderCopilot()

    const step3Target = TOUR_STEPS[STEP_EVIDENCE_VERIFIED].target
    expect(document.querySelector(step3Target)).toBeNull()

    fireEvent.change(screen.getByPlaceholderText(/audit ready/i), {
      target: { value: HERO_QUERY_TEXT },
    })
    fireEvent.click(screen.getByRole('button', { name: /ask copilot/i }))

    await waitFor(() => {
      expect(document.querySelector(step3Target)).not.toBeNull()
    })
  })
})
