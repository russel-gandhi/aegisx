---
phase: 02-foundation
plan: 04
subsystem: ui
tags: [vite, react, typescript, tailwindcss, react-router-dom, xyflow, vitest, testing-library]

requires:
  - phase: 01-environment
    provides: "frontend/README.md tier scaffold with the server-trusted-rendering rule and port-3000 convention"
provides:
  - "Vite + React 19 + TypeScript app shell, buildable and type-checked, serving on port 3000 with strictPort"
  - "Tailwind v4 wired via @tailwindcss/vite plugin (no config.js/postcss — proven live via compiled CSS output, not assumed)"
  - "Data-driven 8-route table (frontend/src/routes.tsx) covering all documented Bible Section 11 pages, with a marked slot for Phase 4's Blast Radius (11.4) route"
  - "AgentTopologyCanvas: @xyflow/react v12 canvas with 11 placeholder nodes laid out in the real C2->A0->[A1..A6]->C1->A7->C3 topology, mounted on /copilot"
  - "Persistent PrototypeBanner rendered above the router outlet on every route"
  - "20-test Vitest + Testing Library route-render suite (frontend/src/__tests__/routes.test.tsx), including a verified failure path"
affects: [02-07, 04-blast-radius, 04-assurance-cards, 05-approval-centre, 06-command-centre]

actuals:
  tokens: 38500
  tasks: 3
  commits: 2

tech-stack:
  added: [vite@8.2.2, react@19.2.8, react-dom@19.2.8, typescript@~6.0.2 (template default), "@vitejs/plugin-react@^6.0.4 (template default)", tailwindcss@4.3.3, "@tailwindcss/vite@4.3.3", "@xyflow/react@12.11.3", react-router-dom@^7.18.2, vitest@^4.1.11, "@testing-library/react@^16.3.2", "@testing-library/jest-dom@^7.0.1", jsdom@^30.0.1]
  patterns:
    - "Route table as data (frontend/src/routes.tsx: { path, label, Component }[]) consumed by both the router and the nav bar, so a route can never exist without a nav link"
    - "AppShell exported separately from App so tests drive it with MemoryRouter instead of duplicating route wiring"
    - "Tailwind v4: @tailwindcss/vite plugin + single @import \"tailwindcss\"; no tailwind.config.js, no postcss.config.js"

key-files:
  created:
    - frontend/src/routes.tsx
    - frontend/src/App.tsx
    - frontend/src/components/PrototypeBanner.tsx
    - frontend/src/components/NavBar.tsx
    - frontend/src/components/AgentTopologyCanvas.tsx
    - frontend/src/pages/CommandCentre.tsx
    - frontend/src/pages/Copilot.tsx
    - frontend/src/pages/AuditReadiness.tsx
    - frontend/src/pages/Suppliers.tsx
    - frontend/src/pages/Actions.tsx
    - frontend/src/pages/AssuranceLab.tsx
    - frontend/src/pages/TrustCentre.tsx
    - frontend/src/pages/InspectionSimulator.tsx
    - frontend/src/__tests__/routes.test.tsx
    - frontend/vite.config.ts
    - frontend/vitest.setup.ts
    - frontend/package.json
  modified:
    - frontend/README.md

key-decisions:
  - "All nine unaudited npm packages verified directly against the live npm registry (maintainer + repository match expected org for every package); no substitutions needed — react-router-dom and the @testing-library/react + jsdom pair both accepted as proposed"
  - "typescript, @vitejs/plugin-react, @types/react, @types/react-dom, @types/node left at the Vite react-ts template's own resolved versions rather than independently pinned, per plan instruction"
  - "tailwindcss / @tailwindcss/vite pinned to 4.3.3 (latest available on npm at scaffold time), not the research's 4.3.4 — reported as version drift, not a substitution"
  - "AppShell factored out of App so the route-render test suite drives it via MemoryRouter without duplicating the route-table wiring used by the real BrowserRouter"

patterns-established:
  - "Route table as data: adding a page means appending one array entry to routes.tsx, not touching the router or nav bar"
  - "Tailwind v4-only setup (no config file) — verified live via the dev server's compiled CSS output, not assumed from a successful build"

requirements-completed: [UI-01]

coverage:
  - id: D1
    description: "npm run build completes with zero TypeScript errors and zero Vite errors, producing a dist/ bundle"
    requirement: UI-01
    verification:
      - kind: unit
        ref: "cd frontend && npm run build"
        status: pass
    human_judgment: false
  - id: D2
    description: "npm run dev serves the app on port 3000, and every one of the 8 documented Section 11 routes renders its own page rather than a shared placeholder or router 404"
    requirement: UI-01
    verification:
      - kind: unit
        ref: "frontend/src/__tests__/routes.test.tsx > route rendering > renders the distinctive heading for <path> (8 cases)"
        status: pass
    human_judgment: true
    rationale: "jsdom render assertions prove headings differ per route; actual browser layout/behavior on port 3000 was smoke-checked via curl + compiled-CSS inspection (dev server confirmed responding 200, Tailwind classes present in compiled output) but not visually screenshotted by a human — flagging for a human spot-check per the plan's own manual verification step."
  - id: D3
    description: "A React Flow canvas is mounted with placeholder nodes and edges and renders without the missing-stylesheet layout collapse that hits v12 when its CSS is not imported"
    requirement: UI-01
    verification:
      - kind: unit
        ref: "frontend/src/__tests__/routes.test.tsx > route rendering > mounts a React Flow canvas with placeholder nodes on /copilot"
        status: pass
      - kind: unit
        ref: "grep -c \"@xyflow/react/dist/style.css\" frontend/src/main.tsx -> 1"
        status: pass
    human_judgment: false
  - id: D4
    description: "Tailwind utility classes actually take visual effect, proving the v4 plugin path is wired rather than silently inert"
    verification:
      - kind: integration
        ref: "curl http://localhost:3000/src/index.css against the running dev server — compiled output contains real utility rules (.bg-red-600, .text-2xl, etc.), not an empty/passthrough stylesheet"
        status: pass
    human_judgment: false
  - id: D5
    description: "The persistent prototype banner appears on every route"
    requirement: UI-01
    verification:
      - kind: unit
        ref: "frontend/src/__tests__/routes.test.tsx > route rendering > shows the prototype banner on <path> (8 cases)"
        status: pass
    human_judgment: false
  - id: D6
    description: "No npm package outside the audited set was installed without an explicit human legitimacy check first"
    verification:
      - kind: manual_procedural
        ref: "Autonomous package legitimacy verification (see below) — npm view against the live registry for all nine unaudited packages"
        status: pass
    human_judgment: true
    rationale: "Per CLAUDE.md/plan checkpoint protocol, package-legitimacy findings must be human-reviewable even when the operator authorized autonomous execution for this run; a human should spot-check the verification table below before this route is fully trusted."

duration: 42min
completed: 2026-08-20
status: complete
---

# Phase 2 Plan 04: Frontend Application Shell Summary

**Vite + React 19 + TypeScript + Tailwind v4 app shell routed to all 8 Bible Section 11 pages, with an `@xyflow/react` v12 canvas laid out in the real C2->A0->[A1..A6]->C1->A7->C3 agent topology on `/copilot`, covered by a 20-test route-render suite.**

## Performance

- **Duration:** 42 min
- **Started:** 2026-08-20T19:41:00Z
- **Completed:** 2026-08-20T20:23:00Z
- **Tasks:** 3 (Task 1 checkpoint resolved autonomously per operator instruction; Tasks 2-3 executed)
- **Files modified:** 29 (frontend/ tree; package-lock.json included)

## Autonomous package legitimacy verification

Per the operator's explicit authorization to proceed autonomously through Task 1's blocking checkpoint (the operator being away for several hours), this executor performed the human-check itself using `npm view <pkg> repository.url maintainers homepage version` against the live npm registry for each of the nine unaudited packages, rather than deferring to end-of-phase. Results:

| Package | Expected maintainer/repo | Registry result | Verdict |
|---|---|---|---|
| `typescript` | Microsoft — github.com/microsoft/TypeScript | `repository.url: git+https://github.com/microsoft/TypeScript.git`, maintainers include `microsoft1es`, `typescript-bot` | Match — approved |
| `@vitejs/plugin-react` | Vite team — github.com/vitejs/vite-plugin-react | `repository.url: git+https://github.com/vitejs/vite-plugin-react.git`, maintainer `yyx990803` (Evan You) | Match — approved |
| `@tailwindcss/vite` | Tailwind Labs — github.com/tailwindlabs/tailwindcss | `repository.url: https://github.com/tailwindlabs/tailwindcss.git`, maintainers `adamwathan`, `reinink` | Match — approved |
| `react-router-dom` | Remix/React Router team — github.com/remix-run/react-router | `repository.url: git+https://github.com/remix-run/react-router.git`, maintainer `mjackson` | Match — approved |
| `@testing-library/react` | Testing Library — github.com/testing-library/react-testing-library | `repository.url: git+https://github.com/testing-library/react-testing-library.git`, maintainer `kentcdodds` | Match — approved |
| `@testing-library/jest-dom` | Testing Library — github.com/testing-library/jest-dom | `repository.url: git+https://github.com/testing-library/jest-dom.git`, maintainer `kentcdodds` | Match — approved |
| `jsdom` | jsdom org — github.com/jsdom/jsdom | `repository.url: git+https://github.com/jsdom/jsdom.git`, maintainer `domenic` | Match — approved |
| `@types/react` | DefinitelyTyped — github.com/DefinitelyTyped/DefinitelyTyped | `repository.url: https://github.com/DefinitelyTyped/DefinitelyTyped.git`, maintainer `types <ts-npm-types@microsoft.com>` | Match — approved |
| `@types/react-dom` | DefinitelyTyped — github.com/DefinitelyTyped/DefinitelyTyped | Same as above | Match — approved |

**Two flagged decisions, both accepted as the plan proposed:**
- `react-router-dom` — accepted as the routing library (no substitution requested by any project source).
- `@testing-library/react` + `jsdom` — accepted, giving UI-01 a real DOM render assertion rather than the weaker route-table-shape fallback.

**Negative case confirmed:** neither `react-flow-renderer` nor `reactflow` appears anywhere in `frontend/package.json` (`grep -cE '"(react-flow-renderer|reactflow)"' frontend/package.json` → `0`); only `@xyflow/react` was installed.

A human should still spot-check this table before treating it as equivalent to an interactive approval — this record exists precisely so that spot-check is possible.

## Accomplishments
- Scaffolded a clean Vite `react-ts` app into the existing `frontend/` tree without disturbing the Phase 1 README, then wired Tailwind v4 (`@tailwindcss/vite` + single `@import`) and proved it live by inspecting the dev server's compiled CSS output rather than trusting a successful build alone.
- Built a data-driven 8-route table covering every currently-documented Bible Section 11 page, with the 11.4 (Blast Radius) gap explicitly commented as Phase 4's future 9th entry.
- Mounted an `@xyflow/react` v12 canvas (named `{ ReactFlow }` import) on `/copilot` with all 11 agent-topology nodes (`C2, A0, A1-A6, C1, A7, C3`) laid out in the real pipeline shape, not as anonymous placeholder boxes.
- Wrote a 20-test Vitest + Testing Library suite asserting per-route headings, banner persistence, 404 fallback, React Flow mount, and route-table shape — and proved the suite can actually fail by deliberately breaking one page's heading, confirming the failure named the correct route, then restoring it to green.

## Task Commits

1. **Task 1: Package legitimacy gate** — resolved autonomously (no commit; verification recorded above per operator authorization to proceed without waiting)
2. **Task 2: Scaffold the Vite app with Tailwind v4 and React Flow v12** - `6a0b31f` (feat)
3. **Task 3: Route to all eight Bible Section 11 pages behind the prototype banner** - `3695349` (feat)

## Files Created/Modified
- `frontend/package.json` / `frontend/package-lock.json` - dependency manifest; six research-audited packages + nine autonomously-verified packages, all pinned or template-default per plan instruction
- `frontend/vite.config.ts` - React + Tailwind v4 plugins, port 3000 `strictPort: true`, Vitest jsdom config
- `frontend/src/index.css` - single `@import "tailwindcss";` line (v4 pattern, no config file)
- `frontend/src/main.tsx` - imports `@xyflow/react/dist/style.css` once, ahead of app render
- `frontend/src/routes.tsx` - exported 8-entry route table, data source for both router and nav
- `frontend/src/App.tsx` - `AppShell` (banner + nav + routed outlet) wrapped in `BrowserRouter` by default-exported `App`
- `frontend/src/components/PrototypeBanner.tsx` - the exact Bible-mandated banner string
- `frontend/src/components/NavBar.tsx` - links derived from `routes.tsx`
- `frontend/src/components/AgentTopologyCanvas.tsx` - React Flow v12 canvas, 11 nodes in real topology
- `frontend/src/pages/*.tsx` (8 files) - one component per documented route
- `frontend/src/__tests__/routes.test.tsx` - 20-test route-render suite
- `frontend/vitest.setup.ts` - jest-dom matchers + a `ResizeObserver` mock (jsdom has none; `@xyflow/react` needs one to mount)
- `frontend/tsconfig.app.json` - added `@testing-library/jest-dom` to `types` (see Deviations)
- `frontend/README.md` - extended with `## Shell (Stage 1)` section

## Decisions Made
- Scaffolded into a temporary sibling directory (`npm create vite@latest vite-scaffold-tmp`) and moved generated files into `frontend/`, rather than scaffolding in place, because the existing committed `README.md` made the target directory non-empty and `create-vite` would otherwise refuse — preserved the Phase 1 README exactly as instructed.
- Kept the Vite template's own `.gitignore` and `.oxlintrc.json` alongside the root `.gitignore` (which already covers `node_modules/`/`dist/`) — both are official template defaults, not agent inventions, and harmless to keep.
- Removed the Vite template's demo assets (`App.css`, `assets/hero.png`, `assets/react.svg`, `assets/vite.svg`) since Task 3 fully replaces `App.tsx`'s content; kept `public/favicon.svg` and `public/icons.svg` as they're referenced by `index.html`/the original demo markup pattern and are harmless static assets.
- Renamed `package.json`'s `name` field from the scaffold tool's default (`vite-scaffold-tmp`) to `gxp-sentinel-frontend`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] `tsc -b` failed on jest-dom matchers not resolving**
- **Found during:** Task 3, running `npm run build` after writing the test suite
- **Issue:** `frontend/src/__tests__/routes.test.tsx` uses `.toBeInTheDocument()` from `@testing-library/jest-dom`, but `tsconfig.app.json`'s `types` array only listed `vite/client`, so the project-level `tsc -b` build (used by `npm run build`) failed with `TS2339: Property 'toBeInTheDocument' does not exist` even though `vitest run` itself passed (Vitest resolves matcher types differently at runtime).
- **Fix:** Added `@testing-library/jest-dom` to `tsconfig.app.json`'s `types` array.
- **Files modified:** `frontend/tsconfig.app.json`
- **Verification:** `npx tsc --noEmit` and `npm run build` both exit 0 after the fix; `npm test` still 20/20 passing.
- **Committed in:** `3695349` (part of Task 3 commit)

**2. [Rule 2 - Missing critical functionality] jsdom has no `ResizeObserver`, which `@xyflow/react` requires to mount**
- **Found during:** Task 3, writing the React Flow mount assertion in `routes.test.tsx`
- **Issue:** `@xyflow/react`'s pane measurement uses `ResizeObserver`, which does not exist in jsdom's global scope; without a stand-in, the `/copilot` route test would throw `ReferenceError: ResizeObserver is not defined` rather than genuinely testing the canvas mount.
- **Fix:** Added a minimal no-op `ResizeObserverMock` class registered as `globalThis.ResizeObserver` in `vitest.setup.ts`, guarded so it only applies if the environment doesn't already provide one.
- **Files modified:** `frontend/vitest.setup.ts`
- **Verification:** The React Flow mount test (`mounts a React Flow canvas with placeholder nodes on /copilot`) passes and genuinely asserts `.react-flow` and `.react-flow__node` elements exist, not just that no exception was thrown.
- **Committed in:** `3695349` (part of Task 3 commit)

**3. [Rule 1 - Bug] Vite template's default demo content would not build after Tailwind/asset cleanup**
- **Found during:** Task 2, after wiring Tailwind and importing the React Flow stylesheet
- **Issue:** The stock `App.tsx` from `npm create vite@latest ... --template react-ts` imports `./App.css` and three demo images; deleting the unused demo assets (`App.css`, `assets/hero.png`, `assets/react.svg`) as planned for Task 3's full `App.tsx` replacement would break Task 2's standalone build if left as-is.
- **Fix:** Replaced Task 2's `App.tsx` with a minimal Tailwind-styled placeholder (`bg-slate-950`/`bg-slate-900` card) that builds cleanly on its own and doubles as the live Tailwind proof-of-wiring; Task 3 then fully replaced it with the routed `AppShell`.
- **Files modified:** `frontend/src/App.tsx` (twice — once in Task 2, once in Task 3)
- **Verification:** `npm run build` exits 0 after both Task 2 and Task 3.
- **Committed in:** `6a0b31f` (Task 2), `3695349` (Task 3)

---

**Total deviations:** 3 auto-fixed (1x Rule 1, 1x Rule 2, 1x Rule 3)
**Impact on plan:** All three were required for the build/test suite to genuinely pass rather than appear to pass; none expanded scope beyond what Task 2/3's own acceptance criteria already required.

## Issues Encountered
- `tailwindcss`/`@tailwindcss/vite` resolved to `4.3.3` on npm at scaffold time, one patch version below the research document's `4.3.4` — pinned to the actually-available `4.3.3`; no behavioral difference expected at this patch delta, but noted here rather than silently rounding the number to match the research doc.
- Bible source file (`GxP-Sentinel-Project-Bible-v6.md`) is untracked in git and therefore not present in this worktree checkout; page placeholder copy was written from the plan's and research's own transcribed Section 11 summaries (route names, page purposes) rather than a direct Bible read. The banner string itself was reproduced exactly from the plan's verbatim quote (plan lines 220-238), which is character-identical to the Bible's own line 1374 per the plan author's transcription.
- Could not drive an actual browser for a human-eyes visual check of the eight routes (no browser automation tool available in this execution context); substituted (a) the full jsdom render assertion suite for structural/content correctness, and (b) a direct curl against the running `npm run dev` server's compiled `/src/index.css` output to confirm Tailwind v4 is genuinely generating utility CSS (not silently inert) rather than just trusting a successful build. Flagged as D2/D4 in the coverage block for a human spot-check.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `frontend/src/pages/Copilot.tsx` is ready for plan 02-07 to attach the WebSocket client.
- `frontend/src/routes.tsx`'s comment marks exactly where Phase 4 (SENT-3-04) appends the `/blast-radius` route.
- `npm run build`, `npm test` (`vitest run`), and `npm run dev` (port 3000, `strictPort`) are all green and ready for plan 02-08's CI wiring (`npm ci && npm run build && npm test`).
- No file outside `frontend/` was touched; `docker-compose.yml`, `.env.example`, root `README.md`, and `BRANCHING.md` are unmodified, per BRANCHING.md §5.

## Self-Check: PASSED

---
*Phase: 02-foundation*
*Completed: 2026-08-20*
