import { useEffect, useState } from 'react'
import {
  Layers,
  ShieldAlert,
  ListChecks,
  Fingerprint,
  FileText,
  CalendarClock,
  ClipboardCheck,
  ShieldCheck,
  UserCheck,
  Truck,
  ServerCrash,
} from 'lucide-react'
import ReadinessDial from '../components/ReadinessDial'
import HealthMiniCard from '../components/HealthMiniCard'
import Skeleton from '../components/Skeleton'
import StatTile, { type StatTileTone } from '../components/StatTile'
import Meter from '../components/Meter'
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

  // dataviz skill: Meter is only drawn where a real denominator exists.
  // CARD1_CHECK_NAMES has 3 members, CARD2_CHECK_NAME is 1 -- both totals
  // scale with however many systems actually answered, never a hardcoded
  // constant, so a partial-data run still shows an honest proportion.
  const card1Total = 3 * assuranceFulfilled.length
  const card2Total = 1 * assuranceFulfilled.length
  const actionsTotal = pendingCount + approvedCount + rejectedCount

  // Top-line "at a glance" KPI strip (dataviz skill: a single headline
  // number is a stat tile, not a chart). Tone follows the same status-
  // color discipline as ReadinessDial/HealthMiniCard -- reserved colors,
  // never decorative.
  const openFindingsTone: StatTileTone = failingCards.length === 0 ? 'good' : 'warning'
  const pendingTone: StatTileTone = pendingCount === 0 ? 'neutral' : 'warning'
  const auditTone: StatTileTone =
    chainData?.status === 'VERIFIED' ? 'good' : chainData?.status === 'TAMPERED' ? 'critical' : 'neutral'
  const auditValue =
    chainState === 'fulfilled'
      ? (chainData?.status ?? 'UNKNOWN')
      : chainState === 'rejected'
        ? 'Unavailable'
        : 'Checking…'

  return (
    <div>
      <p className="eyebrow">Overview</p>
      {/* 2026-09-03 whole-app visual pass: gradient headline (index.css's
          .text-gradient) reserved for this ONE hero heading -- the largest
          , boldest text on the page, matching the Vercel/Linear-style
          "confident type" direction. Every other heading on this page and
          across the app stays plain -- overusing the gradient anywhere
          else is exactly the "gaudy, not bold" failure mode to avoid. */}
      <h1 className="text-gradient mt-2 text-[34px] font-extrabold tracking-tight sm:text-[40px]">
        Command Centre
      </h1>
      <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-ink-muted">
        The top-level view of GxP system readiness: a readiness dial and six health mini-cards,
        computed live from real backend state -- never a stale seed value. This is the landing
        page an IT System Manager or QA/Compliance user sees first.
      </p>

      <div className="mt-5 flex items-center gap-2">
        <label htmlFor="command-centre-system" className="text-[13px] font-medium text-ink-muted">
          System
        </label>
        <select
          id="command-centre-system"
          className="input-field"
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
        // 2026-09-03: previously a plain untouched box -- the one branch of
        // this page the bento redesign never reached, so anyone without a
        // reachable backend saw no visual change at all. Same card-hero
        // treatment as the loaded state's readiness panel, so the page
        // reads as "the same product" whether or not data is flowing.
        <div className="card-hero mt-8 flex flex-col items-center gap-3 p-12 text-center">
          <div className="grid h-14 w-14 place-items-center rounded-2xl bg-red-soft text-red">
            <ServerCrash className="h-6 w-6" />
          </div>
          <p className="text-xl font-bold tracking-tight text-ink">{EMPTY_STATE_HEADING}</p>
          <p className="max-w-md text-[13.5px] leading-relaxed text-ink-muted">{EMPTY_STATE_BODY}</p>
        </div>
      ) : (
        <>
          {hasAnyFailure && !bannerDismissed && (
            <div
              data-testid="aggregate-error-banner"
              className="mt-6 flex items-start justify-between gap-4 rounded-xl border border-red-500/30 bg-red-soft p-4 text-sm text-red"
            >
              <p>{AGGREGATE_ERROR_COPY}</p>
              <button
                type="button"
                onClick={() => setBannerDismissed(true)}
                className="text-red hover:opacity-70"
                aria-label="Dismiss"
              >
                ×
              </button>
            </div>
          )}

          {showPartialNote && (
            <p data-testid="partial-data-note" className="mt-4 text-sm text-amber">
              {PARTIAL_DATA_NOTE}
            </p>
          )}

          {/* 2026-09-03 bento redesign: the dial and the four stat tiles
              were two stacked, disconnected blocks -- now one hero panel,
              dial on the left as the visual anchor, stats as a 2x2 grid on
              the right. Reads as a single "here's where you stand" unit
              instead of two separate widgets glued together. */}
          <div
            className="card-hero mt-8 grid grid-cols-1 items-center gap-8 p-8 lg:grid-cols-[auto_1fr]"
            data-tour="readiness-dial"
          >
            <div className="flex justify-center">
              {assuranceLoading && totalChecks === 0 ? (
                <Skeleton className="h-40 w-40 !rounded-full" />
              ) : totalChecks > 0 ? (
                <ReadinessDial passed={passed} total={totalChecks} />
              ) : (
                <p className="max-w-[188px] text-center text-sm text-ink-muted">
                  No readiness data available for the selected system(s).
                </p>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <StatTile icon={Layers} label="Systems in scope" value={systemsInScope.length} delay={0} />
              <StatTile
                icon={ShieldAlert}
                label="Open findings"
                value={assuranceLoading ? '—' : failingCards.length}
                tone={openFindingsTone}
                delay={0.04}
              />
              <StatTile
                icon={ListChecks}
                label="Pending approvals"
                value={actionsState === 'loading' ? '—' : pendingCount}
                tone={pendingTone}
                delay={0.08}
              />
              <StatTile icon={Fingerprint} label="Audit trail" value={auditValue} tone={auditTone} delay={0.12} />
            </div>
          </div>

          <p className="eyebrow mt-10">Health signals</p>
          {/* Bento grid: Documentation & Traceability and Remediation &
              Approvals each carry the most information (a meter plus
              2-3 numbers), so they span two columns -- the varied cell
              sizing is the "bento" part; the other four stay single-width.
              Deliberately not forced into a perfectly even grid (row 3 has
              a gap) -- real bento layouts accept that trade for the
              size-communicates-importance signal, per the agreed
              bold-but-credible direction. */}
          <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <HealthMiniCard
              title="Documentation & Traceability"
              status={card1Status}
              icon={FileText}
              className="lg:col-span-2"
              style={{ transitionDelay: `${cardDelays[0]}ms` }}
            >
              <p className="text-ink">{card1Count} open</p>
              <Meter
                total={card1Total}
                segments={[
                  { value: card1Total - card1Count, className: 'bg-mint', label: 'Passing' },
                  { value: card1Count, className: 'bg-amber', label: 'Open' },
                ]}
              />
            </HealthMiniCard>

            <HealthMiniCard
              title="Periodic Review"
              status={card2Status}
              icon={CalendarClock}
              style={{ transitionDelay: `${cardDelays[1]}ms` }}
            >
              <p className="text-ink">{card2Count} open</p>
              <Meter
                total={card2Total}
                segments={[
                  { value: card2Total - card2Count, className: 'bg-mint', label: 'Passing' },
                  { value: card2Count, className: 'bg-amber', label: 'Open' },
                ]}
              />
            </HealthMiniCard>

            <HealthMiniCard
              title="Remediation & Approvals"
              status={card3Status}
              icon={ClipboardCheck}
              className="lg:col-span-2"
              style={{ transitionDelay: `${cardDelays[2]}ms` }}
            >
              <p className="text-ink">{pendingCount} pending</p>
              <p className="mt-1 text-ink-muted">{approvedCount} approved</p>
              <p className="mt-1 text-ink-muted">{rejectedCount} rejected</p>
              <Meter
                total={actionsTotal}
                segments={[
                  { value: pendingCount, className: 'bg-amber', label: 'Pending' },
                  { value: approvedCount, className: 'bg-mint', label: 'Approved' },
                  { value: rejectedCount, className: 'bg-red', label: 'Rejected' },
                ]}
              />
            </HealthMiniCard>

            <div data-tour="mini-card-audit-integrity">
              <HealthMiniCard
                title="Audit Trail Integrity"
                status={card4Status}
                icon={ShieldCheck}
                style={{ transitionDelay: `${cardDelays[3]}ms` }}
              >
                <p className={chainData?.status === 'TAMPERED' ? 'text-red' : 'text-mint'}>
                  {chainData?.status ?? 'UNKNOWN'}
                </p>
              </HealthMiniCard>
            </div>

            <HealthMiniCard
              title="Access Reviews"
              status={card5Status}
              icon={UserCheck}
              style={{ transitionDelay: `${cardDelays[4]}ms` }}
            >
              <p className="text-ink">{overdueAccessReviews} overdue</p>
            </HealthMiniCard>

            <HealthMiniCard
              title="Supplier Qualification"
              status={card6Status}
              icon={Truck}
              style={{ transitionDelay: `${cardDelays[5]}ms` }}
            >
              <p className="text-ink">{overdueSuppliers} overdue</p>
              {overdueSupplierNames.length > 0 && (
                <ul className="mt-1 text-ink-muted">
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
