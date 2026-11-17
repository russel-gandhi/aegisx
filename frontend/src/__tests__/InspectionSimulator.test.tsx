import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import InspectionSimulator from '../pages/InspectionSimulator'
import type { CopilotInvestigateResult, CopilotVerificationResult } from '../lib/api'

vi.mock('../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/api')>()
  return {
    ...actual,
    investigateCopilot: vi.fn(),
  }
})

import { investigateCopilot } from '../lib/api'

const mockInvestigateCopilot = vi.mocked(investigateCopilot)

const GENERIC_FALLBACK_TEXT = /found nothing relevant enough to ground/i

function fixtureResult(overrides: Partial<CopilotInvestigateResult> = {}): CopilotInvestigateResult {
  return {
    answer: '',
    insufficient_evidence: false,
    blocked: false,
    blocked_reason: null,
    evidence: [],
    stages: [],
    findings: [],
    verification_results: {},
    evidence_support: 'HIGH',
    model_attribution: 'gemini-2.5-flash',
    navigation_target: null,
    ...overrides,
  }
}

/**
 * A finding as the API really emits it: `confidence_score` is ALWAYS the
 * literal "UNVERIFIED" placeholder every agent hardcodes, never a grade.
 * Tests must not put a real grade here, or they stop reproducing the
 * production shape and let the placeholder-reading bug back in.
 */
function fixtureFinding(findingId: string, claim: string, citation: string) {
  return {
    finding_id: findingId,
    claim,
    regulatory_citations: [citation],
    confidence_score: 'UNVERIFIED',
    evidence_ids: [],
    alcoa_score: {},
    model_attribution: 'openai/gpt-oss-120b',
  }
}

function fixtureVerdict(overrides: Partial<CopilotVerificationResult> = {}): CopilotVerificationResult {
  return {
    confidence: 'HIGH',
    db_record_found: true,
    opa_corroborated: true,
    opa_rule_ids: ['ANNEX11-S10-CHG-001'],
    evidence_ids: ['CR-2026-089'],
    ...overrides,
  }
}

async function startFirstQuestion() {
  render(<InspectionSimulator />)
  const startButton = await screen.findByRole('button', { name: 'Start Question' })
  startButton.click()
}

describe('InspectionSimulator verdict rendering', () => {
  it('shows C1 HIGH — not "insufficient evidence" — for a deterministic finding with zero retrieved passages', async () => {
    // The exact Q4 production shape: RAG retrieved nothing (compliance
    // findings come from Postgres + OPA, not the document corpus), yet C1
    // verified the finding at HIGH. Previously this rendered under an
    // "INSUFFICIENT EVIDENCE" badge, inverting the pipeline's conclusion.
    mockInvestigateCopilot.mockResolvedValue(
      fixtureResult({
        insufficient_evidence: true,
        evidence: [],
        evidence_support: 'INSUFFICIENT_EVIDENCE',
        answer: '',
        findings: [
          fixtureFinding(
            'A4-ANNEX11-S10-CHG-001-CR-2026-089',
            'Change CR-2026-089 is CLOSED but linked action CA-2026-089-1 remains OPEN.',
            'ANNEX11-S10-CHG-001',
          ),
        ],
        verification_results: {
          'A4-ANNEX11-S10-CHG-001-CR-2026-089': fixtureVerdict(),
        },
      }),
    )

    await startFirstQuestion()

    expect(await screen.findByText(/CR-2026-089 is CLOSED/)).toBeInTheDocument()
    expect(screen.getByText('VERIFIED FINDING')).toBeInTheDocument()
    expect(screen.getByText('C1 HIGH')).toBeInTheDocument()
    expect(screen.queryByText('INSUFFICIENT EVIDENCE')).not.toBeInTheDocument()
  })

  it('surfaces the deterministic corroboration behind the grade', async () => {
    mockInvestigateCopilot.mockResolvedValue(
      fixtureResult({
        insufficient_evidence: true,
        findings: [fixtureFinding('F-1', 'Some compliance gap.', 'ANNEX11-S10-CHG-001')],
        verification_results: { 'F-1': fixtureVerdict() },
      }),
    )

    await startFirstQuestion()

    // The whole product thesis, on screen: a real record and an
    // independent policy evaluation stand behind the claim.
    expect(await screen.findByText(/DB record found/)).toBeInTheDocument()
    expect(screen.getByText(/OPA corroborated/)).toBeInTheDocument()
    expect(screen.getByText(/CR-2026-089/)).toBeInTheDocument()
  })

  it('does not treat the finding-level confidence_score placeholder as a grade', async () => {
    // Regression guard for the documented trap: confidence_score is always
    // "UNVERIFIED" regardless of C1's real verdict. A page reading it would
    // show an unverified finding here; the correct source says HIGH.
    mockInvestigateCopilot.mockResolvedValue(
      fixtureResult({
        insufficient_evidence: true,
        findings: [fixtureFinding('F-1', 'Some compliance gap.', 'ANNEX11-S10-CHG-001')],
        verification_results: { 'F-1': fixtureVerdict({ confidence: 'HIGH' }) },
      }),
    )

    await startFirstQuestion()

    expect(await screen.findByText('C1 HIGH')).toBeInTheDocument()
    expect(screen.queryByText('C1 UNVERIFIED')).not.toBeInTheDocument()
    expect(screen.queryByText('FINDING — UNVERIFIED')).not.toBeInTheDocument()
  })

  it('marks a finding unverified when C1 produced no verdict for it', async () => {
    // Fail-closed: a finding with no matching verification entry must never
    // borrow the confident styling of a verified one.
    mockInvestigateCopilot.mockResolvedValue(
      fixtureResult({
        insufficient_evidence: true,
        findings: [fixtureFinding('F-1', 'Unverified compliance claim.', 'ANNEX11-S10-CHG-001')],
        verification_results: {},
      }),
    )

    await startFirstQuestion()

    expect(await screen.findByText('FINDING — UNVERIFIED')).toBeInTheDocument()
    expect(screen.getByText('C1 NOT RUN')).toBeInTheDocument()
    expect(screen.queryByText('VERIFIED FINDING')).not.toBeInTheDocument()
  })

  it('labels the retrieval count as passages, never as evidence for the finding', async () => {
    mockInvestigateCopilot.mockResolvedValue(
      fixtureResult({
        insufficient_evidence: true,
        evidence: [],
        findings: [fixtureFinding('F-1', 'Some compliance gap.', 'ANNEX11-S10-CHG-001')],
        verification_results: { 'F-1': fixtureVerdict() },
      }),
    )

    await startFirstQuestion()

    expect(await screen.findByText(/0 retrieved passages/)).toBeInTheDocument()
    expect(screen.queryByText(/0 evidence items/)).not.toBeInTheDocument()
  })

  it('still shows the generic fallback text when there is no evidence and no findings', async () => {
    mockInvestigateCopilot.mockResolvedValue(
      fixtureResult({
        insufficient_evidence: true,
        evidence: [],
        evidence_support: 'INSUFFICIENT_EVIDENCE',
        answer:
          'Insufficient evidence to answer this question. AegisX searched the indexed knowledge base ' +
          'and found nothing relevant enough to ground an answer — try rephrasing, or upload a document ' +
          'that covers this topic.',
        findings: [],
      }),
    )

    await startFirstQuestion()

    await waitFor(() => expect(screen.getByText('NO EVIDENCE RETRIEVED')).toBeInTheDocument())
    expect(screen.getByText(GENERIC_FALLBACK_TEXT)).toBeInTheDocument()
  })

  it('unaffected: answered questions with real evidence still show the answer text', async () => {
    mockInvestigateCopilot.mockResolvedValue(
      fixtureResult({
        insufficient_evidence: false,
        evidence_support: 'HIGH',
        answer: 'Yes, the periodic evaluation is current.',
        findings: [],
      }),
    )

    await startFirstQuestion()

    expect(await screen.findByText('Yes, the periodic evaluation is current.')).toBeInTheDocument()
  })
})
