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
import { HERO_QUERY_TEXT, JAILBREAK_QUERY_TEXT, TOUR_STEPS } from '../lib/tourSteps'

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
            {isLastStep ? 'Finish' : 'Next'}
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

  function start() {
    setStepIndex(0)
    setRun(true)
    setTargetNotFoundNote(null)
    navigate('/')
  }

  function reset() {
    setRun(false)
    setStepIndex(0)
    setTargetNotFoundNote(null)
  }

  // Route + prefill navigation for every non-remediation step. Step 6
  // (index 5, Controlled Remediation) is handled by Task 2's dedicated D-09
  // guard effect -- this effect intentionally skips it.
  useEffect(() => {
    if (!run || stepIndex === 5) {
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

  function handleEvent(data: EventData) {
    const { status, action, type } = data
    if (status === STATUS.FINISHED || status === STATUS.SKIPPED) {
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
        setStepIndex((i) => Math.min(i + 1, TOUR_STEPS.length - 1))
      } else if (action === ACTIONS.PREV) {
        setStepIndex((i) => Math.max(i - 1, 0))
      }
    }
  }

  const steps: Step[] = TOUR_STEPS.filter((s) => s.target !== '').map((s) => ({
    target: s.target,
    title: s.title,
    content: s.content,
  }))

  return (
    <>
      {run && (
        <Joyride
          steps={steps}
          run={run}
          stepIndex={Math.min(stepIndex, steps.length - 1)}
          continuous
          locale={{ skip: 'Explore Freely' }}
          options={JOYRIDE_OPTIONS}
          styles={JOYRIDE_STYLES}
          tooltipComponent={TourTooltip}
          onEvent={handleEvent}
        />
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
