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
  arrowColor: '#0f172a', // slate-900
  backgroundColor: '#0f172a', // slate-900
  overlayColor: 'rgba(2, 6, 23, 0.75)', // slate-950 @ 75%
  primaryColor: '#059669', // emerald-600
  textColor: '#f1f5f9', // slate-100
  width: 400,
}

const JOYRIDE_STYLES = {
  spotlight: {
    style: {
      filter: 'drop-shadow(0 0 4px rgba(5, 150, 105, 0.4))', // emerald-600 glow, not a new hue
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
      className="max-w-[400px] rounded border border-slate-700 bg-slate-900 p-4 text-slate-100 shadow-lg"
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
        {`Step ${index + 1} of ${TOUR_STEPS.length}`}
      </p>
      {step.title !== undefined && (
        <p className="mt-1 text-lg font-semibold text-slate-100">{step.title}</p>
      )}
      <div className="mt-2 text-sm text-slate-200">{step.content}</div>
      <div className="mt-4 flex items-center justify-between gap-2">
        <button
          type="button"
          {...skipProps}
          className="text-sm text-slate-400 hover:text-slate-200"
        >
          Explore Freely
        </button>
        <div className="flex gap-2">
          {index > 0 && (
            <button
              type="button"
              {...backProps}
              className="rounded px-3 py-1.5 text-sm font-medium text-slate-300 hover:bg-slate-800"
            >
              Back
            </button>
          )}
          <button
            type="button"
            {...primaryProps}
            className="rounded bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-600"
          >
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
      }
    }
  }

  const steps: Step[] = TOUR_STEPS.map((s, idx) => {
    if (idx === REMEDIATION_STEP_INDEX) {
      if (remediationPhase === 'approve') {
        return {
          target: '[data-tour="approve-action"]',
          title: s.title,
          content: skipNote ?? APPROVE_PHASE_CONTENT,
        }
      }
      return { target: s.target, title: s.title, content: s.content }
    }
    if (s.target === '') {
      // Closing step (id:8): a centered, target-less modal per react-joyride's
      // documented pattern for a final "you're done" message.
      return { target: 'body', placement: 'center', title: s.title, content: s.content }
    }
    return { target: s.target, title: s.title, content: s.content }
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
          className="fixed bottom-20 right-6 z-50 max-w-xs rounded border border-amber-700 bg-amber-950/80 p-3 text-sm text-amber-200"
        >
          {skipNote}
        </div>
      )}
      {targetNotFoundNote !== null && (
        <div
          data-testid="tour-target-not-found-note"
          className="fixed bottom-20 right-6 z-50 max-w-xs rounded border border-amber-700 bg-amber-950/80 p-3 text-sm text-amber-200"
        >
          {targetNotFoundNote}
        </div>
      )}
      {!run && (
        <button
          type="button"
          data-testid="start-guided-tour"
          onClick={start}
          className="fixed bottom-6 right-6 z-50 rounded bg-emerald-700 px-4 py-2 text-sm font-medium text-white shadow-lg hover:bg-emerald-600"
        >
          Start Guided Tour
        </button>
      )}
    </>
  )
}
