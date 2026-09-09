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

// `insufficient_evidence` describes RAG retrieval ONLY -- it means no
// document passage cleared the relevance threshold. It says nothing about
// whether a compliance finding was verified, because A2/A4..A6 findings are
// corroborated against Postgres and OPA directly and legitimately cite zero
// retrieved passages.
//
// Rendering the two as one status produced the worst possible frame: a
// finding C1 graded HIGH, with db_record_found and opa_corroborated both
// true, displayed under an "INSUFFICIENT EVIDENCE" badge -- the exact
// inverse of what the pipeline actually concluded. The helpers below keep
// the two questions separate: did retrieval find passages, and did C1
// verify the findings.

const VERIFIED_CONFIDENCES = new Set(['HIGH', 'MEDIUM'])

/** True when C1 corroborated at least one finding against real DB/OPA state. */
function hasVerifiedFinding(result: CopilotInvestigateResult): boolean {
  return result.findings.some((f) => {
    const verdict = result.verification_results[f.finding_id]
    return verdict !== undefined && VERIFIED_CONFIDENCES.has(verdict.confidence)
  })
}

function answeredTone(result: CopilotInvestigateResult): 'verified' | 'unverified' {
  return hasVerifiedFinding(result) ? 'verified' : 'unverified'
}

function headlineVerdict(result: CopilotInvestigateResult): string {
  if (hasVerifiedFinding(result)) return 'VERIFIED FINDING'
  if (result.findings.length > 0) return 'FINDING — UNVERIFIED'
  return 'NO EVIDENCE RETRIEVED'
}

function confidenceBadge(confidence: string | undefined): string {
  switch (confidence) {
    case 'HIGH':
      return 'badge-mint'
    case 'MEDIUM':
      return 'badge-blue'
    case 'LOW':
      return 'badge-amber'
    default:
      return 'badge-neutral'
  }
}

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
  // A question passes when C1 verified a finding for it in time -- NOT when
  // RAG happened to return passages. Scoring on `insufficient_evidence`
  // marked every deterministic compliance answer (which cites zero
  // retrieved passages by design) as a failure.
  const passedCount = Object.values(states).filter(
    (s) => s.phase === 'answered' && hasVerifiedFinding(s.result) && s.elapsedSeconds <= TIME_LIMIT_SECONDS,
  ).length

  return (
    <div>
      <p className="eyebrow">Timed challenge</p>
      <h1 className="mt-1 text-[28px] font-bold text-ink">Inspection Readiness Simulator</h1>
      <p className="mt-2 max-w-2xl text-[13.5px] text-ink-muted">
        Ten FDA-inspector-style questions, each answered live through the real Copilot pipeline
        with cited evidence &mdash; the same 30-second bar the Bible sets for a credible audit-prep
        demo.
      </p>

      <div className="mt-6 flex items-center gap-4">
        <div className="flex gap-1.5">
          {QUESTIONS.map((q, i) => {
            const s = states[q.id]
            const dotClass =
              s.phase === 'answered' && hasVerifiedFinding(s.result)
                ? 'bg-mint'
                : s.phase === 'answered' || s.phase === 'timed_out'
                  ? 'bg-orange'
                  : s.phase === 'error'
                    ? 'bg-red'
                    : i === current
                      ? 'bg-ink-muted'
                      : 'bg-white/15'
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
        <span className="text-sm text-ink-faint">
          {answeredCount}/10 answered &middot; {passedCount} passed
        </span>
      </div>

      <div data-tour="inspection-simulator-panel" className="card mt-6 p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="eyebrow">
              Question {current + 1} of 10
            </p>
            <p className="mt-1 text-sm text-orange">{question.observation}</p>
            <p className="mt-3 text-lg text-ink">&ldquo;{question.query}&rdquo;</p>
          </div>
          {state.phase === 'running' && (
            <div
              data-testid="countdown"
              className={`shrink-0 rounded-full border px-3 py-1.5 text-center text-lg font-semibold tabular-nums ${
                state.secondsLeft <= 10
                  ? 'border-red-500/30 bg-red-soft text-red'
                  : 'border-white/[0.14] bg-white/[0.06] text-ink'
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
              className="btn btn-success"
            >
              Start Question
            </button>
          )}

          {state.phase === 'running' && (
            <p className="text-sm text-ink-muted">
              Copilot is retrieving evidence and verifying against real database and policy state&hellip;
            </p>
          )}

          {state.phase === 'timed_out' && (
            <div className="rounded-xl border border-orange/30 bg-orange-soft p-4">
              <p className="font-medium text-orange">Timed out</p>
              <p className="mt-1 text-sm text-ink-muted">
                No answer within {TIME_LIMIT_SECONDS}s. This counts against readiness the same way a
                slow response would in a real inspection.
              </p>
            </div>
          )}

          {state.phase === 'error' && (
            <p className="text-sm text-red">The request failed. Check that the backend is reachable.</p>
          )}

          {state.phase === 'answered' && (
            <div
              className={`rounded-xl border p-4 ${
                answeredTone(state.result) === 'verified'
                  ? 'border-mint/30 bg-mint-soft'
                  : 'border-orange/30 bg-orange-soft'
              }`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`badge ${
                    answeredTone(state.result) === 'verified' ? 'badge-mint' : 'badge-orange'
                  }`}
                >
                  {headlineVerdict(state.result)}
                </span>
                <span className="font-mono text-xs text-ink-faint">{state.elapsedSeconds.toFixed(1)}s</span>
                {/* Retrieval count is about RAG passages only. It is NOT a
                    statement about whether a finding was verified -- a
                    deterministic A2/A4-plus-OPA finding legitimately cites
                    zero retrieved excerpts. Labelled so it can never again
                    be read as "this finding has no evidence". */}
                <span className="text-xs text-ink-faint">
                  &middot; {state.result.evidence.length} retrieved passage
                  {state.result.evidence.length === 1 ? '' : 's'}
                </span>
              </div>
              {state.result.findings.length > 0 && (
                <ul className="mt-3 space-y-3">
                  {state.result.findings.map((f) => {
                    // C1's real verdict, keyed by finding_id. Never read the
                    // finding's own confidence field -- every agent hardcodes
                    // it to "UNVERIFIED" (see CopilotVerificationResult in
                    // lib/api, and the backend contract test that enforces
                    // this: tests/test_confidence_field_contract.py).
                    const verdict = state.result.verification_results[f.finding_id]
                    return (
                      <li key={f.finding_id} className="text-sm text-ink-muted">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`badge ${confidenceBadge(verdict?.confidence)}`}>
                            {verdict ? `C1 ${verdict.confidence}` : 'C1 NOT RUN'}
                          </span>
                          <span className="font-mono text-xs text-ink-faint">
                            [{f.regulatory_citations.join(', ')}]
                          </span>
                        </div>
                        <p className="mt-1">{f.claim}</p>
                        {verdict && (
                          <p className="mt-1 font-mono text-xs text-ink-faint">
                            {verdict.db_record_found ? 'DB record found' : 'no DB record'}
                            {' · '}
                            {verdict.opa_corroborated ? 'OPA corroborated' : 'not OPA corroborated'}
                            {verdict.evidence_ids.length > 0 && ` · ${verdict.evidence_ids.join(', ')}`}
                          </p>
                        )}
                      </li>
                    )
                  })}
                </ul>
              )}
              {/* When insufficient_evidence fires but findings exist, the
                  server's generic RAG-empty copy ("found nothing relevant")
                  would directly contradict the findings list just rendered
                  above it -- those findings ARE the answer, just sourced
                  from A2/OPA compliance checks rather than RAG evidence.
                  Suppress the generic fallback text in that case; it stays
                  for the true no-findings-either case. */}
              {state.result.answer && !(state.result.insufficient_evidence && state.result.findings.length > 0) && (
                <p className="mt-3 text-sm text-ink-muted">{state.result.answer}</p>
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
          className="btn btn-secondary disabled:cursor-not-allowed disabled:opacity-40"
        >
          Previous
        </button>
        <button
          type="button"
          onClick={() => setCurrent((c) => Math.min(QUESTIONS.length - 1, c + 1))}
          disabled={current === QUESTIONS.length - 1}
          className="btn btn-secondary disabled:cursor-not-allowed disabled:opacity-40"
        >
          Next
        </button>
      </div>
    </div>
  )
}
