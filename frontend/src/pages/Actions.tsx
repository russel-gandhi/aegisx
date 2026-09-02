import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import ActionProposalCard from '../components/ActionProposalCard'
import Skeleton from '../components/Skeleton'
import { motionTokens } from '../lib/motion'
import { useIdentity } from '../lib/identity'
import {
  ApiError,
  approveAction,
  fetchActionProposals,
  rejectAction,
  type ActionProposalData,
} from '../lib/api'
import { connectCopilotStream, type CopilotStreamHandle } from '../lib/ws'

type LoadState = 'loading' | 'error' | 'ready'
type ConnectionStatus = 'connecting' | 'connected' | 'degraded'

interface DecisionState {
  busy: 'approving' | 'rejecting' | null
  error: string | null
}

// Stable across the component's lifetime -- the socket is opened once on
// mount and closed on unmount, matching the plan's "stable session id"
// requirement. The stream is session-agnostic server-side (every
// connected client receives every proposal frame, see
// backend/app/ws/copilot.py's own docstring), so this value only needs to
// be constant, not unique per tab.
const SESSION_ID = 'action-approval-centre'

const PERMISSION_DENIED_MESSAGE =
  "You don't have permission to approve this action — only IT System Manager can approve GxP-relevant writes."
const DECISION_FAILURE_MESSAGE = "Couldn't record your decision — try again."

function sortOldestFirst(proposals: ActionProposalData[]): ActionProposalData[] {
  return [...proposals].sort((a, b) => {
    if (a.created_at && b.created_at) {
      return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    }
    if (a.created_at && !b.created_at) return -1
    if (!a.created_at && b.created_at) return 1
    return a.id < b.id ? -1 : a.id > b.id ? 1 : 0
  })
}

export default function Actions() {
  const identity = useIdentity()
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [proposals, setProposals] = useState<ActionProposalData[]>([])
  const [retryToken, setRetryToken] = useState(0)
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting')
  const [decisions, setDecisions] = useState<Record<string, DecisionState>>({})

  // Cancelled-guard fetch (mirrors pages/FindingInvestigation.tsx): also
  // re-runs when the operator switches role via RoleSelector, so the
  // queue and decision controls reflect the currently-selected identity.
  // `loadState` is reset to 'loading' by the Retry button's own click
  // handler (an event, not this effect) -- calling `setLoadState`
  // synchronously inside the effect body itself would start a second,
  // avoidable render for every commit of this effect.
  useEffect(() => {
    let cancelled = false
    fetchActionProposals()
      .then((response) => {
        if (cancelled) return
        setProposals(sortOldestFirst(response.proposals))
        setLoadState('ready')
      })
      .catch(() => {
        if (cancelled) return
        setLoadState('error')
      })
    return () => {
      cancelled = true
    }
  }, [identity, retryToken])

  // Opened once on mount, closed on unmount -- not re-opened on identity
  // change, since the socket carries no identity of its own (D-04's
  // scope boundary: C2 gates HTTP write routes, not this WebSocket).
  useEffect(() => {
    let handle: CopilotStreamHandle | null = null
    handle = connectCopilotStream(SESSION_ID, {
      onFrame: (frame) => {
        setConnectionStatus((prev) => (prev === 'degraded' ? prev : 'connected'))
        if (frame.event !== 'action_proposal_created') return
        setProposals((prev) => {
          if (prev.some((p) => p.id === frame.proposal.id)) return prev
          return sortOldestFirst([...prev, frame.proposal])
        })
      },
      onError: () => setConnectionStatus('degraded'),
      onClose: () => setConnectionStatus('degraded'),
    })
    return () => {
      handle?.close()
    }
  }, [])

  function updateDecision(id: string, patch: Partial<DecisionState>) {
    setDecisions((prev) => {
      const existing: DecisionState = prev[id] ?? { busy: null, error: null }
      return { ...prev, [id]: { ...existing, ...patch } }
    })
  }

  function handleDecisionError(id: string, error: unknown) {
    if (error instanceof ApiError && error.status === 403) {
      updateDecision(id, { busy: null, error: PERMISSION_DENIED_MESSAGE })
      return
    }
    updateDecision(id, { busy: null, error: DECISION_FAILURE_MESSAGE })
  }

  function handleApprove(id: string) {
    updateDecision(id, { busy: 'approving', error: null })
    approveAction(id)
      .then((updated) => {
        // Replace in place with the server's returned record only after
        // the response arrives -- never an optimistic status flip.
        setProposals((prev) => prev.map((p) => (p.id === id ? updated : p)))
        updateDecision(id, { busy: null, error: null })
      })
      .catch((error: unknown) => handleDecisionError(id, error))
  }

  function handleReject(id: string) {
    updateDecision(id, { busy: 'rejecting', error: null })
    rejectAction(id)
      .then((updated) => {
        setProposals((prev) => prev.map((p) => (p.id === id ? updated : p)))
        updateDecision(id, { busy: null, error: null })
      })
      .catch((error: unknown) => handleDecisionError(id, error))
  }

  return (
    <div>
      <p className="eyebrow">Approval centre</p>
      <h1 className="mt-1 text-[28px] font-bold text-ink">Action / Approval Centre</h1>
      <p className="mt-2 max-w-2xl text-[13.5px] text-ink-muted">
        Every GxP-relevant write proposed by A7 Remediation sits here PENDING until a human
        approves it. Approval dialogs render exclusively from server-trusted proposal metadata,
        never from LLM-generated markup.
      </p>

      <div className="mt-4 flex items-center gap-2 text-sm">
        {connectionStatus === 'connecting' && <span className="text-ink-faint">Connecting…</span>}
        {connectionStatus === 'connected' && (
          <>
            <span
              data-testid="ws-connected-dot"
              aria-hidden="true"
              className="h-2 w-2 rounded-full bg-mint shadow-[0_0_8px_rgba(47,216,137,0.7)]"
            />
            <span className="text-ink-muted">Live</span>
          </>
        )}
        {connectionStatus === 'degraded' && (
          <span className="text-amber">
            Live updates unavailable — refresh to see new actions.
          </span>
        )}
      </div>

      <h2 className="mt-6 text-[15px] font-semibold text-ink">{`Pending Actions (${proposals.length})`}</h2>

      <div className="mt-3 max-h-[36rem] space-y-4 overflow-auto">
        {loadState === 'loading' && (
          <div className="space-y-4">
            <p className="text-ink-muted">Loading pending actions...</p>
            <Skeleton className="h-32 w-full rounded-xl" />
            <Skeleton className="h-32 w-full rounded-xl" />
          </div>
        )}

        {loadState === 'error' && (
          <div>
            <p className="text-red">
              Couldn&apos;t load pending actions — check your connection and retry.
            </p>
            <button
              type="button"
              onClick={() => {
                setLoadState('loading')
                setRetryToken((t) => t + 1)
              }}
              className="btn btn-secondary mt-2"
            >
              Retry
            </button>
          </div>
        )}

        {loadState === 'ready' && proposals.length === 0 && (
          <div>
            <p className="text-lg font-semibold text-ink">No pending actions</p>
            <p className="mt-1 text-ink-muted">
              All caught up — proposed actions will appear here as A7 generates them, and this
              list updates live.
            </p>
          </div>
        )}

        {loadState === 'ready' && (
          <AnimatePresence mode="popLayout" initial={false}>
            {proposals.map((proposal) => (
              <motion.div
                key={proposal.id}
                layout
                initial={{ opacity: 0, y: motionTokens.distance.md }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: motionTokens.duration.normal, ease: motionTokens.easing.smooth }}
              >
                <ActionProposalCard
                  proposal={proposal}
                  onApprove={handleApprove}
                  onReject={handleReject}
                  busy={decisions[proposal.id]?.busy ?? null}
                  error={decisions[proposal.id]?.error ?? null}
                />
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>
    </div>
  )
}
