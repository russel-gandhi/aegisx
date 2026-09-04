import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  Joyride,
  ACTIONS,
  STATUS,
  EVENTS,
  type EventData,
  type Step,
  type TooltipRenderProps,
} from 'react-joyride'
import {
  HERO_QUERY_TEXT,
  HERO_SYSTEM_ID,
  JAILBREAK_QUERY_TEXT,
  TOUR_STEPS,
} from '../lib/tourSteps'
import { fetchActionProposals, fetchAssuranceCards, type ActionProposalData } from '../lib/api'

// react-joyride 3.2.0's theming lives in the top-level `options` prop (its
// `Options` type has no `spotlightShadow` field -- that was a v2-only
// `styles.options` key). The five values below are transcribed verbatim
// from 06-UI-SPEC.md's Animation Contract; `spotlightShadow` is applied
// separately via `styles.spotlight` as a CSS filter approximation (see
// SUMMARY.md Deviations for why the exact box-shadow value could not be
// reproduced on an SVG spotlight path).
const JOYRIDE_OPTIONS = {
  arrowColor: '#111726', // --color-surface-2, matches TourTooltip's glass panel
  backgroundColor: '#111726', // --color-surface-2
  overlayColor: 'rgba(5, 7, 13, 0.75)', // --color-canvas @ 75%
  primaryColor: '#2fd889', // --color-mint
  textColor: '#f3f5fb', // --color-ink
  width: 400,
  // This tour requires REAL user clicks on real product controls (submit the
  // hero query, Generate CAPA, Approve). react-joyride's default
  // `overlayClickAction: 'close'` turns any click that lands on the overlay
  // -- including a mis-aimed click at a control just outside the spotlight --
  // into an ACTIONS.CLOSE that tears the step down with no way back. For a
  // guided demo that is never the desired behaviour: a stray click should be
  // inert, not fatal.
  overlayClickAction: false as const,
}

// Steps whose target only exists AFTER real backend work completes get a
// generous wait instead of react-joyride's 1000ms default. The library polls
// for the target every 100ms and self-heals to LIFECYCLE.READY the moment it
// appears, so a slow stream degrades into a short wait rather than a
// TARGET_NOT_FOUND dead-end (which, in controlled mode, the library will NOT
// auto-recover from -- it only self-advances when `controlled === false`).
const ASYNC_TARGET_WAIT_MS = 15000
const ASYNC_TARGET_STEP_INDEXES = new Set([
  2, // "Evidence, Verified" -- [data-tour="copilot-messages"] renders only after the hero query is submitted and streams
  3, // "Blast Radius" -- FindingInvestigation must load its finding first
  6, // "Audit Integrity" -- CommandCentre mini-cards await /api/audit/verify
])

const JOYRIDE_STYLES = {
  spotlight: {
    style: {
      filter: 'drop-shadow(0 0 4px rgba(47, 216, 137, 0.4))', // --color-mint glow, not a new hue
    },
  },
}

// Index (0-based) of the last real Joyride step -- also the total step
// count minus one, since Task 2 maps every TOUR_STEPS entry (including the
// id:8 closing message) onto a Joyride step via a centered `target: 'body'`
// step rather than a separate custom overlay (see below).
const LAST_STEP_INDEX = TOUR_STEPS.length - 1
// Index (0-based) of Step 6, "Controlled Remediation" -- the only step with
// a two-phase sub-state (D-09).
const REMEDIATION_STEP_INDEX = 5

// Step counter is rendered here, not by react-joyride's own `showProgress`
// option, so its exact copy ("Step N of 8") and Label styling match
// 06-UI-SPEC.md's Typography table precisely.
function TourTooltip({
  index,
  step,
  isLastStep,
  backProps,
  primaryProps,
  skipProps,
}: TooltipRenderProps) {
  return (
    <div
      data-testid="tour-tooltip"
      className="glass max-w-[400px] rounded-xl p-5 text-ink shadow-float"
    >
      <p className="text-[11px] font-bold tracking-[0.1em] text-accent-2 uppercase">
        {`Step ${index + 1} of ${TOUR_STEPS.length}`}
      </p>
      {step.title !== undefined && (
        <p className="mt-1.5 text-lg font-semibold text-ink">{step.title}</p>
      )}
      <div className="mt-2 text-sm text-ink-muted">{step.content}</div>
      <div className="mt-4 flex items-center justify-between gap-2">
        <button type="button" {...skipProps} className="text-sm text-ink-faint hover:text-ink">
          Explore Freely
        </button>
        <div className="flex gap-2">
          {index > 0 && (
            <button type="button" {...backProps} className="btn btn-secondary">
              Back
            </button>
          )}
          <button type="button" {...primaryProps} className="btn btn-success">
            {isLastStep ? 'Restart Tour' : 'Next'}
          </button>
        </div>
      </div>
    </div>
  )
}

// D-09 skip-forward copy (06-UI-SPEC.md Copywriting Contract, "Guided Tour,
// step precondition missing" row). `seeded` uses the "seed-and-continue"
// variant (a pending proposal already exists, reused instead of minting a
// new one); the non-seeded variant is used when the existing proposal is
// already terminal and the tour skips straight to Step 7.
export const SEED_AND_CONTINUE_COPY =
  'This step needs a fresh action proposal -- the tour found one already pending and will use it instead.'
export const SKIP_FORWARD_COPY =
  'This finding already has a decided action proposal -- skipping ahead to Audit Integrity rather than re-attempting an already-terminal action.'
export const TARGET_NOT_FOUND_COPY =
  "Still waiting for this step's target to appear on the page..."
export const APPROVE_PHASE_CONTENT =
  'Approve this real, already-generated CAPA proposal -- GxP-relevant writes stay PENDING until a human signs off.'

// D-09 idempotency guard, pure and independently testable: given the demo
// finding's id and the current /api/actions list, decides whether Step 6
// should guide a fresh Generate CAPA click, jump straight to an existing
// pending proposal's Approve click, or skip the step entirely because the
// proposal is already in a terminal state (06-RESEARCH.md Pitfall 2).
export type RemediationDecision =
  | { kind: 'generate' }
  | { kind: 'approve'; proposalId: string; seeded: boolean }
  | { kind: 'skip'; proposalId: string }

export function resolveRemediationDecision(
  findingId: string,
  proposals: ActionProposalData[],
): RemediationDecision {
  const existing = proposals.find((p) => p.finding_id === findingId)
  if (existing === undefined) {
    return { kind: 'generate' }
  }
  if (existing.status === 'PENDING_APPROVAL') {
    return { kind: 'approve', proposalId: existing.id, seeded: true }
  }
  return { kind: 'skip', proposalId: existing.id }
}

function stepRoute(index: number): string {
  return TOUR_STEPS[index]?.route ?? ''
}

function prefillForStep(index: number): string | undefined {
  if (index === 1) return HERO_QUERY_TEXT
  if (index === 4) return JAILBREAK_QUERY_TEXT
  return undefined
}

export default function GuidedTourOverlay() {
  const navigate = useNavigate()
  const location = useLocation()
  const [run, setRun] = useState(false)
  const [stepIndex, setStepIndex] = useState(0)
  const [targetNotFoundNote, setTargetNotFoundNote] = useState<string | null>(null)
  // D-09 state: null while the guard hasn't resolved yet for the current
  // Step 6 entry (renders the static 'generate'-shaped default target).
  const [remediationPhase, setRemediationPhase] = useState<'generate' | 'approve' | null>(null)
  const [demoFindingId, setDemoFindingId] = useState<string | null>(null)
  const [skipNote, setSkipNote] = useState<string | null>(null)

  function start() {
    setStepIndex(0)
    setRun(true)
    setTargetNotFoundNote(null)
    setRemediationPhase(null)
    setSkipNote(null)
    navigate('/')
  }

  function reset() {
    setRun(false)
    setStepIndex(0)
    setTargetNotFoundNote(null)
    setRemediationPhase(null)
    setDemoFindingId(null)
    setSkipNote(null)
  }

  // Route + prefill navigation for every step except Step 6 (index 5,
  // Controlled Remediation), which the dedicated D-09 guard effect below
  // navigates itself once it has decided which phase to enter.
  useEffect(() => {
    if (!run || stepIndex === REMEDIATION_STEP_INDEX) {
      return
    }
    const route = stepRoute(stepIndex)
    if (route === '' || location.pathname === route) {
      return
    }
    const prefillQuery = prefillForStep(stepIndex)
    navigate(route, prefillQuery !== undefined ? { state: { prefillQuery } } : undefined)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run, stepIndex])

  // D-09 guard: runs once per Step 6 entry. Never listens to the
  // session-agnostic `action_proposal_created` WS broadcast (06-RESEARCH.md
  // Pitfall 4) -- every decision here comes from a direct GET /api/actions
  // re-fetch, keyed on the specific demo finding_id.
  useEffect(() => {
    if (!run || stepIndex !== REMEDIATION_STEP_INDEX) {
      return
    }
    let cancelled = false
    setSkipNote(null)

    fetchAssuranceCards(HERO_SYSTEM_ID)
      .then((cardsResponse) => {
        if (cancelled) return undefined
        const findingId = cardsResponse.cards[0]?.finding_id
        if (findingId === undefined) {
          // No open finding for the demo system -- nothing to guard
          // against; fall back to the generate phase so the page still
          // renders something coherent.
          setDemoFindingId(null)
          setRemediationPhase('generate')
          navigate('/findings')
          return undefined
        }
        setDemoFindingId(findingId)
        return fetchActionProposals().then((actionsResponse) => {
          if (cancelled) return
          const decision = resolveRemediationDecision(findingId, actionsResponse.proposals)
          if (decision.kind === 'generate') {
            setRemediationPhase('generate')
            navigate('/findings')
          } else if (decision.kind === 'approve') {
            setRemediationPhase('approve')
            if (decision.seeded) {
              setSkipNote(SEED_AND_CONTINUE_COPY)
            }
            navigate('/actions')
          } else {
            setSkipNote(SKIP_FORWARD_COPY)
            setRemediationPhase(null)
            setStepIndex(REMEDIATION_STEP_INDEX + 1)
          }
        })
      })
      .catch(() => {
        if (cancelled) return
        setRemediationPhase('generate')
        navigate('/findings')
      })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run, stepIndex])

  // While waiting on a real human click of the real "Generate CAPA" button
  // (this component never calls generateCapa() itself -- 06-UI-SPEC.md's
  // <behavior> requires a real click, not a synthetic one), poll the real
  // GET /api/actions endpoint for the newly created proposal. This is the
  // Pitfall-4-safe re-fetch, never a WS listener.
  useEffect(() => {
    if (
      !run ||
      stepIndex !== REMEDIATION_STEP_INDEX ||
      remediationPhase !== 'generate' ||
      demoFindingId === null
    ) {
      return
    }
    let cancelled = false
    const interval = setInterval(() => {
      fetchActionProposals()
        .then((response) => {
          if (cancelled) return
          const created = response.proposals.find((p) => p.finding_id === demoFindingId)
          if (created !== undefined) {
            setRemediationPhase('approve')
            navigate('/actions')
          }
        })
        .catch(() => {
          // A transient poll failure is not fatal -- the next tick retries.
        })
    }, 1000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [run, stepIndex, remediationPhase, demoFindingId, navigate])

  function handleEvent(data: EventData) {
    const { status, action, type } = data
    if (status === STATUS.FINISHED) {
      // The primary button on the closing step reads "Restart Tour" -- an
      // explicit NEXT/primary click there restarts immediately; the Skip
      // ("Explore Freely") button just ends the tour (06-UI-SPEC.md step 8:
      // "offers Restart Tour / Explore Freely").
      if (action === ACTIONS.NEXT) {
        start()
      } else {
        reset()
      }
      return
    }
    if (status === STATUS.SKIPPED) {
      reset()
      return
    }
    if (type === EVENTS.TARGET_NOT_FOUND) {
      setTargetNotFoundNote(TARGET_NOT_FOUND_COPY)
      return
    }
    if (type === EVENTS.STEP_AFTER) {
      setTargetNotFoundNote(null)
      if (action === ACTIONS.NEXT) {
        setStepIndex((i) => Math.min(i + 1, LAST_STEP_INDEX))
      } else if (action === ACTIONS.PREV) {
        setStepIndex((i) => Math.max(i - 1, 0))
      } else if (action === ACTIONS.CLOSE) {
        // A CLOSE here means the step was torn down without a navigation
        // decision (dismiss key, close button, or -- before
        // `overlayClickAction: false` -- a stray overlay click). Joyride's own
        // lifecycle has already completed, so leaving `stepIndex` untouched
        // would strand the tour with no tooltip and no way forward. Ending
        // cleanly returns the user to the "Start Guided Tour" entry point
        // instead of a frozen overlay.
        reset()
      }
    }
  }

  const steps: Step[] = TOUR_STEPS.map((s, idx) => {
    const waitOverride = ASYNC_TARGET_STEP_INDEXES.has(idx)
      ? { targetWaitTimeout: ASYNC_TARGET_WAIT_MS }
      : {}
    // `skipBeacon` on every step: react-joyride's default is a pulsing
    // dot the user must find and click before the tooltip explaining that
    // step even appears -- for a "Start Guided Tour" click a visitor just
    // made, a silent beacon with no visible instruction reads as broken,
    // not as an invitation. The tooltip should be what appears immediately.
    if (idx === REMEDIATION_STEP_INDEX) {
      if (remediationPhase === 'approve') {
        return {
          target: '[data-tour="approve-action"]',
          title: s.title,
          content: skipNote ?? APPROVE_PHASE_CONTENT,
          targetWaitTimeout: ASYNC_TARGET_WAIT_MS,
          skipBeacon: true,
        }
      }
      return { target: s.target, title: s.title, content: s.content, skipBeacon: true, ...waitOverride }
    }
    if (s.target === '') {
      // Closing step (id:8): a centered, target-less modal per react-joyride's
      // documented pattern for a final "you're done" message.
      return { target: 'body', placement: 'center', title: s.title, content: s.content, skipBeacon: true }
    }
    return { target: s.target, title: s.title, content: s.content, skipBeacon: true, ...waitOverride }
  })

  return (
    <>
      {run && (
        <Joyride
          steps={steps}
          run={run}
          stepIndex={stepIndex}
          continuous
          locale={{ skip: 'Explore Freely' }}
          options={JOYRIDE_OPTIONS}
          styles={JOYRIDE_STYLES}
          tooltipComponent={TourTooltip}
          onEvent={handleEvent}
        />
      )}
      {run && skipNote !== null && (
        <div
          data-testid="tour-skip-note"
          className="glass fixed right-6 bottom-20 z-50 max-w-xs rounded-xl border-amber-500/25 bg-amber-soft p-3 text-sm text-amber"
        >
          {skipNote}
        </div>
      )}
      {targetNotFoundNote !== null && (
        <div
          data-testid="tour-target-not-found-note"
          className="glass fixed right-6 bottom-20 z-50 max-w-xs rounded-xl border-amber-500/25 bg-amber-soft p-3 text-sm text-amber"
        >
          {targetNotFoundNote}
        </div>
      )}
      {!run && (
        <button
          type="button"
          data-testid="start-guided-tour"
          onClick={start}
          className="btn btn-success fixed right-6 bottom-6 z-50"
        >
          Start Guided Tour
        </button>
      )}
    </>
  )
}
