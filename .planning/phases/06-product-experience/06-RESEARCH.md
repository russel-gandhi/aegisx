# Phase 6: Product Experience - Research

**Researched:** 2026-08-27
**Domain:** React/TypeScript frontend product experience (dashboard aggregation, SSE-driven chat, live topology visualization, cross-page guided tour) over an already-real FastAPI/Postgres/OPA backend
**Confidence:** HIGH (backend integration surface and existing code patterns — all read this session); MEDIUM (new frontend library choices — verified on registry, not yet integrated in this repo)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Copilot query path**
- **D-01:** The Copilot chat's hero query reuses the existing `GET /api/systems/{id}/assurance-cards/stream` SSE endpoint (Phase 4, `routes/findings.py`) rather than invoking the compiled LangGraph (`app/graph/state.py`). That endpoint already calls A2 + C1 directly and streams `AssuranceCard`s in completion order — deliberately bypassing the 5-way A1–A6 fan-out, which has no real work to do since only A2 Compliance is real in v1. No backend changes to the query path itself. — Reversibility: reversible.
- **D-02:** The live agent topology visualization (`AgentTopologyCanvas`) does NOT reflect literal per-node backend state. Node Waiting → Running → Complete transitions are synthesized client-side, timed off real SSE event arrival from D-01's stream (not fabricated delays) — e.g. A0/A2 transition to Running when the stream opens, C1 transitions per-card as each `AssuranceCard` arrives, A7/C3 stay Waiting (out of scope for a read-only query). A1 and A3–A6 stay permanently Waiting/dimmed since they don't run for this query type in v1.
- **D-03:** A small, visible note near the topology canvas states "A1, A3–A6 not yet implemented (v2)" — required so the visualization never implies more agent breadth is real than v1 actually built.

**Chat input**
- **D-04:** The Copilot page has a real free-text input (reads as an actual chat), but only the hero-query shape (a system-readiness question against a known/seeded system id) is actually wired to the assurance-cards flow. Any other input receives a clear, honest "not supported yet" response rather than a fabricated or misleading answer.
- **D-05:** `AssuranceCard`s stream into the assistant's chat bubble one-by-one, in arrival order, directly reusing the existing SSE completion-order behavior — no batching/waiting for all 4 checks before rendering.

**Command Centre dashboard content**
- **D-06:** The readiness dial and 6 health mini-cards aggregate across both seeded systems (`GXP-MFG-DEMO-01`, `BUS-IT-DEMO-02`) by default, computed from real backend data (assurance-cards pass/fail ratio for the dial). A system selector lets the user narrow the view to one system. — Reversibility: reversible.
- **D-07:** The 6 mini-cards cover four real signal themes (exact split across 6 cards is Claude's discretion): (1) Compliance findings — open/resolved from A2 checks via assurance-cards; (2) Remediation & approvals — pending/approved/rejected counts from Phase 5's `action_proposals`; (3) Audit trail integrity — `verify_chain()` healthy/tampered signal; (4) Access & supplier signals — overdue supplier/access review data already present in Phase 1 seed data, even though the real A6 Access agent itself is v2.

**Guided Tour mechanics**
- **D-08:** The 8-step Guided Tour (Bible §14.4) is an interactive overlay that drives the user through REAL pages performing REAL actions and REAL backend calls — navigate to Command Centre, ask the hero query on the Copilot page, watch topology + streaming cards, approve a proposal on the Actions.tsx Approval Centre, check the audit trail — not a scripted/static walkthrough. — Reversibility: costly.
- **D-09:** The tour must handle repeat runs without breaking: if a step's target state is already satisfied (e.g. the demo proposal is already approved from a prior run), the tour either seeds a fresh action-proposal for that step or detects completion and skips forward gracefully with a note — it never fails or gets stuck reperforming an already-done irreversible action. A full one-command demo reset (HARD-05) remains out of scope/deferred.

### Claude's Discretion
- Exact split of the 4 mini-card themes (D-07) across the required 6 cards.
- Exact wire-level shape of the "not supported yet" response for non-hero-query chat input (D-04) — client-side guard vs. a real (small, honest) backend response.
- Exact mechanism for the "already completed" detection in D-09 (e.g. checking `action_proposals` status before starting the approval step vs. tour-local state).
- Where the system selector (D-06) lives in the UI (dashboard-level control vs. per-card).

### Deferred Ideas (OUT OF SCOPE)
- Real per-agent backend WS state events (a true `agent_state` frame type reflecting actual A0–A6 execution) — deferred until the compiled LangGraph's full fan-out is actually invoked for a query (v2, once A1/A3–A6 become real agents per AGT-01..05).
- Full one-command demo reset (HARD-05) — Guided Tour gets narrow, tour-scoped defensive handling (D-09) only.
- Live auto-refresh for `/blast-radius` and `/findings` pages — not picked up in Phase 6 discussion; remains a candidate but left for planner/user to decide.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-03 | Command Centre dashboard shows a readiness dial and health mini-cards | Backend integration surface mapped below (Architecture Patterns → "Command Centre data sourcing"); confirms only ONE new backend endpoint is required (supplier/access overdue signals), everything else composes from existing `/assurance-cards`, `/api/actions`, `/api/audit/verify` |
| UI-04 | Ask GxP Copilot page provides chat + live agent topology visualization | Backend integration surface confirms D-01's SSE reuse requires zero backend changes; `AgentTopologyCanvas` extension point identified (component docstring anticipates this exact change); `detect_injection` reuse identified for a real, honest D-04 "not supported" response |

</phase_requirements>

## Summary

Phase 6 is almost entirely a frontend-composition phase: every backend capability the Command Centre, Copilot chat, and Guided Tour need already exists and was verified this session by reading the actual route/agent modules — `GET /api/systems/{id}/assurance-cards` and its `/stream` SSE sibling (`backend/app/routes/findings.py`), `GET /api/actions` + `POST /approve`/`/reject` + `POST /generate-capa` (`backend/app/routes/actions.py`), and `GET /api/audit/verify` (`backend/app/routes/audit.py`). The one genuine backend gap is D-07's fourth mini-card theme (access/supplier overdue signals): no existing HTTP route reads the `suppliers` or `access_reviews` tables — that data is only ever queried by `_check_a6` inside `backend/app/agents/minimal_specialists.py`, which is wired into the LangGraph node path, not any REST route. A small new read endpoint (mirroring `_check_a6`'s query shape plus a new suppliers overdue query) is the one net-new backend surface this phase needs.

The frontend has no chart library, no tour library, no animation library, and no component library (verified: `frontend/package.json` — only `@xyflow/react`, `react`, `react-dom`, `react-router-dom` as runtime deps) — every page through Phase 5 is hand-rolled Tailwind, and `05-UI-SPEC.md` records this as an explicit, established precedent ("none — hand-built Tailwind v4 utility classes, no component library"). This phase should keep the readiness dial hand-rolled (simple SVG arc, no new dependency) but should NOT hand-roll the Guided Tour's spotlight/tooltip positioning engine — cross-viewport element highlighting with scroll-into-view and resize handling is a genuinely deceptive-complexity problem, and `react-joyride` (verified OK on the registry, React 16.8–19 peer range, actively maintained) is the standard tool for it. This creates a real tension with the project's own zero-library UI precedent and with the repo's separate "UI Animation Guidelines" doc (which names React Bits/Framer Motion for exactly this use case) — flagged explicitly below for the UI-SPEC/planning step to resolve, not silently decided here.

Three source-verified findings materially change what the planner should build: (1) `gxp_systems.readiness_score` is a **stale, static seed column** (61/94, never recomputed by any code touched since Phase 2) — the dial must NOT read it; (2) `POST .../generate-capa` has **no idempotency guard** — calling it twice for the same `finding_id` creates two separate `action_proposals` rows, which is exactly the trap D-09 anticipates and must be defended against by checking `/api/actions` first; (3) `detect_injection()` (`backend/app/agents/c2_gateway.py`) is a **already-built, already-tested, zero-LLM pure function** with no HTTP caller today — wiring the Copilot's D-04 "not supported yet" path through it turns Guided Tour Step 6 ("AI Safety") into a real, deterministic demonstration instead of a page with nothing to show.

**Primary recommendation:** Build the Command Centre and Copilot chat as pure composition over the four existing read/write routes plus one new supplier/access-signals read endpoint; extend `AgentTopologyCanvas` with a `nodeStatus` prop (colours only, per its own docstring) driven by SSE event timing; wire the Copilot's non-hero-query path through `detect_injection()` for an honest, real C2 demonstration; and build the Guided Tour as a thin state-machine (route navigation + `/api/actions` completion checks) wrapped around `react-joyride`'s highlight/tooltip mechanics rather than hand-rolling either half.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Readiness dial computation | Browser / Client | API / Backend (data source) | Pure aggregation arithmetic over already-fetched `AssuranceCardsResponse` data from two systems — no new deterministic decision is made, so it stays client-side per D-06's own "additive UI/query concern" framing |
| Health mini-card #1–3 (compliance, remediation, audit integrity) | Browser / Client | API / Backend (data source) | Same reasoning — reads three existing endpoints and counts/labels client-side; no new backend logic |
| Health mini-card #4 (access/supplier signals) | API / Backend | Database / Storage | Requires a genuinely new deterministic query against `suppliers`/`access_reviews` (no existing route exposes them) — this is a backend concern, not client aggregation, to keep the "overdue" threshold logic in one place (mirrors `_check_a6`'s and Rego rule `ANNEX11-S3-SUP-001`'s existing pattern) |
| Copilot hero-query response | API / Backend (SSE) | Browser / Client (render) | Already-built C1-verified data; frontend is a pure renderer per EVID-03's existing contract |
| Copilot non-hero-query handling (D-04) | API / Backend (if wired to `detect_injection`) OR Browser / Client (if client-side guard) | — | Claude's Discretion per CONTEXT.md; research recommends backend (see Don't Hand-Roll) so C2's real deterministic check gets exercised, not a fabricated client string |
| Live agent topology node coloring | Browser / Client | — | D-02 is explicit: synthesized client-side off real SSE timing, never a new backend WS event this phase |
| Guided Tour step sequencing / "already done" detection | Browser / Client | API / Backend (state read) | Tour logic (which step, which route, whether to skip) is a client state machine; it reads real backend state (`/api/actions`) to make skip decisions, but the decision logic itself is UI orchestration, not a new deterministic backend rule |
| RBAC / injection detection (safety decisions) | API / Backend | — | Bible §1.3 — permanent constraint, already implemented (`c2_gateway.py`), unaffected by this phase; this phase's only obligation is to not bypass it when it decides to add a real backend response path |

## Standard Stack

### Core
No new **runtime** dependency is strictly required for UI-03/UI-04's minimum contract — the readiness dial, mini-cards, and chat rendering can all be built on the existing `react` + `react-router-dom` + Tailwind stack already in `frontend/package.json` `[VERIFIED: frontend/package.json:12-16]` ("react": "^19.2.8", "react-dom": "^19.2.8", "react-router-dom": "^7.18.2", "@xyflow/react": "^12.11.3"). The Guided Tour (SENT-5-08, P0) is the one place a new dependency is recommended.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react-joyride | 3.2.0 | Guided Tour spotlight/tooltip highlighting engine | `[VERIFIED: npm registry via package-legitimacy check]` verdict OK, `publishedAt` 2026-07-09, 1,380,658 weekly downloads, repo `github.com/gilbarbara/react-joyride`, `peerDependencies: {"react": "16.8 - 19", "react-dom": "16.8 - 19"}` — the only major React-native tour library with confirmed React 19 support; avoids hand-rolling viewport-aware element highlighting, scroll-into-view, and resize-driven repositioning, which is a deceptive-complexity UI problem (see Don't Hand-Roll) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (none required) | — | — | Readiness dial: hand-rolled SVG arc is the recommended default (see Alternatives below) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled SVG readiness dial | `recharts` (v3.10.1, `[VERIFIED: npm registry]` OK verdict, react peer `^16.8‖^17‖^18‖^19`, 59M weekly downloads) | recharts is safe and well-maintained, but pulls in a full charting library for one radial-progress element; a hand-rolled `<svg><circle>` arc (stroke-dasharray trick) is ~30 lines, matches the zero-chart-library precedent through Phases 2-5, and needs no new dependency. Recommend recharts only if the hand-rolled arc proves visually inadequate during UI-SPEC. |
| react-joyride | `driver.js` (v1.8.0, `[VERIFIED: npm registry]` OK verdict, framework-agnostic, no React peer dep, 1,980,481 weekly downloads) | driver.js is framework-agnostic (works via imperative DOM calls) and slightly more actively downloaded, but has no first-class React integration — every step transition would need manual `useEffect` wiring against its imperative API. react-joyride's React-native `<Joyride>` component with a controlled `stepIndex`/`run` prop maps more directly onto React Router's `useNavigate`-driven, cross-page step advancement this tour needs. |
| React Bits components for tour/dashboard polish | Hand-built Tailwind (existing precedent) | **Flagged tension, not resolved here.** The repo's own `UI Animation Guidelines and React Bits MCP Integration.md` names "Guided tour interactions" as priority-#1 for React Bits/Framer Motion use. But `05-UI-SPEC.md` (Phase 5) explicitly records "no component library... no shadcn... established across Phases 2-4" as this project's convention `[VERIFIED: .planning/phases/05-safety-remediation/05-UI-SPEC.md:23-26,157-161]`. React Bits components are obtained via the shadcn CLI (`npx shadcn@latest mcp init`) and are built on Framer Motion `[CITED: WebSearch — React Bits is "built using frameworks like Framer Motion and Tailwind"]`, so adopting them means both initializing shadcn (a precedent break) and adding `framer-motion` as a runtime dependency. `framer-motion` was flagged `[SUS: too-new]` by the package-legitimacy check (see audit below) — almost certainly a false positive against the actively-maintained `motion`/`framer-motion` project (44.9M weekly downloads), but still requires a `checkpoint:human-verify` per protocol if adopted. **Recommendation:** stay with hand-built Tailwind for dashboard/tour polish (subtle CSS transitions only) unless the user explicitly opts into breaking the no-component-library precedent during UI-SPEC. |

**Installation (only if react-joyride is adopted):**
```bash
npm install react-joyride
```

**Version verification:** `npm view react-joyride version` → `3.2.0` (checked this session, 2026-08-27); `npm view react-joyride peerDependencies` → confirms React 19 support. `npm view driver.js version` → `1.8.0`. `npm view recharts version` → `3.10.1`. `npm view framer-motion version` → latest publish 2026-08-20 (flagged SUS by legitimacy heuristic on "too-new" publish signal despite being an established, high-download package — verify manually before use, do not treat the SUS flag as disqualifying but do not skip the checkpoint either).

## Package Legitimacy Audit

| Package | Registry | Age signal | Downloads/wk | Source Repo | Verdict | Disposition |
|---------|----------|-----------|--------------|-------------|---------|-------------|
| react-joyride | npm | last publish 2026-07-09 | 1,380,658 | github.com/gilbarbara/react-joyride | OK | Approved |
| driver.js | npm | last publish 2026-07-17 | 1,980,481 | github.com/nilbuild/driver.js | OK | Approved (alternative, not primary pick) |
| recharts | npm | last publish 2026-07-25 | 59,007,412 | github.com/recharts/recharts | OK | Approved (alternative, not primary pick) |
| framer-motion | npm | last publish 2026-08-20 | 44,927,623 | github.com/motiondivision/motion | SUS | Flagged — planner must add `checkpoint:human-verify` before installing IF the UI-SPEC step decides to adopt React Bits/Framer Motion polish; NOT required for the phase's core contract |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** `framer-motion` — flagged on a "too-new" publish-date heuristic; the package itself has an 8+ year history and 44.9M weekly downloads (likely a false positive from a recent version bump under the renamed `motion` project), but the flag stands per protocol until a human confirms — gate any future install behind `checkpoint:human-verify`.

## Architecture Patterns

### System Architecture Diagram

```text
Browser (React SPA)
  │
  ├─ CommandCentre.tsx ──GET──▶ /api/systems/{id}/assurance-cards  (×2 systems)   ─┐
  │                      ──GET──▶ /api/actions                                     │ compose
  │                      ──GET──▶ /api/audit/verify                                │ client-side
  │                      ──GET──▶ /api/systems/{id}/access-supplier-signals (NEW) ─┘  → dial %, 6 mini-cards
  │
  ├─ Copilot.tsx (chat)  ──GET(SSE)──▶ /api/systems/{id}/assurance-cards/stream
  │      │                              (existing route, D-01: bypasses LangGraph,
  │      │                               calls A2 + C1 directly)
  │      │                    onCard(card) → append AssuranceCard to chat bubble (D-05)
  │      │                    stream open  → AgentTopologyCanvas: A0,A2 → "running"
  │      │                    onDone       → AgentTopologyCanvas: A0,A2,C1 → "complete"
  │      │
  │      └─ non-hero-query text ──POST(NEW, or client-only)──▶ detect_injection()-backed
  │                                  honest "not supported" response (D-04, Claude's discretion)
  │
  ├─ Actions.tsx (existing, Phase 5) ──POST──▶ /api/actions/{id}/approve|reject
  │                                    ──WS───▶ /api/copilot/stream/{session_id}
  │                                              (existing action_proposal_created frame)
  │
  ├─ FindingInvestigation.tsx / BlastRadius.tsx (existing, Phase 4 — reused by Guided Tour, not rebuilt)
  │
  └─ GuidedTourOverlay (NEW, cross-route)
         │  state machine: step index → { route, target selector, wait-for-real-event }
         ├─ navigate(route) via react-router useNavigate
         ├─ react-joyride <Joyride> controlled stepIndex/run — spotlight + tooltip only
         ├─ before "approve" step: GET /api/actions, filter by finding_id/status (D-09 idempotency guard)
         └─ before "audit" step: GET /api/audit/verify

FastAPI backend (all routes below already exist and are read this session — no LangGraph invocation in this phase's data path)
  routes/findings.py   → assurance-cards, assurance-cards/stream   (A2 + C1, direct call)
  routes/actions.py    → actions list, generate-capa, approve, reject (A7 + C3 + audit_trail)
  routes/audit.py      → audit/verify, audit/demonstrate-tamper     (audit_trail.verify_chain)
  routes/evidence_graph.py → evidence-graph, blast-radius           (NetworkX, unchanged)
  [NEW] routes/system_signals.py (recommended name) → access-supplier-signals (queries suppliers, access_reviews, access_records directly — mirrors minimal_specialists._check_a6's query pattern, which is otherwise only reachable via the LangGraph node path, not HTTP)
         │
         ▼
   Postgres (gxp_systems, suppliers, access_reviews, access_records, action_proposals, audit_events)
```

### Recommended Project Structure
```
frontend/src/
├── pages/
│   ├── CommandCentre.tsx        # full rebuild (currently a static placeholder — read this session)
│   └── Copilot.tsx              # full rebuild (currently a bare WS echo-test stub — read this session)
├── components/
│   ├── AgentTopologyCanvas.tsx  # EXTEND (add nodeStatus prop), do not restructure topology
│   ├── ReadinessDial.tsx        # NEW — hand-rolled SVG arc
│   ├── HealthMiniCard.tsx       # NEW — shared card shell for the 6 mini-cards
│   ├── ChatMessage.tsx          # NEW — renders a user turn or an AssuranceCard-bearing assistant turn
│   └── GuidedTourOverlay.tsx    # NEW — wraps react-joyride, owns step state machine
├── lib/
│   ├── api.ts                   # EXTEND — add fetchSystemSignals() for the one new endpoint
│   ├── tourSteps.ts              # NEW — the 8-step step table (route, target, title per Bible §14.4)
│   └── ws.ts / identity.ts      # unchanged
backend/app/routes/
└── system_signals.py            # NEW — the one net-new backend route this phase needs
```

### Pattern 1: SSE-driven incremental chat rendering (reuse, don't invent)
**What:** `streamAssuranceCards()` (`frontend/src/lib/api.ts:196-258`, already built) opens a `fetch` + `body.getReader()` stream and dispatches `onCard`/`onDone`/`onError` callbacks as SSE frames arrive.
**When to use:** Directly for the Copilot chat's hero-query response — this is the exact mechanism `FindingInvestigation.tsx` already uses (`frontend/src/pages/FindingInvestigation.tsx:96-127`), just re-targeted to append into a chat bubble array instead of a flat card list.
**Example (established pattern, not new code):**
```typescript
// Source: frontend/src/pages/FindingInvestigation.tsx:96-127 (read this session)
streamAssuranceCards(systemId, {
  onCard: (card) => setCards((prev) => [...prev, card]),
  onDone: () => setState('ready'),
  onError: () => setState('error'),
}, controller.signal)
```

### Pattern 2: Cancelled-guard fetch effect
**What:** Every existing data-fetching page (`FindingInvestigation.tsx`, `Actions.tsx`) uses a `let cancelled = false` guard inside `useEffect` to avoid setting state after unmount/dependency-change.
**When to use:** Every new fetch in `CommandCentre.tsx` (the four-endpoint aggregation) and `Copilot.tsx` must follow this exact convention — it is the established pattern, not optional cleanup.
**Example:**
```typescript
// Source: frontend/src/pages/Actions.tsx:59-74 (read this session)
useEffect(() => {
  let cancelled = false
  fetchActionProposals()
    .then((response) => { if (cancelled) return; /* ... */ })
    .catch(() => { if (cancelled) return; /* ... */ })
  return () => { cancelled = true }
}, [identity, retryToken])
```

### Pattern 3: `AgentTopologyCanvas` extension (colours only)
**What:** The component's own docstring already anticipates this phase: `"Phase 6's live agent-state streaming replaces node *colours* only, not this component"` `[VERIFIED: frontend/src/components/AgentTopologyCanvas.tsx:5]`. Today it takes no props and renders static nodes/edges (`frontend/src/components/AgentTopologyCanvas.tsx:8-19`).
**When to use:** Add a `nodeStatus?: Record<string, 'waiting' | 'running' | 'complete'>` prop; map it onto each node's `style`/`className` at render time. Do not change `SPECIALIST_IDS`, node positions, or edges.
**Example skeleton:**
```typescript
// Extends frontend/src/components/AgentTopologyCanvas.tsx:8-19 (existing node array, read this session)
export interface AgentTopologyCanvasProps {
  nodeStatus?: Record<string, 'waiting' | 'running' | 'complete'>
}
// nodes.map(n => ({ ...n, className: statusClassFor(nodeStatus?.[n.id] ?? 'waiting') }))
```

### Pattern 4: Reusing `detect_injection` for an honest D-04 response
**What:** `detect_injection(text: str) -> Optional[str]` (`backend/app/agents/c2_gateway.py:100-125`) is a pure, already-tested, zero-I/O, zero-LLM function: `"""Returns a reason string when injection is suspected, else None."""` — it is not currently called from any HTTP route (confirmed by grep across `backend/app/routes/*.py`), only from the LangGraph node body `run_c2` (line 128).
**When to use:** A new, small route (or inline logic in a new `POST /api/copilot/query`-style endpoint, planner's call) can call `detect_injection(query)` directly for any free-text chat input that isn't the hero-query shape — returning a real "this looks like a prompt-injection attempt, blocked" message when it matches, and the honest "not supported yet" message otherwise. This gives Guided Tour Step 6 ("AI Safety") a real, deterministic backend call to demonstrate instead of nothing.
**Example:**
```python
# Source: backend/app/agents/c2_gateway.py:100-125 (read this session, function body unmodified)
from app.agents.c2_gateway import detect_injection
reason = detect_injection(user_free_text)
if reason:
    return {"blocked": True, "reason": reason}  # e.g. "regex_match:(?i)(ignore previous instructions|...)"
```

### Anti-Patterns to Avoid
- **Reading `gxp_systems.readiness_score` for the dial:** `[VERIFIED: AegisX-AI-Project-Bible-v6.md:600]` (`readiness_score INT DEFAULT 0`) and `[VERIFIED: infra/postgres/seed/001_seed.sql:32-34,93-95]` (`VALUES ('GXP-MFG-DEMO-01', ..., 61, ...)`, `VALUES ('BUS-IT-DEMO-02', ..., 94, ...)`) — these are static seed literals never recomputed by any code path touched since Phase 2. D-06 requires the dial to reflect real, live aggregate state (assurance-cards pass/fail ratio) — this column is not that.
- **Calling `generate-capa` unconditionally on every Guided Tour run:** `persist_proposal` (`backend/app/agents/c3_gateway.py:108-138`) has no idempotency check — a second call for the same `finding_id` inserts a second `action_proposals` row with a fresh `AP-{timestamp}` id. The tour MUST check `/api/actions` for an existing proposal against the demo `finding_id` before calling `generate-capa` again (D-09's own required defensive handling).
- **Building a new WS frame type for agent state:** explicitly deferred (CONTEXT.md Deferred Ideas) — D-02 already specifies client-side synthesis off the existing SSE stream; a new WS event type here would be scope creep past this phase's own locked decision.
- **Gating the new `/access-supplier-signals` read route with RBAC:** the Phase 4/5 precedent is explicit — read routes (`evidence_graph.py`, `findings.py`, `GET /api/audit/verify`) are deliberately ungated (`backend/app/routes/actions.py:14-19` module docstring: "The Phase 4 read routes... are deliberately left ungated per D-04 — this module adds no middleware to them, and this docstring is the record that the omission is intentional"). The new read endpoint should follow the same pattern for consistency, not introduce a one-off RBAC gate on a read-only aggregate.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-viewport element highlighting + tooltip positioning for the Guided Tour | A custom `getBoundingClientRect`-based spotlight/tooltip engine with scroll-into-view and resize listeners | `react-joyride` | Positioning math against a moving, resizable, scrollable viewport is exactly the kind of "looks simple, has a dozen edge cases" problem (offscreen targets, mobile viewport shifts, z-index stacking under the existing `PrototypeBanner`/`NavBar` fixed elements) this project's own philosophy warns against reinventing. A maintained, 1.3M-weekly-download library absorbs that complexity; the actual bespoke work this phase needs (cross-route step sequencing, waiting for real backend state, D-09 idempotency checks) is a thin wrapper around it, not a reason to avoid it. |
| Detecting whether a Guided Tour step's target state is "already done" | Ad-hoc client-only flags that assume a single tour run per session | Query the real backend state the step depends on (`GET /api/actions` filtered by `finding_id`, `GET /api/audit/verify`) before deciding to act or skip | The state the tour cares about (a pending vs. already-approved proposal) lives server-side and can change between tour runs, across tabs, or via direct API use outside the tour — a client-only "have I done this before" flag will silently desync from reality exactly when a judge re-runs the demo. |

**Key insight:** Everything genuinely deterministic and safety-relevant in this phase (RBAC, injection detection, confidence scoring, hash-chain verification) is already built and tested from Phases 3–5 — this phase's only hand-roll risk is on the *presentation* side (tour positioning math, dial/timing synthesis), where the cost of getting it wrong is a broken demo, not a compliance failure, but is still worth avoiding via a proven library where one directly fits (the tour), and worth keeping simple/dependency-free where the problem really is simple (the dial, a single SVG arc).

## Common Pitfalls

### Pitfall 1: Treating `gxp_systems.readiness_score` as live data
**What goes wrong:** The dial silently shows a static, stale percentage (61% / 94%) that never changes regardless of real system state, contradicting D-06's explicit requirement and the product's own "never present unverified/stale state as real" thesis.
**Why it happens:** The column exists, is named exactly what the UI-03 requirement asks for, and is the path of least resistance — a quick `SELECT readiness_score FROM gxp_systems` looks correct at a glance.
**How to avoid:** Compute the dial from `GET /api/systems/{id}/assurance-cards` (pass/fail ratio across `A2_CHECKS`, 4 checks per system) for both seeded systems, exactly as D-06 specifies.
**Warning signs:** The dial value never changes even after a proposal is approved or a seeded gap is (hypothetically) fixed.

### Pitfall 2: Duplicate action proposals across Guided Tour re-runs
**What goes wrong:** Each `POST .../generate-capa` call for the same `finding_id` creates a new, separate `PENDING_APPROVAL` row (no idempotency guard in `persist_proposal`) — after a few tour re-runs (demo rehearsals, judge re-runs), the Approval Centre accumulates duplicate proposals for the same finding, undermining D-09 and confusing the demo.
**Why it happens:** `persist_proposal` (`backend/app/agents/c3_gateway.py:108-138`, read this session) mints a fresh `AP-{utc strftime}` id on every call with no existence check.
**How to avoid:** Before the tour's remediation step calls `generate-capa`, first `GET /api/actions` and check for an existing proposal with the same `finding_id` (any status) — reuse it (jump straight to showing/approving it) rather than minting a new one.
**Warning signs:** The Approval Centre's pending count grows on every tour run even though the same finding is always used.

### Pitfall 3: SSE stream leaks across chat turns / system switches
**What goes wrong:** If the Copilot chat lets a user ask a second hero query before the first stream's `AbortController` is triggered, two concurrent SSE readers can interleave cards into the wrong chat bubble.
**Why it happens:** `streamAssuranceCards` (existing, `frontend/src/lib/api.ts:196-258`) is stateless per call — nothing prevents a second call from starting while the first is still open.
**How to avoid:** Follow `FindingInvestigation.tsx`'s established pattern exactly: one `AbortController` per query, `controller.abort()` on cleanup/re-trigger, and treat `DOMException`/`AbortError` as expected cancellation, not a stream failure (`frontend/src/pages/FindingInvestigation.tsx:96-127`, read this session).
**Warning signs:** Cards from an old query appearing in a new chat turn, or duplicate "done" states.

### Pitfall 4: Session-agnostic WS broadcast noise during the tour
**What goes wrong:** `/api/copilot/stream/{session_id}` broadcasts `action_proposal_created` to **every** connected client regardless of session id (`[VERIFIED: frontend/src/lib/ws.ts:8-9]` — "On a new action proposal (any connected client, any session)"; `[VERIFIED: backend/app/routes/actions.py:90-100]` `_broadcast_new_proposal` docstring: "best-effort... A dead/misbehaving socket must not roll back or fail..."). If a second browser tab or a stray earlier demo run creates a proposal while the Guided Tour is live, the tour's Actions-page WS listener will see an unrelated proposal arrive.
**Why it happens:** The stream was built session-agnostic in Phase 5 for simplicity (single-demo-instance assumption).
**How to avoid:** The tour's "wait for the proposal to appear" step should key off the specific `finding_id`/`proposal_id` it triggered (from the `generate-capa` response), not "any" `action_proposal_created` frame.
**Warning signs:** Tour advances or highlights the wrong proposal card in a multi-tab demo environment.

## Code Examples

### Reading assurance cards for dial aggregation (existing, blocking route)
```typescript
// Source: frontend/src/lib/api.ts:148-152 (read this session, unmodified)
export function fetchAssuranceCards(systemId: string): Promise<AssuranceCardsResponse> {
  return apiGet<AssuranceCardsResponse>(
    `/api/systems/${encodeURIComponent(systemId)}/assurance-cards`,
  )
}
// Command Centre usage: call for both SYSTEM_OPTIONS ids, sum cards.length (failing checks)
// against the fixed A2_CHECKS count (4 per system) to get a pass ratio.
```

### Audit chain status for mini-card #3 (existing route, verbatim response)
```python
# Source: backend/app/routes/audit.py:43-49 (read this session, unmodified)
@router.get("/api/audit/verify", response_model=ChainVerificationResponse)
async def get_chain_verification():
    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")
    return ChainVerificationResponse(**await verify_chain(pool))
# verify_chain returns {"status": "VERIFIED", "events_checked": N}
# or {"status": "TAMPERED", "broken_at_index": i, "event_id": "..."}
# Source: backend/app/audit_trail.py:190-227 (read this session)
```

### Access/supplier overdue query pattern to mirror for the new endpoint
```python
# Source: backend/app/agents/minimal_specialists.py:332-346 (read this session — this exact
# query is currently only reachable via the LangGraph node path, not any HTTP route)
async def _check_a6(pool, system_id: str):
    now_ns = time.time_ns()
    review_row = await pool.fetchrow(
        "SELECT id, scheduled_date_ns FROM access_reviews WHERE system_id = $1 "
        "AND status != 'COMPLETED' AND scheduled_date_ns < $2 "
        "ORDER BY scheduled_date_ns ASC LIMIT 1",
        system_id, now_ns,
    )
    orphan_row = await pool.fetchrow(
        "SELECT id FROM access_records WHERE system_id = $1 "
        "AND is_privileged = TRUE AND user_status = 'DEPARTED' "
        "ORDER BY id LIMIT 1",
        system_id,
    )
# The new /access-supplier-signals endpoint should add an analogous suppliers query:
# SELECT id, name, reassessment_due_date_ns FROM suppliers
# WHERE system_id = $1 AND reassessment_due_date_ns < $2
# (mirrors Rego rule ANNEX11-S3-SUP-001, Bible Section 3.3 rule #6, lines 482-493)
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A new backend read endpoint (suggested name `/api/systems/{id}/access-supplier-signals`) is the right shape for D-07's mini-card #4, rather than client-side raw queries or reusing `_check_a6` directly | Architecture Patterns, Code Examples | Low — this is Claude's Discretion per CONTEXT.md; the underlying finding (no existing route exposes suppliers/access_reviews data) is verified, only the exact endpoint shape/name is assumed |
| A2 | The Copilot's D-04 "not supported yet" response should be wired through a real backend call to `detect_injection()` rather than being a pure client-side string | Don't Hand-Roll, Code Examples | Medium — CONTEXT.md explicitly leaves this to Claude's Discretion; if the planner instead chooses the client-only guard, Guided Tour Step 6 ("AI Safety") has no real backend call to demonstrate, which may undercut D-08's "REAL backend calls" requirement for that specific beat |
| A3 | The C2 node (RBAC + injection gateway) should render as permanently "Waiting"/dimmed on the topology canvas, matching D-02's treatment of A1/A3–A6, since D-01 confirms the hero-query SSE route bypasses C2 entirely | Architecture Patterns (diagram) | Low — CONTEXT.md's D-02 text does not explicitly mention C2's node state; this is an inference from D-01's "bypasses the graph" language, not a stated decision |
| A4 | `react-joyride`, not `driver.js` or a hand-rolled overlay, is the right tour engine pick | Standard Stack | Low-Medium — this is a library recommendation for Claude's Discretion (tour library vs. custom, per CONTEXT.md "Specific Ideas"); reversible at low cost since only ~1 component wraps it |
| A5 | The Bible §14.4 8-step sequence's steps 4 ("Deterministic Verification" FSM animation) and 6 ("AI Safety" prompt-injection UI) have no dedicated real page to point the tour at in v1 (VERF-03 Verification Centre and FE-03 Assurance Lab are both explicitly v2/out-of-scope) — CONTEXT.md's own D-08 prose already narrows the tour to 4 named surfaces (Command Centre, Copilot, Actions, audit trail) rather than 8 distinct pages, which this research reads as an implicit acknowledgment of this gap | Open Questions | Medium — if the planner instead tries to build literal new pages for steps 4/6 to match the Bible's page count exactly, that is scope creep past this phase's REQUIREMENTS.md (UI-03/UI-04 only) and past SENT-5-01/5-08's ticket contracts |

## Open Questions

1. **How do the Bible's 8 named tour steps map onto the 4 real surfaces D-08 names?**
   - What we know: D-08 explicitly says the tour drives "Command Centre, Copilot hero query + topology + streaming cards, approve a proposal on Actions.tsx, check the audit trail" — 4 legs. The Bible's §14.4 sequence names 8 steps: Command Centre, Finding, Evidence, Deterministic Verification (FSM), Blast Radius, AI Safety, Controlled Remediation, Audit Integrity.
   - What's unclear: Whether "Finding"+"Evidence" collapse into the Copilot chat's inline `AssuranceCard` (which already renders CLAIM/EVIDENCE/RULE/DETERMINISTIC CHECK/CONFIDENCE per EVID-03 — plausibly covering steps 2, 3, *and* 4 at once), whether "Blast Radius" (step 5) is folded in via the existing `FindingInvestigation.tsx`-style evidence-node links (already built, `frontend/src/pages/FindingInvestigation.tsx:212-235`), and whether "AI Safety" (step 6) gets a real beat via the `detect_injection` wiring (Assumption A2) or is dropped/narrated-only.
   - Recommendation: The planner should produce an explicit 8-step-to-N-real-surface mapping table as part of the plan (not left implicit), using the inline `AssuranceCard` + existing `BlastRadius.tsx` + a `detect_injection`-backed chat response to cover as many of the 8 named beats with REAL data as possible, per D-08's own "not a scripted/static walkthrough" requirement — rather than inventing new stub pages that don't exist in v1 scope.

2. **Should the new `/access-supplier-signals` endpoint aggregate across both systems server-side, or per-system with client aggregation?**
   - What we know: D-06 requires cross-system aggregation by default with a system-selector narrow-down. The existing `/assurance-cards` and `/api/actions` patterns are per-system or global respectively — no existing precedent for a cross-system aggregate route.
   - What's unclear: Whether the new endpoint should accept `system_id` (matching every other route's shape) and let the frontend call it twice, or expose a `/api/systems/access-supplier-signals` (no id) that aggregates server-side.
   - Recommendation: Follow the existing per-system route shape (`/api/systems/{id}/access-supplier-signals`) for consistency with every other route in the codebase, and aggregate client-side exactly as D-06 already does for the dial — avoids inventing a new response shape.

## Environment Availability

No new external service/runtime dependency is introduced by this phase — Postgres, OPA, and the FastAPI backend were already required and verified running by Phases 1–5 (`ENV-01`..`ENV-04`, all marked Complete in `.planning/REQUIREMENTS.md`). The only new environment consideration is the frontend's `npm install react-joyride` (if adopted), which is a standard dev-time dependency install, not a new service.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Postgres / OPA / FastAPI backend | All four existing routes this phase composes over | ✓ (established Phases 1–5) | — | — |
| react-joyride (npm) | Guided Tour (SENT-5-08) | ✓ on registry, not yet installed | 3.2.0 | Hand-rolled overlay or `driver.js` (see Alternatives) |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** react-joyride is not yet installed in this repo — trivial `npm install`, with `driver.js` or a hand-rolled overlay as documented fallbacks if the team declines the new dependency.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Backend framework | pytest, `[VERIFIED: backend/pytest.ini]` (`testpaths = tests`, `pythonpath = .`) |
| Frontend framework | Vitest 4.1.11 + @testing-library/react 16.3.2, `[VERIFIED: frontend/vite.config.ts:1-19]` (`test: { environment: 'jsdom', globals: true, setupFiles: './vitest.setup.ts' }`) |
| Config file | `backend/pytest.ini`; `frontend/vite.config.ts` (test block) + `frontend/vitest.setup.ts` |
| Quick run command | `pytest tests/test_routes_findings.py -x` (backend); `npm run test -- Actions.test.tsx` (frontend) |
| Full suite command | `pytest` (backend, from `backend/`); `npm run test` (frontend, from `frontend/`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-03 | Command Centre renders a readiness dial value derived from live assurance-cards data across both systems | unit (component) | `npm run test -- CommandCentre.test.tsx` | ❌ Wave 0 — new file, but existing `stubAssuranceCardsFetch`/`jsonResponse` helpers (`frontend/src/__tests__/helpers/sseFetch.ts`, read this session) directly cover mocking the underlying fetches |
| UI-03 | Command Centre's 4th mini-card reflects overdue supplier/access data | unit (backend route) + unit (component) | `pytest tests/test_routes_system_signals.py -x` (new); `npm run test -- CommandCentre.test.tsx` | ❌ Wave 0 — both new; backend pattern mirrors `tests/test_routes_findings.py`'s existing structure |
| UI-04 | Copilot hero query streams `AssuranceCard`s into the chat in arrival order | unit (component) | `npm run test -- Copilot.test.tsx` | ❌ Wave 0 — new file; reuse `assuranceCardsStreamResponse`/`stubAssuranceCardsFetch` from `frontend/src/__tests__/helpers/sseFetch.ts` (already covers exactly this wire format) |
| UI-04 | Topology canvas nodes transition Waiting→Running→Complete off real SSE timing | unit (component) | `npm run test -- AgentTopologyCanvas.test.tsx` | ❌ Wave 0 — new file; existing `ResizeObserverMock` in `frontend/vitest.setup.ts` already handles the `@xyflow/react` jsdom requirement |
| UI-04 | Non-hero-query chat input gets an honest "not supported"/injection-blocked response, never a fabricated answer | unit (backend, if D-04 resolved to backend call) | `pytest tests/test_c2_gateway.py -x` (existing, covers `detect_injection` itself) + new route test | Partial — `detect_injection`'s own unit coverage already exists (`tests/test_c2_gateway.py`); a new HTTP-boundary test is needed if a route is added |
| SENT-5-08 (Guided Tour) | Tour completes all 8 beats without re-creating a duplicate action proposal on a second run | integration | `pytest tests/test_routes_actions.py -x` (existing idempotency-adjacent coverage) + new frontend integration test for the tour's skip-detection logic | ❌ Wave 0 — the skip-detection logic itself (D-09) has no existing test; must be written new |

### Sampling Rate
- **Per task commit:** run the specific new/changed test file (e.g. `npm run test -- CommandCentre.test.tsx`).
- **Per wave merge:** full frontend (`npm run test`) + full backend (`pytest`) suites.
- **Phase gate:** Full suite green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `frontend/src/__tests__/CommandCentre.test.tsx` — covers UI-03 (dial + 6 mini-cards)
- [ ] `frontend/src/__tests__/Copilot.test.tsx` — covers UI-04 (chat + hero query + non-hero-query path)
- [ ] `frontend/src/__tests__/AgentTopologyCanvas.test.tsx` — covers UI-04 (node status coloring)
- [ ] `frontend/src/__tests__/GuidedTourOverlay.test.tsx` — covers SENT-5-08 (step sequencing + D-09 skip detection)
- [ ] `backend/tests/test_routes_system_signals.py` — covers the new access/supplier signals endpoint (Wave 0 must also create `backend/app/routes/system_signals.py` itself)
- [ ] No framework install needed — both pytest and Vitest are already fully configured and exercised by 25+ existing test files in each suite.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | This phase adds no new authentication surface — `require_identity`'s fixed demo-identity model (Phase 5) is unchanged |
| V3 Session Management | No (unchanged) | Copilot's `session_id` remains a client-generated, non-authoritative value per existing `Copilot.tsx` precedent (`frontend/src/pages/Copilot.tsx:7-12`, read this session — "no application state correlates a session id with a server-side record") |
| V4 Access Control | Yes | New read endpoint (`/access-supplier-signals`) should follow the existing deliberate "read routes are ungated" pattern (`backend/app/routes/actions.py:14-19`); it must NOT introduce a one-off RBAC gate inconsistent with sibling read routes, and must NOT accidentally expose a write capability |
| V5 Input Validation | Yes | Any new backend endpoint accepting a `system_id` path parameter must reuse the existing `_system_exists()` guard pattern (`backend/app/routes/evidence_graph.py:31-33`, already used identically in `findings.py`/`actions.py`) — parameterized queries only, no f-string SQL, matching the established codebase-wide convention |
| V6 Cryptography | No | Unaffected — hash-chain logic (`audit_trail.py`) is read-only from this phase's perspective |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Chat input reflecting unescaped user text into the DOM (stored/reflected XSS) | Tampering / Information Disclosure | React's default JSX text-node escaping already prevents this as long as no new code uses `dangerouslySetInnerHTML` to render chat messages — verified no existing component in this codebase uses it |
| Prompt injection via the new free-text chat field | Tampering (of downstream agent behavior) | `detect_injection()` (`c2_gateway.py:100-125`) already implements the Bible's required deterministic (non-LLM) regex + entropy detection — this phase's obligation is to actually invoke it on the chat's non-hero-query path (Assumption A2), not to build new detection logic |
| A second, unauthenticated caller hitting the new `/access-supplier-signals` read endpoint directly (not through the UI) | Information Disclosure | Acceptable per existing precedent — this is read-only, non-PII aggregate GxP metadata, matching every other ungated read route already shipped; no new exposure class is introduced |

## Sources

### Primary (HIGH confidence)
- `AegisX-AI-Project-Bible-v6.md` §1.2 (LangGraph topology, lines 97-196), §1.3 (deterministic-first table, lines 198-228), §10.3 (React Flow Trace Chain, lines 1364-1366), §11.1/11.2 (Command Centre / Copilot specs, lines 1372-1378), §14.4 (Guided Tour 8-step sequence, lines 1918-2135), §12 (API table, lines 1404-1420), §4.1 DDL (`gxp_systems`, `suppliers`, `access_reviews`, `access_records`, lines 593-703) — all read directly this session.
- `AegisX-Build-Map.md` Stage 5 ticket table (lines 102-118) — read this session.
- Direct source reads (all this session): `frontend/src/pages/Copilot.tsx`, `frontend/src/pages/CommandCentre.tsx`, `frontend/src/components/AgentTopologyCanvas.tsx`, `frontend/src/lib/ws.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/identity.ts`, `frontend/src/pages/FindingInvestigation.tsx`, `frontend/src/pages/Actions.tsx`, `frontend/src/pages/BlastRadius.tsx`, `frontend/src/pages/AssuranceLab.tsx`, `frontend/src/pages/TrustCentre.tsx`, `frontend/src/App.tsx`, `frontend/src/routes.tsx`, `frontend/src/components/PrototypeBanner.tsx`, `frontend/src/components/AssuranceCard.tsx`, `frontend/src/__tests__/helpers/sseFetch.ts`, `frontend/vitest.setup.ts`, `frontend/vite.config.ts`, `frontend/package.json`, `backend/app/routes/findings.py`, `backend/app/routes/actions.py`, `backend/app/routes/audit.py`, `backend/app/routes/evidence_graph.py`, `backend/app/main.py`, `backend/app/schemas.py`, `backend/app/identity.py`, `backend/app/agents/c2_gateway.py`, `backend/app/agents/minimal_specialists.py`, `backend/app/agents/a2_compliance.py` (grep-confirmed `A2_CHECKS` tuple), `backend/app/agents/c3_gateway.py` (`persist_proposal`), `backend/app/audit_trail.py` (`verify_chain`), `infra/postgres/seed/001_seed.sql`, `.planning/config.json`, `.planning/phases/05-safety-remediation/05-UI-SPEC.md`.
- npm registry checks via `npm view` and `gsd-tools query package-legitimacy check` (this session): `react-joyride`, `driver.js`, `recharts`, `framer-motion`.

### Secondary (MEDIUM confidence)
- WebSearch: "React Bits components framer-motion dependency requirements" — confirms React Bits is a copy-paste component library (via shadcn CLI) built on Framer Motion + Tailwind, not a standalone installable package.

### Tertiary (LOW confidence)
- None — all findings in this document are either read from source this session or verified against the npm registry/legitimacy checker.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH for "no new dependency required for core UI-03/UI-04 contract" (verified via package.json + route reads); MEDIUM for the react-joyride recommendation specifically (verified on registry, but not yet integrated/tested in this repo, and genuinely contested against the project's own zero-library precedent)
- Architecture: HIGH — every integration point (SSE reuse, WS broadcast semantics, RBAC gating pattern, missing endpoint) was confirmed by reading the actual route/agent source this session, not inferred from the Bible alone
- Pitfalls: HIGH — all four pitfalls are backed by a specific, quoted source line (stale seed column, missing idempotency check, existing abort-guard pattern, session-agnostic broadcast), not speculative

**Research date:** 2026-08-27
**Valid until:** 30 days (stable — no fast-moving external dependency drives this phase; the backend surface is fixed and already shipped)
