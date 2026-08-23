# Phase 5: Safety & Remediation - Pattern Map

**Mapped:** 2026-08-23
**Files analyzed:** 15 (backend: 7 new modules/routes, 1 extended; frontend: 4 new/extended components, 1 extended lib, 1 extended shell)
**Analogs found:** 15 / 15

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|-----------------|---------------|
| `backend/app/agents/c2_gateway.py` | middleware/gateway (deterministic) | request-response (fail-closed decision) | `backend/app/agents/c1_verifier.py` | exact (frozen-allowlist + deterministic-fn shape) |
| `backend/app/agents/c3_gateway.py` | middleware/gateway (deterministic) | request-response (category routing) | `backend/app/agents/c1_verifier.py` (RULE_EVIDENCE_TABLES pattern) + `backend/app/graph/evidence_graph.py` (NODE_SPECS allowlist) | role-match |
| `backend/app/agents/a7_remediation.py` | service (LLM synthesis) | transform (verified findings -> ActionProposal) | `backend/app/agents/a2_compliance.py` (narrate_gap/model call shape) — see note below | role-match |
| `backend/app/audit_trail.py` | service/utility (hash chain) | CRUD (append-only) + transactional | `backend/app/db.py` (pool/degrade-don't-raise convention) + Bible §7.1 `AuditLogger` (verbatim source) | role-match (no existing hash-chain analog in repo; Bible is primary source) |
| `backend/app/identity.py` | middleware (FastAPI dependency) | request-response | `backend/app/db.py` (module-level constant, degrade pattern) — new shape, no direct analog | partial |
| `backend/app/routes/actions.py` | route (controller) | request-response, CRUD | `backend/app/routes/findings.py` (assemble-from-already-computed-objects) + `backend/app/routes/evidence_graph.py` (pool/404/503 pattern) | exact |
| `backend/app/routes/audit.py` | route (controller) | request-response | `backend/app/routes/evidence_graph.py` | exact |
| `backend/app/ws/copilot.py` (extended) | provider (WS broadcast) | event-driven, pub-sub | itself (existing file, extend in place) | exact |
| `backend/app/graph/state.py` (extended: C2/A7/C3 stub -> real) | orchestration wiring | event-driven | existing `compliance_a2`/`evidence_verifier_c1` node delegation pattern in same file | exact |
| `backend/app/main.py` (extended: router registration) | config | — | itself (existing file, extend in place) | exact |
| `frontend/src/pages/Actions.tsx` (extended: stub -> real) | component (page) | CRUD (fetch queue) + streaming (WS) | `frontend/src/pages/FindingInvestigation.tsx` (fetch/loading/error state machine) + `frontend/src/pages/BlastRadius.tsx` (WS/panel wiring pattern) | exact |
| `frontend/src/components/ActionProposalCard.tsx` (new) | component | request-response (props-only render) | `frontend/src/components/AssuranceCard.tsx` | exact |
| `frontend/src/components/RoleSelector.tsx` (new) | component | client-state only | `frontend/src/components/NavBar.tsx` (pill styling) | role-match |
| `frontend/src/lib/api.ts` (extended) | utility (API client) | request-response | itself (existing file, extend in place) | exact |
| `frontend/src/lib/ws.ts` (extended: discriminated union + proposal frame) | utility (WS client) | streaming | itself (existing file, extend in place) | exact |

## Pattern Assignments

### `backend/app/agents/c2_gateway.py` (gateway, request-response)

**Analog:** `backend/app/agents/c1_verifier.py`

**Module docstring / determinism discipline** (lines 1-33 of c1_verifier.py):
```python
"""
C1 - Evidence & Grounding Verifier ...
This module must never contain a model call — that constraint is
permanent, not a stub-stage convenience (Bible Section 1.3, ...).
Table and column names used to build SQL statements come exclusively from
the frozen allowlists below ... never from request data ...
"""
```
Copy this exact discipline for C2: module docstring states "this module must never contain a model call — permanent constraint (Bible §1.3)", cite SAFE-01/SAFE-02.

**Frozen-allowlist pattern** (c1_verifier.py lines 76-129, `RULE_EVIDENCE_TABLES` / `RULE_OPA_INPUT`):
```python
RULE_EVIDENCE_TABLES: Dict[str, str] = {
    "ANNEX11-S4-DOC-001": "documents",
    ...
}
```
C2 must define `PERMISSION_MATRIX: Dict[str, FrozenSet[str]]` and `JAILBREAK_PATTERNS: Tuple[re.Pattern, ...]` as the single module-level frozen source of truth — exact same shape as `RULE_EVIDENCE_TABLES`. RESEARCH.md Pattern 1/Pattern 2 already gives the literal content (transcribe verbatim from Bible §2, do not re-derive).

**Fail-closed deterministic function shape** (c1_verifier.py lines 51-70, `calculate_confidence`):
```python
def calculate_confidence(finding: dict, db_record: dict, opa_evaluation: bool) -> str:
    """Transcribed from Bible Section 2 with ... nothing else changed."""
    score = 100
    if not db_record:
        return "INSUFFICIENT_EVIDENCE"
    ...
```
`check_rbac(role, agent_id)` and `detect_injection(text)` must follow the same "docstring cites Bible section, pure function, no I/O" shape. `check_rbac` must default fail-closed on unrecognized role (`PERMISSION_MATRIX.get(role, frozenset())`), matching this function's `if not db_record: return "INSUFFICIENT_EVIDENCE"` fail-safe idiom.

**Degrade-don't-raise entry point convention** (from `db.py` lines 106-125, `acquire_pool_or_none`):
```python
async def acquire_pool_or_none() -> Optional[asyncpg.Pool]:
    """The entry point every agent uses: never raises. ..."""
    try:
        return await get_pool()
    except (OSError, asyncpg.PostgresError, asyncio.TimeoutError) as e:
        logger.warning(...)
        return None
```
C2 has no I/O so this doesn't apply directly to check_rbac/detect_injection, but any route that calls C2 and needs to log a block via `audit_trail.log_event()` must wrap that call the same degrade-don't-raise way `routes/evidence_graph.py` wraps `acquire_pool_or_none()` (see routes pattern below).

---

### `backend/app/agents/c3_gateway.py` (gateway, request-response)

**Analog:** `backend/app/agents/c1_verifier.py`'s frozen-allowlist shape + `backend/app/graph/evidence_graph.py`'s `NODE_SPECS`-style derived-not-stored convention (referenced in RESEARCH.md; not re-read this pass — cite by name only, pattern already fully specified in RESEARCH.md Pitfall 4 recommendation: "category derivable from action_type via a frozen mapping, so storing it would violate the cache-never-holds-a-fact-not-derivable-from-domain-state principle").

**Core pattern:** `route_action(proposal: ActionProposal) -> str` returning one of `READ`/`DRAFT`/`MOCK_WRITE_LOW_RISK`/`GXP_RELEVANT_WRITE`/`PROHIBITED`, driven by a frozen `Dict[str, str]` keyed on `action_type` (same shape as `RULE_EVIDENCE_TABLES`). No branching logic beyond a dict lookup, mirroring `c1_verifier.RULE_EVIDENCE_TABLES.get(citations[0])` returning `None`/unrecognized -> safest default (here: `PROHIBITED`, fail-closed, not `READ`).

**Insert-pending pattern** (mirrors `routes/evidence_graph.py`'s `_system_exists` pool-based existence check plus `c1_verifier.py`'s `_select_one_by_id_query` string-concat-not-fstring discipline): any `INSERT INTO action_proposals` must use `$N` placeholders exclusively; table/column names never come from `proposal.action_type` directly interpolated.

---

### `backend/app/agents/a7_remediation.py` (service, LLM synthesis)

**Analog:** `backend/app/agents/a2_compliance.py` referenced via `routes/findings.py`'s import (`from app.agents.a2_compliance import A2_CHECKS, build_finding, narrate_gap` — see `routes/findings.py` line 27) — the codebase's one existing "call an LLM to narrate a deterministic result" pattern. `a2_compliance.py` itself was not re-read this pass (budget); its call site is fully visible via `routes/findings.py`:

```python
# backend/app/routes/findings.py lines 92-98
for check_fn in A2_CHECKS:
    check_result = await check_fn(pool, system_id)
    if check_result["passed"]:
        continue
    claim, model_id = await narrate_gap(check_result)
    finding = build_finding(check_result, claim, model_id)
    verification_result = await verify_finding(pool, finding)
    cards.append(_assemble_card(check_result, finding, verification_result))
```
A7 must follow the same "narrate via LLM, then build a typed object, model_id always carried" shape: `synthesize_capa(verified_finding: dict) -> Tuple[ActionProposal, str]` where the second element is `model_id` (Bible: "every response carries the actual model_id used"). Per CONTEXT.md D-03/REM-01, A7 must filter to only `verification_result["confidence"] in {"HIGH","MEDIUM","LOW"}` (i.e. NOT `INSUFFICIENT_EVIDENCE`) findings — mirrors `c1_verifier.verify_finding`'s own confidence field as the single source of truth, never re-verified.

**Anti-pattern guard (explicit, from RESEARCH.md):** A7 must never call `c1_verifier.verify_finding` or `calculate_confidence` itself — only read `state["verification_results"]` / the already-computed dict, exactly as `routes/findings.py`'s `_assemble_card` reads `verification_result["confidence"]` and explicitly warns against reading the adjacent-but-wrong `finding["confidence_score"]` field (see `routes/findings.py` lines 44-51 docstring) — same class of adjacent-field trap applies to A7 consuming C1 output.

---

### `backend/app/audit_trail.py` (hash-chain service)

**Analog:** Bible §7.1 `AuditLogger` (verbatim, quoted in full in RESEARCH.md Code Examples) is the primary source — no existing repo module performs multi-statement transactional Postgres work with `LOCK TABLE`. Structural conventions to borrow from `backend/app/db.py`:

**Pool-acquisition + docstring discipline** (db.py lines 1-23, module docstring pattern):
```python
"""
Async Postgres connectivity for AegisX AI (Phase 3, D-01).
...
House style mirrors `backend/app/opa_client.py`: a module-level
env-var-backed constant read at call time ..., `logging.getLogger(__name__)`
rather than `print`, and degrade-don't-raise on the caller-facing entry point.
"""
```
`audit_trail.py` should open with the same "Source: Bible §7.1, ticket, requirement" docstring header format used by every other module in this codebase (`c1_verifier.py`, `db.py`, `evidence_graph.py` route file all follow it).

**Hash-chain algorithm** — transcribe Bible §7.1 verbatim (already reproduced in RESEARCH.md Code Examples, `log_event`/`verify_chain`/`demonstrate_tamper`), with the JSONB-canonicalization fix from `routes/evidence_graph.py` lines 82-84:
```python
properties = row["properties"]
if isinstance(properties, str):
    properties = json.loads(properties)
```
Apply the identical `isinstance(value, str): json.loads(value)` normalization to `evidence_ids`/`opa_rule_ids` on both the `log_event` write side and the `verify_chain` read side (RESEARCH.md Pitfall 2 — this is the load-bearing fix, not optional).

**Transaction shape** (from RESEARCH.md, Bible-sourced, use as-is):
```python
async with pool.acquire() as conn:
    async with conn.transaction():
        await conn.execute("LOCK TABLE audit_events IN EXCLUSIVE MODE")
        prev_row = await conn.fetchrow(
            "SELECT event_hash FROM audit_events ORDER BY timestamp_utc DESC LIMIT 1"
        )
```

---

### `backend/app/identity.py` (FastAPI dependency)

**Analog:** No direct analog exists in-repo (RESEARCH.md Open Question 1 flags this as a new shape). Follow `db.py`'s module-level-constant-read-at-call-time convention for anything configurable, and FastAPI's own `Depends()` idiom. Recommended per RESEARCH.md: custom headers (`X-User-Id`/`X-User-Role`) resolved via a `Depends()`-based function, never trusted without re-derivation on every write-capable route (Security Domain table: "Server independently re-derives user_id/role from the request on every write-capable route").

---

### `backend/app/routes/actions.py` (route/controller)

**Analog:** `backend/app/routes/findings.py` (assembly-from-already-computed-objects) + `backend/app/routes/evidence_graph.py` (pool/404/503 pattern).

**Pool + 503 + 404 pattern** (evidence_graph.py lines 40-49):
```python
@router.post("/api/systems/{system_id}/evidence-graph/rebuild", response_model=EvidenceGraphRebuildResponse)
async def rebuild_evidence_graph(system_id: str):
    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")
    if not await _system_exists(pool, system_id):
        raise HTTPException(status_code=404, detail=f"Unknown system_id: {system_id}")
```
Every new route in `actions.py` (`generate-capa`, `approve`, `reject`, `GET /api/actions`) must open with this exact three-line pool/503 guard, and add a fourth guard calling `c2_gateway.check_rbac(role, "A7")` -> `HTTPException(403, ...)` before doing any work (RBAC 403 comes before any DB mutation).

**Response-model-only, no LLM-authored field** (findings.py `_assemble_card`, lines 36-69): every field in the route's Pydantic response must be read from an already-computed dict/object (C2/C3/A7 outputs), never string-built in the route handler — same discipline REM-03 requires ("approval dialog reads only server-trusted metadata").

**Router registration** (main.py lines 61-63):
```python
app.include_router(copilot_ws_router)
app.include_router(evidence_graph_router)
app.include_router(findings_router)
```
Add `app.include_router(actions_router)` and `app.include_router(audit_router)`, one line each, plus a docstring note in `main.py`'s module docstring following the existing "Plan 04-03 registers a third router..." convention (lines 27-31).

---

### `backend/app/routes/audit.py` (route/controller)

**Analog:** `backend/app/routes/evidence_graph.py` — identical pool/503 guard shape; `GET /api/audit/verify` calls `audit_trail.verify_chain()` directly and returns its dict; `POST /api/audit/demonstrate-tamper` takes an `event_id` body/query param, calls `audit_trail.demonstrate_tamper(event_id)`, returns the resulting verdict. No RBAC gating needed on `GET /api/audit/verify` per D-04 (read-only), but `demonstrate-tamper` is a write and should still get identity resolved for its own audit trail entry (self-referential — log that the tamper-demo was invoked).

---

### `backend/app/ws/copilot.py` (extend in place)

**Analog:** itself — extend, don't duplicate. Current echo-only shape:
```python
# backend/app/ws/copilot.py lines 40-55
@router.websocket("/api/copilot/stream/{session_id}")
async def copilot_stream(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    await websocket.send_json({"event": "connected", "session_id": session_id})
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"event": "echo", "payload": data})
    except WebSocketDisconnect:
        return
```
Add a module-level `_active_connections: set[WebSocket]` populated in the existing handler (`_active_connections.add(websocket)` after `accept()`, `_active_connections.discard(websocket)` in a `finally`), plus a new `async def broadcast_json(event: dict) -> None` function per RESEARCH.md Pattern 4 (verbatim code given there). Do not create a second `@router.websocket` route — REM-04/UI-02 both require reusing this exact `/api/copilot/stream/{session_id}` channel. Update this module's own docstring "Wire contract" section (currently lines 12-18) to add the third frame shape: `{"event": "action_proposal_created", "proposal": {...}}`.

---

## Shared Patterns

### Docstring header convention (every new backend module)
**Source:** `backend/app/agents/c1_verifier.py` lines 1-33, `backend/app/db.py` lines 1-23, `backend/app/routes/findings.py` lines 1-21
**Apply to:** all 7 new/extended backend files
Every module opens with a docstring stating: Ticket id, Requirement id(s), Source (Bible section cited), and any constraint/decision this module encodes permanently (e.g. "never contains a model call"). This is the established pattern across every Phase 2-4 module — the planner should require it in every new-file action.

### Degrade-don't-raise Postgres access
**Source:** `backend/app/db.py` lines 106-125 (`acquire_pool_or_none`)
**Apply to:** `routes/actions.py`, `routes/audit.py`, `c3_gateway.py`, `a7_remediation.py`, `audit_trail.py` — any function touching Postgres
```python
pool = await acquire_pool_or_none()
if pool is None:
    raise HTTPException(status_code=503, detail="Postgres pool unavailable")
```

### Frozen-allowlist single source of truth
**Source:** `backend/app/agents/c1_verifier.py` lines 76-129 (`RULE_EVIDENCE_TABLES`, `RULE_OPA_INPUT`)
**Apply to:** C2's `PERMISSION_MATRIX`/`JAILBREAK_PATTERNS`, C3's action-category mapping
No table/column name, permission matrix, or regex list may exist as a second copy anywhere else in the codebase — a route or agent that needs it imports it from the one module that owns it.

### SQL placeholder discipline (never f-string)
**Source:** `backend/app/agents/c1_verifier.py` lines 132-155 (`_select_one_by_id_query`, string concatenation not f-string, for code-only interpolation; `$1`-style asyncpg placeholders for all bound values)
**Apply to:** `c3_gateway.py`, `audit_trail.py`, `routes/actions.py` — every SQL statement

### JSONB round-trip normalization
**Source:** `backend/app/routes/evidence_graph.py` lines 82-84
```python
properties = row["properties"]
if isinstance(properties, str):
    properties = json.loads(properties)
```
**Apply to:** `audit_trail.py`'s `log_event`/`verify_chain` (RESEARCH.md Pitfall 2 — load-bearing, chain will falsely report TAMPERED without this)

### Frontend: props-only, no-fetch, no-fallback presentation component
**Source:** `frontend/src/components/AssuranceCard.tsx` lines 1-11, `frontend/src/components/BlastRadiusPanel.tsx` lines 1-12
**Apply to:** `frontend/src/components/ActionProposalCard.tsx` (new)
```tsx
// Pure presentation ... this component is a window onto server-trusted state.
// It performs no fetch, no arithmetic, no grading, and holds no fallback that
// would let a missing server field be replaced by a client-invented one.
```
Every value in the new `ActionProposalCard` reads directly from an `ActionProposalData` prop; missing `justification`/`category` render the literal string `"Not provided"` per UI-SPEC's `partial` state row — never blank, never fabricated.

### Frontend: status-badge color-map pattern
**Source:** `frontend/src/components/AssuranceCard.tsx` lines 13-25 (`CONFIDENCE_STYLES`/`CONFIDENCE_BADGE_STYLES`)
**Apply to:** `ActionProposalCard.tsx`'s status badges (`PENDING_APPROVAL`/`APPROVED`/`EXECUTED`/`REJECTED`/`BLOCKED`) — reuse the exact `Record<string, string>` two-map shape (border/bg map + badge-fill map), with the five hue/status pairs UI-SPEC's Color section already specifies verbatim.

### Frontend: loading/error/empty page state machine
**Source:** `frontend/src/pages/FindingInvestigation.tsx` lines 15-24, 34-51 (`LoadState` union, `useEffect` fetch-with-cancelled-guard)
```tsx
type LoadState = 'loading' | 'error' | 'ready'
...
useEffect(() => {
  let cancelled = false
  fetchX(...).then((response) => { if (cancelled) return; ... setState('ready') })
    .catch(() => { if (cancelled) return; setState('error') })
  return () => { cancelled = true }
}, [dep])
```
**Apply to:** `Actions.tsx`'s pending-queue fetch (`GET /api/actions`) — identical cancelled-guard shape prevents a stale response overwriting newer state on rapid role/system switches.

### Frontend: REST client module conventions
**Source:** `frontend/src/lib/api.ts` lines 1-32 (module docstring, `resolveApiBase`, `apiGet<T>`)
**Apply to:** extend `api.ts` with `ActionProposalData`/`ActionProposalsResponse` interfaces mirroring backend Pydantic field-for-field (per its own existing precedent comment: "mirroring backend/app/schemas.py's ... field for field"), plus `apiPost<T>` (does not exist yet — needed for approve/reject/generate-capa) added alongside `apiGet<T>` in the same file, carrying the `X-User-Id`/`X-User-Role` headers per RESEARCH.md Open Question 1's recommendation.

### Frontend: WS discriminated-union frame contract
**Source:** `frontend/src/lib/ws.ts` lines 15-25
```tsx
export interface ConnectedFrame { event: 'connected'; session_id: string }
export interface EchoFrame { event: 'echo'; payload: string }
export type CopilotStreamFrame = ConnectedFrame | EchoFrame
```
**Apply to:** add `ActionProposalCreatedFrame { event: 'action_proposal_created'; proposal: ActionProposalData }` to the union — this file's own docstring (lines 8-12) explicitly anticipates this exact Phase 5 addition.

### Frontend: nav-pill styling reuse for Role Selector
**Source:** `frontend/src/components/NavBar.tsx` lines 6-18 (`rounded px-3 py-1.5 text-sm font-medium` pill classes)
**Apply to:** new `RoleSelector.tsx`, placed in `AppShell` (frontend/src/App.tsx lines 17-32) adjacent to `<NavBar />`, per UI-SPEC's Interaction Notes — matches the exact `rounded px-3 py-1.5 text-sm font-medium` pill family so it reads as the same chrome, not a new control language.

## No Analog Found

None — every file has at least a role-match analog. `backend/app/audit_trail.py` and `backend/app/identity.py` have no *structural* precedent in-repo (no prior hash-chain or identity-dependency module existed), but both have a fully-specified source (Bible §7.1 verbatim; RESEARCH.md Open Question 1 recommendation respectively) plus the shared conventions (docstring header, degrade-don't-raise, `$N` placeholders) that every other module already establishes — flagged as role-match rather than "no analog."

## Metadata

**Analog search scope:** `backend/app/agents/`, `backend/app/routes/`, `backend/app/{db,main}.py`, `backend/app/ws/copilot.py`, `backend/app/schemas.py`, `frontend/src/{components,pages,lib}/`
**Files scanned:** 11 backend + 8 frontend (read in full or targeted excerpt this session)
**Pattern extraction date:** 2026-08-23
