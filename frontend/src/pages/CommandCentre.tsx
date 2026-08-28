import { useEffect, useState } from 'react'
import ReadinessDial from '../components/ReadinessDial'
import HealthMiniCard from '../components/HealthMiniCard'
import {
  fetchAssuranceCards,
  fetchSystemSignals,
  fetchActionProposals,
  fetchChainVerification,
  type AssuranceCardsResponse,
  type SystemSignalsResponse,
  type ActionProposalsResponse,
  type ChainVerificationResponse,
} from '../lib/api'

// Phase 6 (06-02, Task 2, D-06/D-07): the two seeded systems this
// dashboard aggregates across by default. Never read `gxp_systems.
// readiness_score` (06-RESEARCH.md Pitfall 1: a static seed literal, 61/94,
// never recomputed) -- every number on this page is computed client-side
// from the four live backend surfaces below.
const SYSTEM_IDS = ['GXP-MFG-DEMO-01', 'BUS-IT-DEMO-02'] as const
type SystemId = (typeof SYSTEM_IDS)[number]
type Scope = 'ALL' | SystemId

const SYSTEM_OPTIONS: Array<{ value: Scope; label: string }> = [
  { value: 'ALL', label: 'All Systems' },
  { value: 'GXP-MFG-DEMO-01', label: 'GXP-MFG-DEMO-01' },
  { value: 'BUS-IT-DEMO-02', label: 'BUS-IT-DEMO-02' },
]

// 06-UI-SPEC.md Interaction Notes, D-07 mapping table: verify_urs_approved
// and verify_no_stale_documents both cite ANNEX11-S4-DOC-001 (same rule
// family) and group into mini-card #1 alongside verify_test_traceability;
// verify_periodic_eval_current alone is mini-card #2.
const CARD1_CHECK_NAMES = new Set([
  'verify_urs_approved',
  'verify_no_stale_documents',
  'verify_test_traceability',
])
const CARD2_CHECK_NAME = 'verify_periodic_eval_current'

type CallStatus = 'loading' | 'fulfilled' | 'rejected'

interface SystemEntry {
  assurance: CallStatus
  assuranceData: AssuranceCardsResponse | null
  signals: CallStatus
  signalsData: SystemSignalsResponse | null
}

function initialSystemEntry(): SystemEntry {
  return { assurance: 'loading', assuranceData: null, signals: 'loading', signalsData: null }
}

function initialSystemStates(ids: readonly string[]): Record<string, SystemEntry> {
  return Object.fromEntries(ids.map((id) => [id, initialSystemEntry()]))
}

function statusFor(loading: boolean, allRejected: boolean): 'loading' | 'ready' | 'error' {
  if (loading) return 'loading'
  if (allRejected) return 'error'
  return 'ready'
}

export const EMPTY_STATE_HEADING = 'No system data available'
export const EMPTY_STATE_BODY =
  "Couldn't compute readiness for any registered system — check that the backend is running and reachable."
export const AGGREGATE_ERROR_COPY =
  "Couldn't load one or more health signals — showing partial data where available. Refresh to retry."
export const PARTIAL_DATA_NOTE =
  'Partial data: one or more systems did not respond — the values above reflect only the systems that did.'

export default function CommandCentre() {
  const [scope, setScope] = useState<Scope>('ALL')
  const systemsInScope: string[] = scope === 'ALL' ? [...SYSTEM_IDS] : [scope]

  const [systemStates, setSystemStates] = useState<Record<string, SystemEntry>>(() =>
    initialSystemStates(SYSTEM_IDS),
  )
  const [actionsState, setActionsState] = useState<CallStatus>('loading')
  const [actionsData, setActionsData] = useState<ActionProposalsResponse | null>(null)
  const [chainState, setChainState] = useState<CallStatus>('loading')
  const [chainData, setChainData] = useState<ChainVerificationResponse | null>(null)
  const [bannerDismissed, setBannerDismissed] = useState(false)

  // Cancelled-guard fetch effect (mirrors pages/Actions.tsx / BlastRadius.tsx):
  // re-runs whenever the system selector changes. Promise.allSettled, not
  // Promise.all -- a system whose calls fail contributes 0 to every count
  // it would have fed rather than failing the whole page.
  useEffect(() => {
    let cancelled = false
    setSystemStates(initialSystemStates(systemsInScope))
    setActionsState('loading')
    setActionsData(null)
    setChainState('loading')
    setChainData(null)
    setBannerDismissed(false)

    systemsInScope.forEach((id) => {
      Promise.allSettled([fetchAssuranceCards(id), fetchSystemSignals(id)]).then(
        ([assuranceResult, signalsResult]) => {
          if (cancelled) return
          setSystemStates((prev) => ({
            ...prev,
            [id]: {
              assurance: assuranceResult.status === 'fulfilled' ? 'fulfilled' : 'rejected',
              assuranceData: assuranceResult.status === 'fulfilled' ? assuranceResult.value : null,
              signals: signalsResult.status === 'fulfilled' ? 'fulfilled' : 'rejected',
              signalsData: signalsResult.status === 'fulfilled' ? signalsResult.value : null,
            },
          }))
        },
      )
    })

    fetchActionProposals()
      .then((response) => {
        if (cancelled) return
        setActionsState('fulfilled')
        setActionsData(response)
      })
      .catch(() => {
        if (cancelled) return
        setActionsState('rejected')
      })

    fetchChainVerification()
      .then((response) => {
        if (cancelled) return
        setChainState('fulfilled')
        setChainData(response)
      })
      .catch(() => {
        if (cancelled) return
        setChainState('rejected')
      })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope])

  const systemEntries = systemsInScope.map((id) => systemStates[id] ?? initialSystemEntry())

  const assuranceLoading = systemEntries.some((e) => e.assurance === 'loading')
  const assuranceFulfilled = systemEntries.filter((e) => e.assurance === 'fulfilled')
  const assuranceSettledCount = systemEntries.filter((e) => e.assurance !== 'loading').length
  const assuranceAllRejected =
    systemEntries.length > 0 && systemEntries.every((e) => e.assurance === 'rejected')

  const signalsLoading = systemEntries.some((e) => e.signals === 'loading')
  const signalsFulfilled = systemEntries.filter((e) => e.signals === 'fulfilled')
  const signalsAllRejected =
    systemEntries.length > 0 && systemEntries.every((e) => e.signals === 'rejected')

  // "Every call across every system in scope" (plan Task 2 <action>) --
  // assurance + signals calls for every system in scope, all settled and
  // all rejected. Only this combination triggers the full-page empty
  // state; any lesser failure degrades to per-card error / a partial note
  // + dismissible banner instead.
  const allSystemCallsSettled = !assuranceLoading && !signalsLoading
  const everyCallFailed = allSystemCallsSettled && assuranceAllRejected && signalsAllRejected

  const totalChecks = 4 * assuranceFulfilled.length
  const failingCards = assuranceFulfilled.flatMap((e) => e.assuranceData?.cards ?? [])
  const passed = totalChecks - failingCards.length

  const card1Count = failingCards.filter((c) =>
    CARD1_CHECK_NAMES.has(c.deterministic_check.check_name),
  ).length
  const card2Count = failingCards.filter(
    (c) => c.deterministic_check.check_name === CARD2_CHECK_NAME,
  ).length

  const scopedProposals = (actionsData?.proposals ?? []).filter(
    (p) => scope === 'ALL' || p.target_system === scope,
  )
  const pendingCount = scopedProposals.filter((p) => p.status === 'PENDING_APPROVAL').length
  const approvedCount = scopedProposals.filter(
    (p) => p.status === 'APPROVED' || p.status === 'EXECUTED',
  ).length
  const rejectedCount = scopedProposals.filter((p) => p.status === 'REJECTED').length

  const overdueAccessReviews = signalsFulfilled.reduce(
    (sum, e) => sum + (e.signalsData?.overdue_access_reviews ?? 0),
    0,
  )
  const overdueSuppliers = signalsFulfilled.reduce(
    (sum, e) => sum + (e.signalsData?.overdue_suppliers ?? 0),
    0,
  )
  const overdueSupplierNames = Array.from(
    new Set(signalsFulfilled.flatMap((e) => e.signalsData?.overdue_supplier_names ?? [])),
  )

  const showPartialNote =
    scope === 'ALL' &&
    !everyCallFailed &&
    ((allSystemCallsSettled &&
      assuranceSettledCount === systemsInScope.length &&
      assuranceFulfilled.length > 0 &&
      assuranceFulfilled.length < systemsInScope.length) ||
      (!signalsLoading &&
        signalsFulfilled.length > 0 &&
        signalsFulfilled.length < systemsInScope.length))

  const hasAnyFailure =
    assuranceFulfilled.length < systemEntries.filter((e) => e.assurance !== 'loading').length ||
    signalsFulfilled.length < systemEntries.filter((e) => e.signals !== 'loading').length ||
    actionsState === 'rejected' ||
    chainState === 'rejected'

  const card1Status = statusFor(assuranceLoading, assuranceAllRejected)
  const card2Status = statusFor(assuranceLoading, assuranceAllRejected)
  const card3Status = statusFor(actionsState === 'loading', actionsState === 'rejected')
  const card4Status = statusFor(chainState === 'loading', chainState === 'rejected')
  const card5Status = statusFor(signalsLoading, signalsAllRejected)
  const card6Status = statusFor(signalsLoading, signalsAllRejected)

  const cardDelays = [0, 40, 80, 120, 160, 200]

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-100">Command Centre</h1>
      <p className="mt-2 max-w-2xl text-slate-400">
        The top-level view of GxP system readiness: a readiness dial and six health mini-cards,
        computed live from real backend state -- never a stale seed value. This is the landing
        page an IT System Manager or QA/Compliance user sees first.
      </p>

      <div className="mt-4">
        <label htmlFor="command-centre-system" className="text-sm text-slate-400">
          System
        </label>
        <select
          id="command-centre-system"
          className="ml-2 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm text-slate-100"
          value={scope}
          onChange={(e) => setScope(e.target.value as Scope)}
        >
          {SYSTEM_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {everyCallFailed ? (
        <div className="mt-8">
          <p className="text-lg font-semibold text-slate-100">{EMPTY_STATE_HEADING}</p>
          <p className="mt-1 text-slate-400">{EMPTY_STATE_BODY}</p>
        </div>
      ) : (
        <>
          {hasAnyFailure && !bannerDismissed && (
            <div
              data-testid="aggregate-error-banner"
              className="mt-6 flex items-start justify-between gap-4 rounded border border-red-700 bg-red-950/40 p-3 text-sm text-red-300"
            >
              <p>{AGGREGATE_ERROR_COPY}</p>
              <button
                type="button"
                onClick={() => setBannerDismissed(true)}
                className="text-red-300 hover:text-red-100"
                aria-label="Dismiss"
              >
                ×
              </button>
            </div>
          )}

          {showPartialNote && (
            <p data-testid="partial-data-note" className="mt-4 text-sm text-amber-400">
              {PARTIAL_DATA_NOTE}
            </p>
          )}

          <div className="mt-8 flex justify-center">
            {assuranceLoading && totalChecks === 0 ? (
              <p className="text-slate-400">Loading readiness…</p>
            ) : totalChecks > 0 ? (
              <ReadinessDial passed={passed} total={totalChecks} />
            ) : (
              <p className="text-slate-400">
                No readiness data available for the selected system(s).
              </p>
            )}
          </div>

          <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <HealthMiniCard
              title="Documentation & Traceability"
              status={card1Status}
              style={{ transitionDelay: `${cardDelays[0]}ms` }}
            >
              <p className="text-slate-100">{card1Count} open</p>
            </HealthMiniCard>

            <HealthMiniCard
              title="Periodic Review"
              status={card2Status}
              style={{ transitionDelay: `${cardDelays[1]}ms` }}
            >
              <p className="text-slate-100">{card2Count} open</p>
            </HealthMiniCard>

            <HealthMiniCard
              title="Remediation & Approvals"
              status={card3Status}
              style={{ transitionDelay: `${cardDelays[2]}ms` }}
            >
              <p className="text-slate-100">{pendingCount} pending</p>
              <p className="mt-1 text-slate-400">{approvedCount} approved</p>
              <p className="mt-1 text-slate-400">{rejectedCount} rejected</p>
            </HealthMiniCard>

            <HealthMiniCard
              title="Audit Trail Integrity"
              status={card4Status}
              style={{ transitionDelay: `${cardDelays[3]}ms` }}
            >
              <p
                className={
                  chainData?.status === 'TAMPERED' ? 'text-red-400' : 'text-emerald-400'
                }
              >
                {chainData?.status ?? 'UNKNOWN'}
              </p>
            </HealthMiniCard>

            <HealthMiniCard
              title="Access Reviews"
              status={card5Status}
              style={{ transitionDelay: `${cardDelays[4]}ms` }}
            >
              <p className="text-slate-100">{overdueAccessReviews} overdue</p>
            </HealthMiniCard>

            <HealthMiniCard
              title="Supplier Qualification"
              status={card6Status}
              style={{ transitionDelay: `${cardDelays[5]}ms` }}
            >
              <p className="text-slate-100">{overdueSuppliers} overdue</p>
              {overdueSupplierNames.length > 0 && (
                <ul className="mt-1 text-slate-400">
                  {overdueSupplierNames.map((name) => (
                    <li key={name}>{name}</li>
                  ))}
                </ul>
              )}
            </HealthMiniCard>
          </div>
        </>
      )}
    </div>
  )
}
