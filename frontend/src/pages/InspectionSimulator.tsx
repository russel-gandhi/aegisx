import { useEffect, useRef, useState } from 'react'
import { investigateCopilot, type CopilotInvestigateResult } from '../lib/api'

// Bible Section 11.9: "A timed challenge simulating an FDA inspector's
// line of questioning based on common 483 observations... The Copilot
// must retrieve cited evidence and answer each of the 10 seeded
// questions in under 30 seconds." Every question below targets a real,
// already-seeded GXP-MFG-DEMO-01 finding this session verified live
// (periodic evaluation, traceability, risk review, change control,
// incident RCA, access review, privileged access, supplier
// qualification) -- the "seeding" is these fixed prompts, not a new
// database table, and every answer is a real `POST /api/copilot/investigate`
// call through the live C2->A0->[A1..A6]->C1->A7->C3 pipeline, not a
// canned response.
const DEMO_SYSTEM = 'GXP-MFG-DEMO-01'
const TIME_LIMIT_SECONDS = 30

interface InspectionQuestion {
  id: string
  observation: string
  query: string
}

const QUESTIONS: InspectionQuestion[] = [
  {
    id: 'Q1',
    observation: '483 Observation: Periodic review deficiency',
    query: 'Is the periodic evaluation for GXP-MFG-DEMO-01 current, or is it overdue for review?',
  },
  {
    id: 'Q2',
    observation: '483 Observation: Requirements traceability gap',
    query: 'Does every requirement in GXP-MFG-DEMO-01 have linked, approved test case evidence?',
  },
  {
    id: 'Q3',
    observation: '483 Observation: Risk assessment currency (ICH Q9)',
    query: 'Are all risk assessments for GXP-MFG-DEMO-01 within their required review cycle?',
  },
  {
    id: 'Q4',
    observation: '483 Observation: CAPA / change-control completeness',
    query: 'Are all change control actions closed for changes marked as closed on GXP-MFG-DEMO-01?',
  },
  {
    id: 'Q5',
    observation: '483 Observation: Incident investigation timeliness',
    query: 'Are there any open P1 incidents on GXP-MFG-DEMO-01 without a completed root cause analysis?',
  },
  {
    id: 'Q6',
    observation: '483 Observation: Access review currency',
    query: 'Is the privileged access review for GXP-MFG-DEMO-01 up to date?',
  },
  {
    id: 'Q7',
    observation: '483 Observation: Segregation of duties / orphaned access',
    query: 'Are there any privileged accounts still active for users who have departed on GXP-MFG-DEMO-01?',
  },
  {
    id: 'Q8',
    observation: '483 Observation: Supplier qualification currency',
    query: 'Are all suppliers for GXP-MFG-DEMO-01 within their reassessment schedule?',
  },
  {
    id: 'Q9',
    observation: '483 Observation: Document control / traceability evidence',
    query: 'Is there a User Requirements Specification on file for GXP-MFG-DEMO-01, and is it approved?',
  },
  {
    id: 'Q10',
    observation: '483 Observation: Overall audit readiness',
    query: 'Is GXP-MFG-DEMO-01 audit ready?',
  },
]

type QuestionState =
  | { phase: 'not_started' }
  | { phase: 'running'; secondsLeft: number }
  | { phase: 'timed_out' }
  | { phase: 'answered'; result: CopilotInvestigateResult; elapsedSeconds: number }
  | { phase: 'error' }

export default function InspectionSimulator() {
  const [current, setCurrent] = useState(0)
  const [states, setStates] = useState<Record<string, QuestionState>>(() =>
    Object.fromEntries(QUESTIONS.map((q) => [q.id, { phase: 'not_started' }])),
  )
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => () => {
    if (intervalRef.current) clearInterval(intervalRef.current)
  }, [])

  const question = QUESTIONS[current]
  const state = states[question.id]

  const startQuestion = () => {
    const startedAt = Date.now()
    setStates((prev) => ({ ...prev, [question.id]: { phase: 'running', secondsLeft: TIME_LIMIT_SECONDS } }))

    intervalRef.current = setInterval(() => {
      setStates((prev) => {
        const entry = prev[question.id]
        if (entry.phase !== 'running') return prev
        const secondsLeft = entry.secondsLeft - 1
        if (secondsLeft <= 0) {
          if (intervalRef.current) clearInterval(intervalRef.current)
          return { ...prev, [question.id]: { phase: 'timed_out' } }
        }
        return { ...prev, [question.id]: { phase: 'running', secondsLeft } }
      })
    }, 1000)

    investigateCopilot(question.query, DEMO_SYSTEM)
      .then((result) => {
        if (intervalRef.current) clearInterval(intervalRef.current)
        const elapsedSeconds = (Date.now() - startedAt) / 1000
        setStates((prev) =>
          prev[question.id].phase === 'timed_out'
            ? prev
            : { ...prev, [question.id]: { phase: 'answered', result, elapsedSeconds } },
        )
      })
      .catch(() => {
        if (intervalRef.current) clearInterval(intervalRef.current)
        setStates((prev) => ({ ...prev, [question.id]: { phase: 'error' } }))
      })
  }

  const answeredCount = Object.values(states).filter((s) => s.phase === 'answered').length
  const passedCount = Object.values(states).filter(
    (s) => s.phase === 'answered' && !s.result.insufficient_evidence && s.elapsedSeconds <= TIME_LIMIT_SECONDS,
  ).length

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-100">Inspection Readiness Simulator</h1>
      <p className="mt-2 max-w-2xl text-slate-400">
        Ten FDA-inspector-style questions, each answered live through the real Copilot pipeline
        with cited evidence &mdash; the same 30-second bar the Bible sets for a credible audit-prep
        demo.
      </p>

      <div className="mt-6 flex items-center gap-4">
        <div className="flex gap-1.5">
          {QUESTIONS.map((q, i) => {
            const s = states[q.id]
            const dotClass =
              s.phase === 'answered' && !s.result.insufficient_evidence
                ? 'bg-emerald-500'
                : s.phase === 'answered' || s.phase === 'timed_out'
                  ? 'bg-orange-500'
                  : s.phase === 'error'
                    ? 'bg-red-500'
                    : i === current
                      ? 'bg-slate-400'
                      : 'bg-slate-700'
            return (
              <button
                key={q.id}
                type="button"
                onClick={() => setCurrent(i)}
                aria-label={`Go to question ${i + 1}`}
                className={`h-2.5 w-2.5 rounded-full transition-colors ${dotClass}`}
              />
            )
          })}
        </div>
        <span className="text-sm text-slate-500">
          {answeredCount}/10 answered &middot; {passedCount} passed
        </span>
      </div>

      <div className="mt-6 rounded-lg border border-slate-800 bg-slate-900 p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Question {current + 1} of 10
            </p>
            <p className="mt-1 text-sm text-orange-300">{question.observation}</p>
            <p className="mt-3 text-lg text-slate-100">&ldquo;{question.query}&rdquo;</p>
          </div>
          {state.phase === 'running' && (
            <div
              data-testid="countdown"
              className={`shrink-0 rounded-full border px-3 py-1.5 text-center text-lg font-semibold tabular-nums ${
                state.secondsLeft <= 10
                  ? 'border-red-700 bg-red-950/40 text-red-300'
                  : 'border-slate-700 bg-slate-800 text-slate-200'
              }`}
            >
              {state.secondsLeft}s
            </div>
          )}
        </div>

        <div className="mt-5">
          {state.phase === 'not_started' && (
            <button
              type="button"
              onClick={startQuestion}
              className="rounded bg-emerald-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-600"
            >
              Start Question
            </button>
          )}

          {state.phase === 'running' && (
            <p className="text-sm text-slate-400">
              Copilot is retrieving evidence and verifying against real database and policy state&hellip;
            </p>
          )}

          {state.phase === 'timed_out' && (
            <div className="rounded-lg border border-orange-800 bg-orange-950/30 p-4">
              <p className="font-medium text-orange-300">Timed out</p>
              <p className="mt-1 text-sm text-slate-400">
                No answer within {TIME_LIMIT_SECONDS}s. This counts against readiness the same way a
                slow response would in a real inspection.
              </p>
            </div>
          )}

          {state.phase === 'error' && (
            <p className="text-sm text-red-400">The request failed. Check that the backend is reachable.</p>
          )}

          {state.phase === 'answered' && (
            <div
              className={`rounded-lg border p-4 ${
                state.result.insufficient_evidence
                  ? 'border-orange-800 bg-orange-950/20'
                  : 'border-emerald-800 bg-emerald-950/10'
              }`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                    state.result.insufficient_evidence
                      ? 'border-orange-700 bg-orange-950/50 text-orange-300'
                      : 'border-emerald-700 bg-emerald-950/50 text-emerald-300'
                  }`}
                >
                  {state.result.insufficient_evidence ? 'INSUFFICIENT EVIDENCE' : 'ANSWERED'}
                </span>
                <span className="font-mono text-xs text-slate-500">{state.elapsedSeconds.toFixed(1)}s</span>
                <span className="text-xs text-slate-500">&middot; {state.result.evidence.length} evidence items</span>
              </div>
              {state.result.findings.length > 0 && (
                <ul className="mt-3 space-y-2">
                  {state.result.findings.map((f) => (
                    <li key={f.finding_id} className="text-sm text-slate-300">
                      <span className="font-mono text-xs text-slate-500">[{f.regulatory_citations.join(', ')}]</span>{' '}
                      {f.claim}
                    </li>
                  ))}
                </ul>
              )}
              {state.result.answer && (
                <p className="mt-3 text-sm text-slate-300">{state.result.answer}</p>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="mt-4 flex justify-between">
        <button
          type="button"
          onClick={() => setCurrent((c) => Math.max(0, c - 1))}
          disabled={current === 0}
          className="rounded border border-slate-700 bg-slate-800 px-3 py-1.5 text-sm text-slate-200 transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Previous
        </button>
        <button
          type="button"
          onClick={() => setCurrent((c) => Math.min(QUESTIONS.length - 1, c + 1))}
          disabled={current === QUESTIONS.length - 1}
          className="rounded border border-slate-700 bg-slate-800 px-3 py-1.5 text-sm text-slate-200 transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Next
        </button>
      </div>
    </div>
  )
}
