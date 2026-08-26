import { describe, it, expect, vi, afterEach } from 'vitest'
import { streamAssuranceCards } from '../lib/api'
import type { AssuranceCardData } from '../lib/api'
import { assuranceCardsStreamResponse, jsonResponse, sseBody, streamingResponse } from './helpers/sseFetch'

// Direct contract coverage for `streamAssuranceCards` (frontend/src/lib/api.ts),
// which had zero tests of its own before this quick task -- precisely why
// nothing failed at merge time when 260826-p1q shipped it (260827-0ls plan).
// Fixture values are prefixed `FIXTURE-` so no assertion can pass on the
// wrong field.
const FIXTURE_CARD_A: AssuranceCardData = {
  finding_id: 'A2-FIXTURE-STREAM-01',
  claim: 'FIXTURE-STATEMENT-stream contract test card A',
  evidence_ids: ['FIXTURE-RECORD-STREAM-A'],
  regulatory_citations: ['FIXTURE-CITATION-STREAM-A'],
  deterministic_check: {
    check_name: 'FIXTURE-CHECKFN-stream-a',
    passed: false,
    db_record_found: true,
    opa_corroborated: true,
    opa_rule_ids: ['FIXTURE-CITATION-STREAM-A'],
  },
  confidence: 'MEDIUM',
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
  model_attribution: 'FIXTURE-MODEL-ID-stream-a',
}

const FIXTURE_CARD_B: AssuranceCardData = {
  ...FIXTURE_CARD_A,
  finding_id: 'A2-FIXTURE-STREAM-02',
  claim: 'FIXTURE-STATEMENT-stream contract test card B',
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('streamAssuranceCards', () => {
  it('dispatches each card frame in order then the terminal done frame', async () => {
    const response = assuranceCardsStreamResponse([FIXTURE_CARD_A, FIXTURE_CARD_B], {
      systemId: 'GXP-MFG-DEMO-01',
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
    const onCard = vi.fn()
    const onDone = vi.fn()
    const onError = vi.fn()

    await streamAssuranceCards('GXP-MFG-DEMO-01', { onCard, onDone, onError })

    expect(onCard).toHaveBeenCalledTimes(2)
    expect(onCard).toHaveBeenNthCalledWith(1, FIXTURE_CARD_A)
    expect(onCard).toHaveBeenNthCalledWith(2, FIXTURE_CARD_B)
    expect(onDone).toHaveBeenCalledTimes(1)
    expect(onDone).toHaveBeenCalledWith('GXP-MFG-DEMO-01', 2)
    expect(onError).not.toHaveBeenCalled()
  })

  it('dispatches only the terminal done frame with count 0 for an empty card list', async () => {
    const response = assuranceCardsStreamResponse([], { systemId: 'GXP-MFG-DEMO-01' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
    const onCard = vi.fn()
    const onDone = vi.fn()
    const onError = vi.fn()

    await streamAssuranceCards('GXP-MFG-DEMO-01', { onCard, onDone, onError })

    expect(onCard).not.toHaveBeenCalled()
    expect(onDone).toHaveBeenCalledTimes(1)
    expect(onDone).toHaveBeenCalledWith('GXP-MFG-DEMO-01', 0)
    expect(onError).not.toHaveBeenCalled()
  })

  it('dispatches exactly one complete card when its frame arrives split across 1-byte chunks', async () => {
    const response = assuranceCardsStreamResponse([FIXTURE_CARD_A], {
      systemId: 'GXP-MFG-DEMO-01',
      chunkSize: 1,
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
    const onCard = vi.fn()
    const onDone = vi.fn()
    const onError = vi.fn()

    await streamAssuranceCards('GXP-MFG-DEMO-01', { onCard, onDone, onError })

    expect(onCard).toHaveBeenCalledTimes(1)
    expect(onCard).toHaveBeenCalledWith(FIXTURE_CARD_A)
    expect(onDone).toHaveBeenCalledWith('GXP-MFG-DEMO-01', 1)
  })

  it('dispatches an in-stream error frame to onError without calling onCard or onDone', async () => {
    const response = assuranceCardsStreamResponse([], {
      errorDetail: 'FIXTURE-DETAIL-upstream unavailable',
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
    const onCard = vi.fn()
    const onDone = vi.fn()
    const onError = vi.fn()

    await streamAssuranceCards('GXP-MFG-DEMO-01', { onCard, onDone, onError })

    expect(onError).toHaveBeenCalledTimes(1)
    expect(onError).toHaveBeenCalledWith('FIXTURE-DETAIL-upstream unavailable')
    expect(onCard).not.toHaveBeenCalled()
    expect(onDone).not.toHaveBeenCalled()
  })

  it('still dispatches a final card frame with no trailing blank line, via the reader-done remainder flush', async () => {
    const body = sseBody([{ event: 'card', card: FIXTURE_CARD_A }]).slice(0, -2)
    const response = streamingResponse(body)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
    const onCard = vi.fn()
    const onDone = vi.fn()
    const onError = vi.fn()

    await streamAssuranceCards('GXP-MFG-DEMO-01', { onCard, onDone, onError })

    expect(onCard).toHaveBeenCalledTimes(1)
    expect(onCard).toHaveBeenCalledWith(FIXTURE_CARD_A)
    expect(onDone).not.toHaveBeenCalled()
    expect(onError).not.toHaveBeenCalled()
  })

  it('rejects with an ApiError carrying the parsed status and detail for a non-2xx response', async () => {
    const response = jsonResponse(
      { detail: 'FIXTURE-DETAIL-service unavailable' },
      { ok: false, status: 503 },
    )
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
    const onCard = vi.fn()
    const onDone = vi.fn()
    const onError = vi.fn()

    await expect(
      streamAssuranceCards('GXP-MFG-DEMO-01', { onCard, onDone, onError }),
    ).rejects.toMatchObject({
      status: 503,
      detail: 'FIXTURE-DETAIL-service unavailable',
    })
    expect(onCard).not.toHaveBeenCalled()
    expect(onDone).not.toHaveBeenCalled()
    expect(onError).not.toHaveBeenCalled()
  })
})
