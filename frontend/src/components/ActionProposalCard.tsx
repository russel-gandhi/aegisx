import { useState } from 'react'
import type { ActionProposalData } from '../lib/api'

// Pure presentation, per REM-03 and Bible Section 11.6: this component is a
// window onto server-trusted state. It performs no fetch, no arithmetic, no
// grading, and holds no fallback that would let a missing server field be
// replaced by a client-invented one -- a client-side default here would be
// exactly the LLM-generated-UI failure mode the requirement forbids. Every
// rendered value reads from the `proposal` prop and nothing else. The card
// owns no async state of its own -- `busy`/`error` are supplied by the page,
// which owns the approve/reject request lifecycle.
export interface ActionProposalCardProps {
  proposal: ActionProposalData
  onApprove: (id: string) => void
  onReject: (id: string) => void
  busy: 'approving' | 'rejecting' | null
  error: string | null
}

export const STATUS_STYLES: Record<string, string> = {
  PENDING_APPROVAL: 'border-amber-700 bg-amber-950/40',
  APPROVED: 'border-emerald-700 bg-emerald-950/40',
  EXECUTED: 'border-emerald-700 bg-emerald-950/40',
  REJECTED: 'border-red-700 bg-red-950/40',
  BLOCKED: 'border-orange-700 bg-orange-950/40',
}

export const STATUS_BADGE_STYLES: Record<string, string> = {
  PENDING_APPROVAL: 'bg-amber-700 text-amber-50',
  APPROVED: 'bg-emerald-700 text-emerald-50',
  EXECUTED: 'bg-emerald-700 text-emerald-50',
  REJECTED: 'bg-red-700 text-red-50',
  BLOCKED: 'bg-orange-700 text-orange-50',
}

function SectionLabel({ children }: { children: string }) {
  return (
    <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{children}</p>
  )
}

export default function ActionProposalCard({
  proposal,
  onApprove,
  onReject,
  busy,
  error,
}: ActionProposalCardProps) {
  const [confirmingReject, setConfirmingReject] = useState(false)

  const borderStyle = STATUS_STYLES[proposal.status] ?? 'border-slate-700 bg-slate-900/40'
  const badgeStyle = STATUS_BADGE_STYLES[proposal.status] ?? 'bg-slate-700 text-slate-50'
  const isPending = proposal.status === 'PENDING_APPROVAL'
  const isBusy = busy !== null

  return (
    <div
      data-testid="action-proposal-card"
      data-status={proposal.status}
      className={`rounded-lg border p-4 ${borderStyle}`}
    >
      <p className="text-sm text-slate-500">{proposal.id}</p>

      <div className="mt-3">
        <SectionLabel>ACTION TYPE</SectionLabel>
        <p className="mt-1 text-sm text-slate-100">{proposal.action_type}</p>
      </div>

      <div className="mt-3">
        <SectionLabel>CATEGORY</SectionLabel>
        <p className="mt-1 text-sm text-slate-100">{proposal.category ?? 'Not provided'}</p>
      </div>

      <div className="mt-3">
        <SectionLabel>TARGET SYSTEM</SectionLabel>
        <p className="mt-1 text-sm text-slate-100">{proposal.target_system}</p>
      </div>

      <div className="mt-3">
        <SectionLabel>JUSTIFICATION</SectionLabel>
        <p className="mt-1 whitespace-pre-wrap text-sm text-slate-100">
          {proposal.justification ?? 'Not provided'}
        </p>
      </div>

      <div className="mt-3">
        <SectionLabel>PAYLOAD</SectionLabel>
        <pre className="mt-1 max-h-48 overflow-auto rounded bg-slate-950 p-2 text-xs text-slate-300">
          {JSON.stringify(proposal.payload, null, 2)}
        </pre>
      </div>

      <div className="mt-3">
        <SectionLabel>STATUS</SectionLabel>
        <span
          className={`mt-1 inline-block rounded px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${badgeStyle}`}
        >
          {proposal.status}
        </span>
      </div>

      {isPending && (
        <div className="mt-4 border-t border-slate-800 pt-3">
          {confirmingReject ? (
            <div>
              <p className="text-sm text-slate-200">
                {`Reject Action: Reject this ${proposal.action_type} on ${proposal.target_system}? It will not be executed. This decision is recorded in the audit trail and cannot be undone.`}
              </p>
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  disabled={isBusy}
                  onClick={() => {
                    setConfirmingReject(false)
                    onReject(proposal.id)
                  }}
                  className="rounded bg-red-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-600 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {busy === 'rejecting' ? 'Rejecting...' : 'Confirm Reject'}
                </button>
                <button
                  type="button"
                  disabled={isBusy}
                  onClick={() => setConfirmingReject(false)}
                  className="rounded px-3 py-1.5 text-sm font-medium text-slate-400 hover:bg-slate-800 hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="flex gap-2">
              <button
                type="button"
                disabled={isBusy}
                onClick={() => onApprove(proposal.id)}
                data-tour="approve-action"
                className="rounded bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-600 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {busy === 'approving' ? 'Approving...' : 'Approve Action'}
              </button>
              <button
                type="button"
                disabled={isBusy}
                onClick={() => setConfirmingReject(true)}
                className="rounded bg-red-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-600 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {busy === 'rejecting' ? 'Rejecting...' : 'Reject Action'}
              </button>
            </div>
          )}
          {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
        </div>
      )}
    </div>
  )
}
