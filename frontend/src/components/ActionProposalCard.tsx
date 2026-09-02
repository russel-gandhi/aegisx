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
  PENDING_APPROVAL: 'border-l-amber',
  APPROVED: 'border-l-mint',
  EXECUTED: 'border-l-mint',
  REJECTED: 'border-l-red',
  BLOCKED: 'border-l-orange',
}

export const STATUS_BADGE_STYLES: Record<string, string> = {
  PENDING_APPROVAL: 'badge-amber',
  APPROVED: 'badge-mint',
  EXECUTED: 'badge-mint',
  REJECTED: 'badge-red',
  BLOCKED: 'badge-orange',
}

function SectionLabel({ children }: { children: string }) {
  return <p className="text-[11px] font-bold tracking-[0.08em] text-ink-faint uppercase">{children}</p>
}

export default function ActionProposalCard({
  proposal,
  onApprove,
  onReject,
  busy,
  error,
}: ActionProposalCardProps) {
  const [confirmingReject, setConfirmingReject] = useState(false)

  const borderStyle = STATUS_STYLES[proposal.status] ?? 'border-l-white/20'
  const badgeStyle = STATUS_BADGE_STYLES[proposal.status] ?? 'badge-neutral'
  const isPending = proposal.status === 'PENDING_APPROVAL'
  const isBusy = busy !== null

  return (
    <div
      data-testid="action-proposal-card"
      data-status={proposal.status}
      className={`card border-l-[3px] p-5 ${borderStyle}`}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="font-mono text-[11px] text-ink-faint">{proposal.id}</p>
        <span className={`badge ${badgeStyle}`}>{proposal.status}</span>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <SectionLabel>Action type</SectionLabel>
          <p className="mt-1 text-[13.5px] text-ink">{proposal.action_type}</p>
        </div>

        <div>
          <SectionLabel>Category</SectionLabel>
          <p className="mt-1 text-[13.5px] text-ink">{proposal.category ?? 'Not provided'}</p>
        </div>

        <div>
          <SectionLabel>Target system</SectionLabel>
          <p className="mt-1 font-mono text-[13px] text-ink">{proposal.target_system}</p>
        </div>
      </div>

      <div className="mt-4">
        <SectionLabel>Justification</SectionLabel>
        <p className="mt-1 text-[13.5px] leading-relaxed whitespace-pre-wrap text-ink-muted">
          {proposal.justification ?? 'Not provided'}
        </p>
      </div>

      <div className="mt-4">
        <SectionLabel>Payload</SectionLabel>
        <pre className="mt-1 max-h-48 overflow-auto rounded-lg border border-white/[0.06] bg-black/30 p-3 font-mono text-[11px] text-ink-muted">
          {JSON.stringify(proposal.payload, null, 2)}
        </pre>
      </div>

      {isPending && (
        <div className="mt-4 border-t border-white/[0.07] pt-4">
          {confirmingReject ? (
            <div>
              <p className="text-[13px] text-ink">
                {`Reject Action: Reject this ${proposal.action_type} on ${proposal.target_system}? It will not be executed. This decision is recorded in the audit trail and cannot be undone.`}
              </p>
              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  disabled={isBusy}
                  onClick={() => {
                    setConfirmingReject(false)
                    onReject(proposal.id)
                  }}
                  className="btn btn-danger"
                >
                  {busy === 'rejecting' ? 'Rejecting...' : 'Confirm Reject'}
                </button>
                <button
                  type="button"
                  disabled={isBusy}
                  onClick={() => setConfirmingReject(false)}
                  className="btn btn-secondary"
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
                className="btn btn-success"
              >
                {busy === 'approving' ? 'Approving...' : 'Approve Action'}
              </button>
              <button
                type="button"
                disabled={isBusy}
                onClick={() => setConfirmingReject(true)}
                className="btn btn-danger"
              >
                {busy === 'rejecting' ? 'Rejecting...' : 'Reject Action'}
              </button>
            </div>
          )}
          {error && <p className="mt-2 text-sm text-red">{error}</p>}
        </div>
      )}
    </div>
  )
}
