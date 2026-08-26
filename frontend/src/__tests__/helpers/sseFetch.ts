/**
 * Shared SSE mock-response builder for tests exercising `streamAssuranceCards`
 * (frontend/src/lib/api.ts) via a stubbed global `fetch`. This is the single
 * place that encodes the wire format -- no test file hand-rolls its own
 * stream frame text (quick task 260827-0ls, closing the coverage hole left
 * by 260826-p1q).
 *
 * Filename deliberately has no `.test.` segment: vitest's default include
 * pattern is name-based (`**\/*.{test,spec}.*`), so a plain `.ts` file here
 * would be collected as a suite and fail for containing no tests.
 */
import { vi } from 'vitest'
import type { AssuranceCardData, AssuranceCardStreamFrame } from '../../lib/api'

// The longer of the two sibling assurance-cards paths. This page no longer
// requests the blocking sibling at all, so no branch is needed for it.
export const ASSURANCE_CARDS_STREAM_PATH = '/assurance-cards/stream'

/**
 * Serialises stream frames to the SSE wire text `streamAssuranceCards`
 * parses: one `data: <json>` line per frame, each terminated by a literal
 * blank line.
 */
export function sseBody(frames: AssuranceCardStreamFrame[]): string {
  return frames.map((frame) => `data: ${JSON.stringify(frame)}\n\n`).join('')
}

interface FakeReader {
  read: () => Promise<{ value: Uint8Array | undefined; done: boolean }>
}

interface MockResponse {
  ok: boolean
  status: number
  json: () => Promise<unknown>
  body: { getReader: () => FakeReader } | null
}

/**
 * Wraps wire text in a mock `Response`-shaped object whose `body.getReader()`
 * yields the text back as `TextEncoder`-encoded `Uint8Array` chunks --
 * `TextDecoder.decode` rejects a plain string at runtime, and `vi.stubGlobal`
 * erases the type so nothing else catches that mistake. When `chunkSize` is
 * omitted the whole body is emitted as one slice; otherwise it is split into
 * `chunkSize`-byte pieces to exercise cross-chunk frame buffering.
 */
export function streamingResponse(body: string, chunkSize?: number): MockResponse {
  const bytes = new TextEncoder().encode(body)
  const chunks: Uint8Array[] = []
  if (chunkSize === undefined || chunkSize >= bytes.length) {
    if (bytes.length > 0) {
      chunks.push(bytes)
    }
  } else {
    for (let offset = 0; offset < bytes.length; offset += chunkSize) {
      chunks.push(bytes.slice(offset, offset + chunkSize))
    }
  }

  let index = 0
  const reader: FakeReader = {
    read: async () => {
      if (index < chunks.length) {
        const value = chunks[index]
        index += 1
        return { value, done: false }
      }
      return { value: undefined, done: true }
    },
  }

  return {
    ok: true,
    status: 200,
    json: async () => ({}),
    body: { getReader: () => reader },
  }
}

export interface AssuranceCardsStreamOptions {
  systemId?: string
  chunkSize?: number
  errorDetail?: string
  omitTerminator?: boolean
}

/**
 * Composes `sseBody` + `streamingResponse` for the common case: one `card`
 * frame per entry in `cards`, then a terminal frame -- `done` carrying
 * `systemId` and `cards.length`, or `error` carrying `errorDetail` when
 * supplied instead of a done frame. `omitTerminator` drops the trailing
 * blank line after the last frame, forcing the reader-done remainder flush.
 */
export function assuranceCardsStreamResponse(
  cards: AssuranceCardData[],
  options?: AssuranceCardsStreamOptions,
): MockResponse {
  const systemId = options?.systemId ?? 'GXP-MFG-DEMO-01'
  const frames: AssuranceCardStreamFrame[] = cards.map((card) => ({
    event: 'card',
    card,
  }))
  frames.push(
    options?.errorDetail !== undefined
      ? { event: 'error', detail: options.errorDetail }
      : { event: 'done', system_id: systemId, count: cards.length },
  )

  let body = sseBody(frames)
  if (options?.omitTerminator && body.endsWith('\n\n')) {
    body = body.slice(0, -2)
  }
  return streamingResponse(body, options?.chunkSize)
}

export interface JsonResponseOptions {
  ok?: boolean
  status?: number
}

/**
 * The ordinary `{ ok, status, json }` shape for routes that legitimately
 * stay plain JSON (evidence-graph, generate-capa).
 */
export function jsonResponse(payload: unknown, options?: JsonResponseOptions): MockResponse {
  return {
    ok: options?.ok ?? true,
    status: options?.status ?? 200,
    json: async () => payload,
    body: null,
  }
}

export interface ExtraRoute {
  match: (url: string, init?: RequestInit) => boolean
  respond: (url: string, init?: RequestInit) => Promise<MockResponse> | MockResponse
}

export interface StubAssuranceCardsFetchOptions {
  cards?: AssuranceCardData[]
  systemId?: string
  chunkSize?: number
  errorDetail?: string
  omitTerminator?: boolean
  graph?: unknown
  graphReject?: boolean
  extraRoutes?: ExtraRoute[]
}

/**
 * Installs a `vi.fn` fetch router via `vi.stubGlobal`, returning the mock so
 * callers can assert on calls. Routes in priority order: any `extraRoutes`
 * entry first (so a caller can add e.g. a POST generate-capa branch without
 * a second router), then the assurance-cards stream path, then
 * `/evidence-graph`, then a rejected promise naming the unstubbed URL --
 * preserving the existing suite's fail-loud convention.
 */
export function stubAssuranceCardsFetch(options?: StubAssuranceCardsFetchOptions) {
  const streamResponse = assuranceCardsStreamResponse(options?.cards ?? [], {
    systemId: options?.systemId,
    chunkSize: options?.chunkSize,
    errorDetail: options?.errorDetail,
    omitTerminator: options?.omitTerminator,
  })
  const defaultGraph = { system_id: options?.systemId ?? 'GXP-MFG-DEMO-01', nodes: [], edges: [] }

  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    for (const route of options?.extraRoutes ?? []) {
      if (route.match(url, init)) {
        return Promise.resolve(route.respond(url, init))
      }
    }
    if (url.includes(ASSURANCE_CARDS_STREAM_PATH)) {
      return Promise.resolve(streamResponse)
    }
    if (url.includes('/evidence-graph')) {
      if (options?.graphReject) {
        return Promise.reject(new Error('network down'))
      }
      return Promise.resolve(jsonResponse(options?.graph ?? defaultGraph))
    }
    return Promise.reject(new Error(`unstubbed fetch: ${url}`))
  })

  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
