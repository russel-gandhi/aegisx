import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import {
  ApiError,
  listDocuments,
  uploadDocument,
  type DocumentSummary,
} from '../lib/api'

/**
 * Knowledge page (Phase 06.1, plan 06.1-05, RAG-01/RAG-07, D-10): a real
 * front door onto the ingestion pipeline `06.1-01`/`06.1-04` already built.
 * A user picks a system, uploads a document, watches its real ingestion
 * stages, and sees the indexed corpus the Copilot retrieves from.
 *
 * Stage honesty (D-10, the load-bearing constraint): there is no per-stage
 * push channel for uploads -- `uploadDocument()` is a single awaited call.
 * This page therefore NEVER advances a stage on a timer and never renders
 * a stage transition the backend has not actually reported. A document's
 * stage checklist is derived from exactly two sources: (1) while its own
 * upload request is in flight, from local state this page owns; (2) once
 * the response returns, from the response's own `status`/`failed_stage`
 * fields, cached locally per `document_id` since `GET /api/documents`
 * (06.1-04-SUMMARY.md's own documented decision) never re-derives
 * `failed_stage` at read time -- it would have to guess, and this page
 * inherits that same never-fabricate discipline rather than working around
 * it. A document loaded from `GET /api/documents` that this page did not
 * itself upload therefore shows a plain READY/FAILED checklist with no
 * specific failed stage highlighted, which is the honest limit of what the
 * server told it.
 *
 * `?system=`/`?document=` deep-link preselection and row highlighting are
 * plan 06.1-08's job (06.1-08-PLAN.md Task 3, "after plan 06.1-05") -- this
 * page establishes the row markup/keys that plan consumes, nothing more.
 */

export const KNOWLEDGE_SYSTEM_IDS = ['GXP-MFG-DEMO-01', 'BUS-IT-DEMO-02']

export const INGESTION_STAGE_LABELS = [
  'Uploading',
  'Parsing',
  'Structure',
  'Chunking',
  'Indexing',
  'Ready',
]

// 06.1-UI-SPEC.md Copywriting Contract, transcribed verbatim.
export const DROP_ZONE_COPY =
  'Drop GxP documents here — or use Browse files below. Supports PDF, DOCX, CSV, and plain text/Markdown.'
export const EMPTY_HEADING = 'No knowledge sources yet.'
export const EMPTY_BODY = 'Upload your GxP documents to begin an investigation.'
export const EMPTY_CTA = 'Add Knowledge'
export const UNSUPPORTED_TYPE_COPY =
  "This file type isn't supported. Nothing was uploaded — try a PDF, DOCX, CSV, or plain text/Markdown file."
export const TOO_LARGE_COPY =
  'This file is too large to upload. Nothing was uploaded — try a smaller file or split it into sections.'
export const SELECT_SYSTEM_HINT = 'Select a system first'

export function ingestionFailureCopy(stage: string): string {
  return `Processing stopped at ${stage} — the file was uploaded but not fully indexed, so it won't appear in retrieval yet. Try uploading it again.`
}

// Client-side pre-check only -- a convenience so an obviously-wrong file
// never leaves the browser. `detect_format`'s extension-AND-magic-bytes
// sniff on the backend remains the authority; its 415/413 responses (not
// this check) drive which copy actually renders on a rejected upload.
const SUPPORTED_EXTENSIONS = ['.pdf', '.docx', '.csv', '.md', '.txt']

function hasSupportedExtension(filename: string): boolean {
  const lower = filename.toLowerCase()
  return SUPPORTED_EXTENSIONS.some((extension) => lower.endsWith(extension))
}

function formatCreatedDate(createdDate: string | null): string {
  if (!createdDate) {
    return '—'
  }
  const parsed = new Date(createdDate)
  return Number.isNaN(parsed.getTime()) ? createdDate : parsed.toLocaleDateString()
}

interface StageGlyph {
  char: string
  className: string
}

type RowStageState =
  | { kind: 'uploading' }
  | { kind: 'ready' }
  | { kind: 'failed'; failedStageIndex: number | null }

function computeStageGlyphs(state: RowStageState): StageGlyph[] {
  return INGESTION_STAGE_LABELS.map((_, index) => {
    if (state.kind === 'uploading') {
      return index === 0
        ? { char: '◌', className: 'text-amber-600' }
        : { char: '-', className: 'text-slate-500' }
    }
    if (state.kind === 'ready') {
      return { char: '✓', className: 'text-emerald-600' }
    }
    // state.kind === 'failed'
    if (state.failedStageIndex === null) {
      return { char: '-', className: 'text-slate-500' }
    }
    if (index < state.failedStageIndex) {
      return { char: '✓', className: 'text-emerald-600' }
    }
    if (index === state.failedStageIndex) {
      return { char: '✕', className: 'text-red-400' }
    }
    return { char: '-', className: 'text-slate-500' }
  })
}

function failedStageIndexFor(failedStage: string | null | undefined): number | null {
  if (!failedStage) {
    return null
  }
  const index = INGESTION_STAGE_LABELS.findIndex(
    (label) => label.toLowerCase() === failedStage.toLowerCase(),
  )
  return index === -1 ? null : index
}

interface PendingUpload {
  tempId: string
  fileName: string
}

function StageChecklist({ state, documentId }: { state: RowStageState; documentId: string }) {
  const glyphs = computeStageGlyphs(state)
  return (
    <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs">
      {INGESTION_STAGE_LABELS.map((label, index) => (
        <span
          key={label}
          data-testid={`stage-glyph-${documentId}-${label}`}
          className="flex items-center gap-1"
        >
          <span className={`transition-colors duration-300 ${glyphs[index].className}`}>
            {glyphs[index].char}
          </span>
          <span className="text-slate-400">{label}</span>
        </span>
      ))}
    </div>
  )
}

export default function Knowledge() {
  const [systemId, setSystemId] = useState('')
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [inlineError, setInlineError] = useState<string | null>(null)
  const [pendingUpload, setPendingUpload] = useState<PendingUpload | null>(null)
  const [failedStageByDocumentId, setFailedStageByDocumentId] = useState<Record<string, string>>({})
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    let cancelled = false
    listDocuments()
      .then((result) => {
        if (!cancelled) {
          setDocuments(result.documents)
        }
      })
      .catch(() => {
        // Honest empty state on a load failure -- no fabricated error
        // banner outside the Copywriting Contract; the empty state (or
        // whatever the last-known list was) simply stays as-is.
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function handleFile(file: File) {
    if (!systemId) {
      return
    }
    setInlineError(null)

    if (!hasSupportedExtension(file.name)) {
      setInlineError(UNSUPPORTED_TYPE_COPY)
      return
    }

    setPendingUpload({ tempId: crypto.randomUUID(), fileName: file.name })

    try {
      const result = await uploadDocument(file, systemId)
      if (result.status === 'FAILED' && result.failed_stage) {
        setFailedStageByDocumentId((prev) => ({
          ...prev,
          [result.document_id]: result.failed_stage as string,
        }))
      }
      // Refetch so this row's persisted values (title, doc_type, version,
      // created_date, chunk_count) come from the server, not from the
      // upload response alone.
      const list = await listDocuments()
      setDocuments(list.documents)
      setPendingUpload(null)
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.status === 413) {
          setInlineError(TOO_LARGE_COPY)
        } else if (error.status === 415) {
          setInlineError(UNSUPPORTED_TYPE_COPY)
        } else {
          setInlineError(error.detail)
        }
      } else {
        setInlineError(TOO_LARGE_COPY)
      }
      setPendingUpload(null)
    }
  }

  function handleBrowseClick() {
    fileInputRef.current?.click()
  }

  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (file) {
      void handleFile(file)
    }
  }

  function handleDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    const file = event.dataTransfer.files?.[0]
    if (file) {
      void handleFile(file)
    }
  }

  const isEmpty = documents.length === 0 && pendingUpload === null

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-100">Knowledge</h1>
      <p className="mt-2 max-w-2xl text-slate-400">
        Upload GxP documents to build the indexed corpus Copilot retrieves evidence from --
        every ingestion stage below reflects real backend state, never a fabricated progress
        animation.
      </p>

      <div className="mt-6 lg:mt-6">
        <h2 className="text-lg font-semibold text-slate-100">Add Knowledge</h2>

        <div className="mt-3">
          <label htmlFor="knowledge-system" className="text-sm text-slate-400">
            System
          </label>
          <select
            id="knowledge-system"
            data-testid="knowledge-system-select"
            className="ml-2 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm text-slate-100"
            value={systemId}
            onChange={(event) => setSystemId(event.target.value)}
          >
            <option value="">Select a system…</option>
            {KNOWLEDGE_SYSTEM_IDS.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
        </div>

        <div
          data-testid="knowledge-drop-zone"
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          className="mt-3 flex min-h-[160px] flex-col items-center justify-center rounded border border-dashed border-slate-800 bg-slate-900/50 p-4 text-center"
        >
          <p className="max-w-md text-sm text-slate-400">{DROP_ZONE_COPY}</p>
          <button
            type="button"
            data-testid="browse-files-button"
            disabled={!systemId}
            onClick={handleBrowseClick}
            className="mt-3 rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Browse files
          </button>
          {!systemId && (
            <p data-testid="select-system-hint" className="mt-1 text-xs text-slate-400">
              {SELECT_SYSTEM_HINT}
            </p>
          )}
          <input
            ref={fileInputRef}
            type="file"
            data-testid="knowledge-file-input"
            className="hidden"
            onChange={handleInputChange}
          />
        </div>

        {inlineError && (
          <p data-testid="knowledge-inline-error" className="mt-2 text-sm text-red-400">
            {inlineError}
          </p>
        )}
      </div>

      <div className="mt-6 lg:mt-6">
        {isEmpty ? (
          <div
            data-testid="knowledge-empty-state"
            className="rounded border border-slate-800 bg-slate-900/50 p-6 text-center"
          >
            <p className="text-lg font-semibold text-slate-100">{EMPTY_HEADING}</p>
            <p className="mt-1 text-sm text-slate-400">{EMPTY_BODY}</p>
            <button
              type="button"
              data-testid="knowledge-empty-cta"
              disabled={!systemId}
              onClick={handleBrowseClick}
              className="mt-3 rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {EMPTY_CTA}
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {pendingUpload && (
              <div
                key={pendingUpload.tempId}
                data-testid={`knowledge-source-row-${pendingUpload.tempId}`}
                className="rounded border border-slate-800 bg-slate-900 p-4 transition-all duration-300 ease-out"
              >
                <p
                  className="truncate text-sm font-medium text-slate-100"
                  title={pendingUpload.fileName}
                >
                  {pendingUpload.fileName}
                </p>
                <p className="mt-1 text-xs text-slate-400">Uploading…</p>
                <StageChecklist state={{ kind: 'uploading' }} documentId={pendingUpload.tempId} />
              </div>
            )}
            {documents.map((doc) => {
              const cachedFailedStage = failedStageByDocumentId[doc.document_id] ?? doc.failed_stage
              const stageState: RowStageState =
                doc.ingestion_status === 'READY'
                  ? { kind: 'ready' }
                  : { kind: 'failed', failedStageIndex: failedStageIndexFor(cachedFailedStage) }

              return (
                <div
                  key={doc.document_id}
                  data-testid={`knowledge-source-row-${doc.document_id}`}
                  className="rounded border border-slate-800 bg-slate-900 p-4 transition-all duration-300 ease-out"
                >
                  <p className="truncate text-sm font-medium text-slate-100" title={doc.title}>
                    {doc.title}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    {doc.doc_type} · {doc.version ?? '—'} · {doc.ingestion_status} ·{' '}
                    {formatCreatedDate(doc.created_date)} · {doc.chunk_count} indexed units
                  </p>
                  {cachedFailedStage && (
                    <p className="mt-1 text-xs text-red-400">
                      {ingestionFailureCopy(cachedFailedStage)}
                    </p>
                  )}
                  <StageChecklist state={stageState} documentId={doc.document_id} />
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
