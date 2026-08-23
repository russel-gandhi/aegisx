# Phase 5: Safety & Remediation - Research

**Researched:** 2026-08-23
**Domain:** Deterministic safety gateways (RBAC + prompt-injection detection), controlled-write action routing, human-approval workflow over WebSocket, hash-chained tamper-evident audit trail
**Confidence:** MEDIUM — the Bible fully specifies data shapes and the two Critical algorithms (`calculate_confidence`-style determinism, hash-chain), but leaves two concrete implementation details unspecified (entropy threshold, exact `/api/copilot/query` wiring point), which are called out below and logged in the Assumptions table.

## Summary

Phase 5 builds three deterministic gateways and one generative agent, all sitting on a codebase that already has a real, tested substrate: a compiled LangGraph topology with C2/A7/C3 as literal (currently stub) nodes, a real Postgres pool helper (`acquire_pool_or_none()`), a real OPA client, a real multi-provider LLM router (with a `"remediation"` task already wired to `gemini_flash_thinking`), and two established route-module examples (`routes/evidence_graph.py`, `routes/findings.py`) that call agent functions directly rather than through the compiled graph. The four Stage-4 deliverables (C2 RBAC, C2 injection detection, C3 category routing + approval queue, hash-chained audit trail) should each become a new deterministic Python module under `app/agents/` (mirroring `c1_verifier.py`'s naming and its allowlist-not-f-string / frozen-constant conventions), wired into the graph's existing stub nodes in `app/graph/state.py`, and separately exposed as reusable functions for the new write-capable routes this phase adds.

The single most important scope-boundary finding: the Bible's Section 12 `POST /api/copilot/query` endpoint — the one that would carry a raw, untrusted user prompt into C2 for injection scanning — is **not built this phase**. Per ROADMAP.md, the "Ask GxP Copilot" chat page is Phase 6 (SENT-5-02). CONTEXT.md's own D-04 already names it "the *future* `/api/copilot/query`". This means SAFE-01/SAFE-02 must be proven this phase via direct unit tests against the C2 functions and via wiring the real `safety_gateway_c2` graph node (replacing today's "admit everything" stub), **not** via an end-to-end HTTP round trip through a query endpoint that does not exist yet. The write-capable endpoints that *do* get built this phase — action-approval, action-execution, and the A7 "Generate CAPA" trigger — are where C2's RBAC check has a real HTTP surface to gate today.

The second most important finding: the real, already-migrated `action_proposals` table (`infra/postgres/initdb/001_schema.sql:174-180`) has only `id, action_type, target_system, payload, status` — no `justification`, `category`, `created_at`, `approved_by`, or `approved_at` columns, even though `app/schemas.py`'s `ActionProposal` Pydantic model already declares `justification`, and REM-03/REM-04 need ordering and approval provenance. Phase 4 already established the fix pattern for exactly this class of gap (`infra/postgres/initdb/002_change_affects.sql`, an additive `IF NOT EXISTS` migration file, applied via `infra/apply-migrations.sh`) — this phase's plan should decide, as an explicit `checkpoint:decision`, whether to add a similar `003_action_proposal_columns.sql` migration or pack the extra fields into the existing `payload JSONB` column.

**Primary recommendation:** Build C2 (`app/agents/c2_gateway.py`), C3 (`app/agents/c3_gateway.py`), A7 (`app/agents/a7_remediation.py`), and the hash-chain (`app/audit_trail.py`) as four new deterministic-or-generative modules following the exact allowlist/frozen-constant/degrade-don't-raise conventions `c1_verifier.py`, `evidence_graph.py`, and `db.py` already establish; wire C2/A7/C3 into their existing `app/graph/state.py` stub nodes; add a new `app/routes/actions.py` and `app/routes/audit.py` for the write-capable HTTP surface; and extend the existing `app/ws/copilot.py` module with a connection-registry + broadcast helper rather than building a second WebSocket route.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| RBAC permission check (role → allowed agents) | API / Backend (deterministic Python) | — | Bible Section 1.3: forbids an LLM from ever making an RBAC decision; C2 is a fixed-topology graph node, not a model call |
| Prompt-injection detection (entropy + regex) | API / Backend (deterministic Python) | — | Same constraint — "Bypasses LLM interpretation entirely" (Bible §2, C2) |
| Action category routing (READ/DRAFT/MOCK_WRITE_LOW_RISK/GXP_RELEVANT_WRITE/PROHIBITED) | API / Backend (deterministic Python) | Database (`action_proposals` status) | C3 is a fixed-topology decision node (Bible §1.3); persisted status is the durable record of the decision |
| CAPA / ActionProposal narrative synthesis | API / Backend (LLM via `llm_router`) | — | Bible §2 A7: "Purely generative based on upstream verified data" — the one node in this phase permitted to call a model, and only after C1 has already verified its inputs |
| Human approval decision | Browser / Client (user action) → API / Backend (persists) | — | The approval itself is a human act; the backend only records and executes it |
| WebSocket push of pending proposals | API / Backend (produces frames) | Browser / Client (consumes) | Reuses the existing `/api/copilot/stream/{session_id}` transport (`app/ws/copilot.py`) already registered in `main.py` |
| Hash-chain append + verify | Database / Storage (Postgres `audit_events` + `LOCK TABLE`) | API / Backend (Python hashing logic) | 21 CFR 11.10(e); must be transactionally serialized against concurrent appends — belongs at the DB-transaction boundary, not purely in-process |
| Identity (`user_id`/`role`) carrier | API / Backend (dependency/middleware reading request) | Browser / Client (role-selector UI state) | D-01: no real auth exists; the selector is client-side state, but every write-capable route must independently re-derive identity server-side for RBAC/audit — never trust a client-asserted role without a request-level check |

## Package Legitimacy Audit

No new external packages are required for this phase. Every capability is buildable from packages already pinned in `backend/requirements.txt`:

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `fastapi==0.141.1` | pypi | already pinned | already pinned | github.com/fastapi/fastapi | OK | Already installed — WebSocket + `TestClient.websocket_connect` support confirmed via official docs `[CITED: fastapi.tiangolo.com/advanced/testing-websockets/]` |
| `asyncpg==0.31.0` | pypi | already pinned | already pinned | github.com/MagicStack/asyncpg | OK | Already installed — used for `LOCK TABLE ... IN EXCLUSIVE MODE` transactional hash-chain append |
| `hashlib` (stdlib) | — | — | — | — | OK | No install needed — `hashlib.sha256` is the Bible's own literal algorithm (§7.1) |
| `math` (stdlib, `math.log2`) | — | — | — | — | OK | No install needed — Shannon entropy needs only `math.log2` over a character-frequency histogram |
| `re` (stdlib) | — | — | — | — | OK | No install needed — jailbreak-phrase regex matching |

**Packages removed due to `[SLOP]` verdict:** none.
**Packages flagged as suspicious `[SUS]`:** none.

Do not add a dedicated "entropy" or "prompt-injection" PyPI package — the Bible's own architecture requires the logic to be inline, auditable, deterministic Python (Bible §1.3, §2), not a third-party black box; pulling in an unaudited classifier library here would violate the same "never trust a generated regulatory claim" discipline this phase exists to enforce, and CLAUDE.md Rule 7 (no silent scope expansion).

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fastapi` | 0.141.1 (pinned, unchanged) | New `routes/actions.py`, `routes/audit.py`; WebSocket broadcast extension | Already the app's only web framework; `TestClient.websocket_connect` is the project's established WS-testing pattern (`tests/test_ws_echo.py`) |
| `asyncpg` | 0.31.0 (pinned, unchanged) | Hash-chain transaction (`LOCK TABLE`, `INSERT`), action-proposal CRUD | Already the app's only DB driver; every write in this phase must go through `acquire_pool_or_none()` per `db.py`'s degrade-don't-raise contract |
| `hashlib` | stdlib | SHA-256 event/prev-hash chaining | Bible §7.1's literal algorithm; no dependency to add |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `math` | stdlib | Shannon entropy: `-sum(p * math.log2(p) for p in freqs)` | C2's injection-detection entropy leg |
| `re` | stdlib, compiled once at module import into a frozen tuple | Jailbreak-phrase regex matching | C2's injection-detection regex leg |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled `ConnectionManager` in `app/ws/copilot.py` | Redis pub/sub fan-out across workers | Redis pub/sub is the correct answer only when running >1 uvicorn worker process; this is a single-process hackathon demo (`uvicorn` default single worker) — adding Redis here would be unjustified infra for a problem the deployment doesn't have `[CITED: websocket.org/guides/frameworks/fastapi/, betterstack.com/community/guides/scaling-python/fastapi-websockets/]` |
| Inline entropy+regex in `c2_gateway.py` | A third-party prompt-injection detection package (`prompt-armor`, etc.) | Third-party classifiers are typically ML-based or maintain their own non-auditable phrase lists — violates Bible §1.3's "Bypasses LLM interpretation entirely" determinism requirement and Rule 13 (never trust a generated regulatory claim); the Bible gives the exact regex to transcribe, which is the auditable, correct choice `[CITED: github.com/prompt-armor/prompt-armor - reference only, not adopted]` |
| Additive migration for `action_proposals` columns | Pack `justification`/`category`/timestamps into existing `payload JSONB` | Migration is more explicit/queryable and matches the Phase-4 precedent (`002_change_affects.sql`); JSONB-packing is zero-migration but makes `SELECT ... ORDER BY created_at` impossible without a JSONB expression index. See `<code_context>` note below — flagged as a `checkpoint:decision` for the planner. |

**Installation:** None — no new packages required (`pip install -r backend/requirements.txt` is already sufficient).

**Version verification:** All three touched packages (`fastapi`, `asyncpg`, plus stdlib) are already pinned and installed in this repo; no registry lookup needed this phase — verified by reading `backend/requirements.txt` directly (`[VERIFIED: backend/requirements.txt:1-11]`, quoted below):

```
fastapi==0.141.1
pydantic==2.13.4
uvicorn[standard]==0.52.4
httpx==0.28.1
langgraph==1.2.11
langchain-core==1.6.0
pytest==9.1.1
asyncpg==0.31.0
respx==0.23.1
python-dotenv==1.1.1
networkx==3.6.1
```

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SAFE-01 | C2 enforces RBAC exactly per Bible permission matrix, zero LLM in decision path | Permission matrix transcribed verbatim below (Bible §2, C2); frozen-dict pattern from `c1_verifier.RULE_EVIDENCE_TABLES`; RBAC-gated route set scoped by CONTEXT.md D-04 |
| SAFE-02 | C2 detects prompt injection via entropy + regex, zero LLM in decision path | Bible's literal example regex transcribed below; Shannon-entropy formula + threshold-tuning guidance in Common Pitfalls; must run before A0 (already true — C2 precedes A0 in the compiled graph) |
| AUDIT-01 | Hash-chained append-only audit trail records finding/verification/approval events | Bible §7.1 `AuditLogger.log_event` transcribed verbatim below; real `audit_events` schema confirmed identical to Bible (`infra/postgres/initdb/001_schema.sql:183-202`) |
| AUDIT-02 | `verify_chain()` implemented alongside the chain, detects tampering | Bible §7.1 `verify_chain` transcribed verbatim; JSONB-canonicalization pitfall documented (Common Pitfalls #2) |
| AUDIT-03 | `/api/audit/demonstrate-tamper` executes raw SQL, `verify_chain()` flags it | Bible §12 API table + §7.1 `demonstrate_tamper`; deterministic-test gotchas documented in Common Pitfalls #3 |
| REM-01 | A7 synthesizes ActionProposal/CAPA from already-verified findings only | Bible §2 A7 + §6 A7 prompt transcribed below; `llm_router`'s `"remediation"` task already routes to `gemini_flash_thinking` (thinking ON) — confirmed by reading `llm_router.py:53-63` |
| REM-02 | C3 routes actions by category | Bible §2 C3 categories transcribed below; frozen-allowlist routing pattern recommended, mirroring `evidence_graph.NODE_SPECS` |
| REM-03 | GxP-relevant writes sit PENDING until human approval; dialog reads only server-trusted metadata | D-02's fixed flow; existing `routes/findings.py` pattern (server assembles response from already-computed Pydantic models, never LLM prose in structured fields) is the template |
| REM-04 | Full loop: proposal → WS push → approve → audit-logged → executed | WS broadcast pattern researched below; `test_ws_echo.py` is the literal test-pattern template to extend |
| UI-02 | `/api/copilot/stream/{session_id}` streams live agent state end-to-end | Already accepts connections (`app/ws/copilot.py`); this phase's job is adding the proposal-push frame type, not building a new socket |
</phase_requirements>

## Architecture Patterns

### System Architecture Diagram

```
                                    ┌─────────────────────────────┐
                                    │  Role selector (client state)│
                                    │  -> X-User-Id / X-User-Role  │
                                    └──────────────┬───────────────┘
                                                    │ every write-capable request
                                                    ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │  Write-capable HTTP routes (routes/actions.py, new this phase)           │
 │    POST /api/systems/{id}/findings/{finding_id}/generate-capa  (A7 trig) │
 │    POST /api/actions/{proposal_id}/approve                               │
 │    GET  /api/actions                          (hydrate approval queue)  │
 └───────────────────┬────────────────────────────────────────┬────────────┘
                      │ identity + payload                     │
                      ▼                                        │
        ┌───────────────────────────┐                          │
        │ C2 Gateway (app/agents/    │  role not permitted /    │
        │ c2_gateway.py)             │  injection detected      │
        │  - check_rbac(role, "A7") │─────────────► HTTP 403 +  │
        │  - detect_injection(text) │               audit_trail.log_event(
        └──────────────┬────────────┘                action_type="BLOCKED_*")
                        │ permitted
                        ▼
        ┌───────────────────────────┐
        │ A7 Remediation             │   only reads C1-verified
        │ (app/agents/a7_remediation │   findings — never re-runs
        │ .py) — LLM call, task=     │   verification itself
        │ "remediation"              │
        └──────────────┬────────────┘
                        │ ActionProposal (draft)
                        ▼
        ┌───────────────────────────┐
        │ C3 Action Gateway           │  category = READ/DRAFT/
        │ (app/agents/c3_gateway.py) │  MOCK_WRITE_LOW_RISK/
        │  route_action(proposal)    │  GXP_RELEVANT_WRITE/
        └──────────────┬────────────┘  PROHIBITED
                        │
          ┌─────────────┼───────────────────┐
          ▼             ▼                   ▼
    PROHIBITED    MOCK_WRITE_LOW_RISK   GXP_RELEVANT_WRITE
   (blocked,      or                    (blocked pending human
    audit-logged,  GXP_RELEVANT_WRITE    out-of-band execution)
    no queue row)  → INSERT action_proposals
                     (status=PENDING_APPROVAL)
                        │
                        ▼
        ┌───────────────────────────┐
        │ WS broadcast (extends      │──► every connected
        │ app/ws/copilot.py)         │    /api/copilot/stream/*
        │  broadcast_json({"event":  │    client (Approval Centre
        │  "action_proposal_created" │    UI + any other open tab)
        │  , "proposal": {...}})     │
        └───────────────────────────┘
                        │  (human clicks Approve in UI)
                        ▼
        ┌───────────────────────────┐
        │ POST /api/actions/{id}/    │
        │ approve  → C2 RBAC check  │
        │ (role must have A7)  →    │
        │ UPDATE status=APPROVED →  │
        │ "execute" (mock) →         │
        │ audit_trail.log_event(...) │
        └──────────────┬────────────┘
                        ▼
        ┌───────────────────────────┐
        │ Hash chain (app/           │  GET /api/audit/verify
        │ audit_trail.py)            │◄─────────────────────────
        │  log_event() under         │  POST /api/audit/
        │  LOCK TABLE audit_events   │  demonstrate-tamper
        │  IN EXCLUSIVE MODE         │  (raw SQL UPDATE, then
        │  verify_chain()            │  re-verify_chain())
        └───────────────────────────┘
```

### Recommended Project Structure
```
backend/app/
├── agents/
│   ├── c2_gateway.py       # NEW — RBAC + injection detection (SAFE-01/02)
│   ├── c3_gateway.py       # NEW — action category routing (REM-02)
│   ├── a7_remediation.py   # NEW — CAPA/ActionProposal synthesis (REM-01)
│   └── c1_verifier.py      # EXISTING — read-only input to A7; not modified
├── audit_trail.py          # NEW, top-level like db.py/opa_client.py/llm_router.py — hash chain (AUDIT-01/02/03)
├── identity.py             # NEW — FastAPI dependency resolving user_id/role from request (D-01 discretion)
├── routes/
│   ├── actions.py          # NEW — generate-capa, approve, list-pending routes
│   ├── audit.py            # NEW — /api/audit/verify, /api/audit/demonstrate-tamper
│   ├── evidence_graph.py   # EXISTING — unmodified per D-04 (no C2 gating added)
│   └── findings.py         # EXISTING — unmodified per D-04
├── ws/
│   └── copilot.py          # EXTENDED — add connection registry + broadcast_json()
└── graph/
    └── state.py            # EXTENDED — safety_gateway_c2/remediation_a7/action_gateway_c3
                             # stubs replaced with delegating calls, mirroring the
                             # existing compliance_a2/evidence_verifier_c1 pattern
```

### Pattern 1: Frozen-allowlist RBAC matrix (mirrors `c1_verifier.RULE_EVIDENCE_TABLES`)
**What:** A module-level, immutable `Dict[str, FrozenSet[str]]` mapping role name to the set of agent ids that role may invoke — never a database-driven config, matching this codebase's established "the only source of truth reaching a decision" convention.
**When to use:** Every RBAC check in C2, and the A7-trigger / action-approve routes' own permission check (both gate on `"A7" in PERMISSION_MATRIX[role]`).
**Example:**
```python
# Source: AegisX-AI-Project-Bible-v6.md Section 2, C2 "Permission Matrix"
# (transcribed verbatim — see <canonical_refs> below)
PERMISSION_MATRIX: Dict[str, FrozenSet[str]] = {
    "IT System Manager": frozenset({"A1", "A2", "A3", "A4", "A5", "A6", "A7"}),
    "QA/Compliance": frozenset({"A1", "A2", "A3", "A4", "A5", "A6"}),
    "Auditor": frozenset({"A1", "A2"}),
}

def check_rbac(role: str, agent_id: str) -> bool:
    """Returns False for an unrecognised role too — fail closed, never
    fail open on a typo'd or missing role string."""
    return agent_id in PERMISSION_MATRIX.get(role, frozenset())
```

### Pattern 2: Deterministic entropy + regex injection detection
**What:** Two independent, composable checks — a frozen tuple of compiled jailbreak-phrase regexes (Bible's literal example), and a Shannon-entropy check over the message (or per-token, see Pitfall 1) to catch obfuscated/encoded payloads that evade plain-text regex.
**When to use:** Before any LLM ever sees a user-supplied prompt string — this must run in front of A0, matching the graph's existing `C2 -> A0` edge.
**Example:**
```python
# Source: AegisX-AI-Project-Bible-v6.md Section 2, C2 "Prompt Injection Logic"
# (regex example transcribed verbatim)
import math
import re
from collections import Counter

JAILBREAK_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(r"(?i)(ignore previous instructions|override system prompt|disregard rules)"),
)

def shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    length = len(text)
    return -sum((n / length) * math.log2(n / length) for n in counts.values())

def detect_injection(text: str, entropy_threshold: float = 4.5) -> Optional[str]:
    """Returns a reason string when injection is suspected, else None.
    Regex leg catches known plain-text jailbreak phrasing; entropy leg
    catches high-entropy substrings (base64/hex blobs) used to smuggle
    instructions past the regex. Both legs deterministic Python — no
    LLM call anywhere in this function (Bible Section 1.3)."""
    for pattern in JAILBREAK_PATTERNS:
        if pattern.search(text):
            return f"regex_match:{pattern.pattern}"
    for token in text.split():
        if len(token) >= 12 and shannon_entropy(token) >= entropy_threshold:
            return f"high_entropy_token:{token[:16]}..."
    return None
```

### Pattern 3: Hash-chain append under `LOCK TABLE ... IN EXCLUSIVE MODE`
**What:** Every audit event insert reads the previous row's `event_hash` inside the *same* transaction as an exclusive table lock, so two concurrent appends cannot both read the same `prev_hash` and create a forked chain.
**When to use:** Every call to `audit_trail.log_event()` — approvals, blocked injections, blocked RBAC violations, executed actions.
**Example:**
```python
# Source: AegisX-AI-Project-Bible-v6.md Section 7.1 (transcribed verbatim,
# `datetime.utcnow()` deprecation already fixed elsewhere in this codebase
# per app/schemas.py's own precedent — apply the same fix here)
GENESIS_HASH = "0" * 64  # verified length: matches VARCHAR(64) and a sha256 hexdigest

async def log_event(pool, event_data: dict) -> str:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("LOCK TABLE audit_events IN EXCLUSIVE MODE")
            prev_row = await conn.fetchrow(
                "SELECT event_hash FROM audit_events ORDER BY timestamp_utc DESC LIMIT 1"
            )
            prev_hash = prev_row["event_hash"] if prev_row else GENESIS_HASH
            canonical_data = {
                k: v for k, v in event_data.items()
                if k not in ("event_id", "timestamp_utc", "event_hash", "previous_event_hash")
            }
            canonical_json = json.dumps(canonical_data, sort_keys=True, separators=(",", ":"))
            event_hash = hashlib.sha256(f"{prev_hash}{canonical_json}".encode("utf-8")).hexdigest()
            # ... INSERT with $1..$18 placeholders, per Bible §7.1 ...
            return event_id
```

### Pattern 4: WebSocket broadcast extension (not a second socket)
**What:** A module-level registry of active `WebSocket` connections on the existing `/api/copilot/stream/{session_id}` route, plus a `broadcast_json()` helper that any HTTP route handler can call after a state change. Per-connection send failures are caught and the dead connection pruned, so one stale client never blocks the broadcast to the rest `[CITED: github.com/fastapi/fastapi/discussions/6370, medium.com/@connect.hashblock/10-fastapi-websocket-patterns-for-live-dashboards]`.
**When to use:** After C3 inserts a new `PENDING_APPROVAL` row (REM-04's "proposal → WebSocket push" step).
**Example:**
```python
# Extends app/ws/copilot.py — does not create a second route (CONTEXT.md
# code_context: "reuse, don't build a second WS").
_active_connections: "set[WebSocket]" = set()

@router.websocket("/api/copilot/stream/{session_id}")
async def copilot_stream(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    _active_connections.add(websocket)
    await websocket.send_json({"event": "connected", "session_id": session_id})
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"event": "echo", "payload": data})
    except WebSocketDisconnect:
        return
    finally:
        _active_connections.discard(websocket)

async def broadcast_json(event: dict) -> None:
    dead = set()
    for ws in _active_connections:
        try:
            await ws.send_json(event)
        except Exception:
            dead.add(ws)
    _active_connections.difference_update(dead)
```

### Anti-Patterns to Avoid
- **Gating the existing Phase 4 read routes with C2:** `evidence-graph`, `blast-radius`, `assurance-cards`, and the `evidence-graph/rebuild` POST are explicitly out of scope per CONTEXT.md D-04 — do not add RBAC middleware to already-shipped, already-tested routes; that is a "costly" reversibility decision the user already made.
- **Auto-executing GxP-relevant writes:** D-02 is explicit — there is no auto-approve path anywhere in this phase, even for low-risk categories. Every write-capable action ends in a human click.
- **Re-verifying findings inside A7:** A7 must read `verification_results` (C1's output) as-is and filter on it; it must never re-run `calculate_confidence()` or query Postgres itself for evidence — that would duplicate C1's authority and violate the "already-verified findings only" contract (REM-01).
- **A second Python copy of the injection phrase list or the RBAC matrix:** both must live in exactly one frozen constant each (mirrors `RULE_EVIDENCE_TABLES`'s "single source of truth reaching SQL" precedent) — a second copy drifting from the first is the same failure mode `opa_client.py`'s own docstring warns against for Rego duplication.
- **Building `/api/copilot/query` this phase:** it is Phase 6 scope (Ask GxP Copilot chat page). Prove C2 via direct unit tests + the graph node + the write-capable routes that do exist this phase.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SHA-256 hashing | A custom hash function or HMAC scheme | `hashlib.sha256` (stdlib) | Bible §7.1's literal algorithm; no cryptographic library needed or wanted here |
| WebSocket multi-client fan-out at scale | A custom pub/sub broker | Redis pub/sub *only if* the deployment ever runs multiple uvicorn workers | Out of scope for a single-process hackathon demo — the in-process registry (Pattern 4) is correct at this scale `[CITED: betterstack.com/community/guides/scaling-python/fastapi-websockets/]` |
| Prompt-injection classification | A trained ML classifier or third-party detection package | The Bible's exact regex + Shannon entropy | Determinism is the explicit product thesis (Bible §1.3); an ML classifier reintroduces the exact non-determinism this gateway exists to eliminate |
| Approval-queue ordering | A custom sequencing/versioning scheme | Postgres `created_at TIMESTAMP` column (if migration is chosen) or a sortable, timestamp-embedded id (`AP-{utc-strftime}`, mirroring `audit_events.event_id`'s own `EVT-{strftime}` convention) | `action_proposals` has no ordering column today — reuse the codebase's own existing convention rather than inventing a new one |

**Key insight:** Every deterministic decision node in this phase (C2, C3, hash-chain) has its "hard part" already fully specified by the Bible as literal, transcribable code — the risk in this phase is not algorithmic novelty, it is *fidelity to the Bible's exact literal values* (the regex, the permission matrix, the canonical-JSON hashing recipe) plus *correct integration with the already-migrated schema*, which in two places (entropy threshold, `action_proposals` columns) requires an engineering judgment call the Bible does not make for you.

## Common Pitfalls

### Pitfall 1: Shannon entropy has no Bible-specified threshold or scanning window
**What goes wrong:** Computing entropy over an entire natural-language message and comparing it to a single threshold either misses a short embedded base64/hex payload (diluted by surrounding plain text) or false-positives on legitimate technical jargon/ids.
**Why it happens:** The Bible states only "combining Shannon entropy calculations with regex pattern matching" (§2, C2) — no formula parameters, no threshold, no windowing strategy are given.
**How to avoid:** Scan per-token (whitespace-split) rather than whole-message, and only evaluate tokens above a minimum length (e.g., 12 characters) before computing entropy — a short token can't carry enough information to be a meaningful obfuscation vector, and this avoids false-positiving on ordinary short high-entropy strings (UUIDs, hex hashes already legitimately present in GxP record ids). English prose typically sits well under 4.5 bits/char; base64/hex-encoded payloads approach 6 bits/char (`log2(64)`/`log2(16)`) — a threshold around 4.5 is a reasonable starting point, but **must be tuned against the actual seeded jailbreak test fixtures and confirmed with the user before being presented as a locked value** (this is `[ASSUMED]`, logged in the Assumptions table below).
**Warning signs:** A negative test asserting a benign message (containing a system_id like `GXP-MFG-DEMO-01` or a UUID) is *not* flagged, alongside a positive test asserting a base64-obfuscated jailbreak phrase *is* flagged — write both before tuning the constant.

### Pitfall 2: JSONB round-trip breaks canonical-hash stability
**What goes wrong:** `audit_events.evidence_ids` and `opa_rule_ids` are `JSONB` columns. `asyncpg` returns `JSONB` values as raw JSON **text strings**, not parsed Python objects, unless a custom type codec is registered on the connection (this codebase has not registered one — confirmed by reading `evidence_graph.py`'s own workaround: `properties = row["properties"]; if isinstance(properties, str): properties = json.loads(properties)`, `[VERIFIED: backend/app/routes/evidence_graph.py:82-84]`, quoted verbatim: `"properties = row[\"properties\"]\n        if isinstance(properties, str):\n            properties = json.loads(properties)"`). If `log_event()` builds `canonical_data` from a dict with native Python lists (at insert time) but `verify_chain()` builds it from `dict(row)` where those same fields are still-JSON-text strings (at read-back time), `json.dumps(canonical_data, sort_keys=True, ...)` produces **different bytes** for the identical logical event, and every legitimate row will report `TAMPERED` even though nothing was tampered.
**Why it happens:** The Bible's `verify_chain()` example does `dict(row)` and hashes it directly, silently assuming `asyncpg` already returns parsed objects — it does not, for `JSONB` columns, without an explicit codec.
**How to avoid:** In `verify_chain()`, before building `canonical_data`, run the same `isinstance(value, str): json.loads(value)` normalization on `evidence_ids` and `opa_rule_ids` that `evidence_graph.py` already established as this codebase's pattern for this exact asyncpg behavior — and normalize identically in `log_event()`'s own `canonical_data` build (parse-then-`json.dumps(sort_keys=True)` on both sides, never raw string interpolation on one side only).
**Warning signs:** `verify_chain()` reports `TAMPERED` on the very first row appended by a passing test that made no tamper call — this is the signature of the canonicalization mismatch, not a real chain break.

### Pitfall 3: Deterministic tamper-detection tests need a controlled two-row chain, not the full seed dataset
**What goes wrong:** A test that calls `demonstrate_tamper(event_id)` against whatever rows already exist in `audit_events` (populated by other tests in the same session, or by manual dev-server use) can pick an `event_id` that either doesn't exist (silent no-op `UPDATE`, zero rows affected, chain reports `VERIFIED` — a false negative that looks like a passing test) or belongs to a chain state a *different* test already mutated.
**Why it happens:** `audit_events` starts empty (`infra/postgres/seed/001_seed.sql` deliberately seeds zero rows into it, `[VERIFIED: infra/postgres/seed/001_seed.sql:26-29]`, quoted: `"Every other table (document_chunks, design_elements, ... action_proposals, audit_events) is intentionally left empty"`), so test isolation is entirely the test's own responsibility — there is no seed fixture to reset to.
**How to avoid:** Each tamper-detection test must (1) insert its own known 2-3-row chain via `log_event()` directly (not depend on any other test having run), (2) call `verify_chain()` first and assert `VERIFIED`, (3) call `demonstrate_tamper()` on one of *its own* inserted `event_id`s, (4) assert `TAMPERED` with the expected `broken_at_index`, and (5) clean up (`DELETE FROM audit_events WHERE event_id = ANY($1)`) in a fixture teardown so later tests in the same session see a clean append point. Follow this codebase's existing `reset_db_pool`-style fixture convention (`tests/conftest.py`) rather than relying on database-level transaction rollback (the hash-chain's own `LOCK TABLE`+multi-statement transaction shape makes nesting a rollback-based test transaction around it fragile).
**Warning signs:** A tamper test passes in isolation (`pytest tests/test_audit_trail.py`) but fails when run with the full suite (`pytest`), or vice versa — a strong signal of cross-test `audit_events` state leakage.

### Pitfall 4: `action_proposals` has no `justification`, `category`, or timestamp column today
**What goes wrong:** REM-03 requires the approval dialog to render "the proposed payload, justification, and regulatory citation" (Bible §11.6) from server-trusted metadata, and REM-04 needs ordering for the approval queue — but the real, already-migrated table (`[VERIFIED: infra/postgres/initdb/001_schema.sql:174-180]`, quoted verbatim: `"CREATE TABLE action_proposals (\n    id VARCHAR(50) PRIMARY KEY,\n    action_type VARCHAR(50),\n    target_system VARCHAR(50),\n    payload JSONB,\n    status VARCHAR(50)\n);"`) has none of those columns.
**Why it happens:** The Bible's own DDL (§4.1) never declared them either — `justification` exists only on the Pydantic `ActionProposal` model (§4.3), not the SQL table; this is a pre-existing Bible-internal gap, not something Phase 1-4 code introduced.
**How to avoid:** This is a `checkpoint:decision` for the plan, not something research can resolve unilaterally. Two viable options, both consistent with established codebase precedent:
  1. **Additive migration** (`infra/postgres/initdb/003_action_proposal_columns.sql`, `IF NOT EXISTS`, applied via `infra/apply-migrations.sh` — exact precedent: `002_change_affects.sql`): add `justification TEXT`, `category VARCHAR(50)`, `created_at TIMESTAMP DEFAULT now()`, `approved_by VARCHAR(50)`, `approved_at TIMESTAMP`.
  2. **Pack into `payload JSONB`**: store `{"action_detail": {...}, "justification": "...", "category": "..."}` and compute `category` at read-time via the same frozen-allowlist pattern `evidence_graph.py` already uses for derived-not-stored values, using the row's own `id` (if timestamp-embedded, e.g. `AP-{utc-strftime}`) for ordering instead of a `created_at` column.
Recommend option 1 for `created_at`/`approved_by`/`approved_at` (genuinely new facts, not derivable from `action_type`) and computing `category` at read-time (it *is* derivable from `action_type` via a frozen mapping, so storing it would violate the "cache never holds a fact not derivable from domain state" principle `evidence_graph.py`'s own docstring establishes for `graph_nodes`/`graph_edges`).
**Warning signs:** A plan that writes `justification` or `category` directly into a bare `UPDATE action_proposals SET justification = ...` without first confirming the column exists will fail at execution with a Postgres `column "justification" of relation "action_proposals" does not exist` error — catch this at plan-review time, not at execute time.

### Pitfall 5: `audit_events` has no auto-timestamp default, and the Bible's DDL comment lists it as VARCHAR(64) with no CHECK
**What goes wrong:** The real table (`[VERIFIED: infra/postgres/initdb/001_schema.sql:183-202]`) declares `timestamp_utc TIMESTAMP` with no `DEFAULT now()` — every `INSERT` must supply it explicitly (the Bible's own `log_event()` does, via `datetime.now(timezone.utc)`), and there is no database-level ordering guarantee beyond application discipline. Two `log_event()` calls racing without the `LOCK TABLE ... IN EXCLUSIVE MODE` step (e.g., a refactor that "optimizes" it away) could both read the same `prev_hash` and insert two rows with the same `previous_event_hash`, silently forking the chain in a way `verify_chain()`'s simple linear `ORDER BY timestamp_utc ASC` scan would not necessarily catch as `TAMPERED` (it would just verify whichever fork sorts second against the wrong predecessor, at best failing loudly; at worst, if timestamps happen to sort the "wrong" branch first, the primary-key constraint would still prevent literal duplicate `event_id`s, but the *hash chain integrity*, not just row uniqueness, is what's at risk).
**Why it happens:** The exclusive table lock is easy to treat as boilerplate and drop during a later refactor once tests are passing without it (most single-writer test runs won't exercise the race).
**How to avoid:** Never remove the `LOCK TABLE audit_events IN EXCLUSIVE MODE` statement from inside `log_event()`'s transaction; add a concurrency test that fires two `log_event()` calls via `asyncio.gather()` and asserts the resulting chain still passes `verify_chain()` with exactly two sequential links (Rule 6's "edge-case coverage" requirement for this Critical-review module).
**Warning signs:** A concurrency-only-reproducible chain break that a single-threaded test suite never exercises.

## Code Examples

### Bible §7.1 `AuditLogger` (verbatim reference implementation)
```python
# Source: AegisX-AI-Project-Bible-v6.md Section 7.1, lines 1122-1185
import json
import hashlib
from datetime import datetime, timezone
import asyncpg
from typing import Dict, Any

class AuditLogger:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self.genesis_hash = "0000000000000000000000000000000000000000000000000000000000000000"

    async def log_event(self, event_data: dict) -> str:
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("LOCK TABLE audit_events IN EXCLUSIVE MODE")
                prev_row = await conn.fetchrow(
                    "SELECT event_hash FROM audit_events ORDER BY timestamp_utc DESC LIMIT 1"
                )
                prev_hash = prev_row['event_hash'] if prev_row else self.genesis_hash
                canonical_data = {k: v for k, v in event_data.items() if k not in ['event_id', 'timestamp_utc', 'event_hash', 'previous_event_hash']}
                canonical_json = json.dumps(canonical_data, sort_keys=True, separators=(',', ':'))
                event_hash = hashlib.sha256(f"{prev_hash}{canonical_json}".encode('utf-8')).hexdigest()
                event_id = f"EVT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
                await conn.execute("""
                    INSERT INTO audit_events
                    (event_id, timestamp_utc, session_id, user_id, user_role, agent_id, action_type, target_system_id, target_record_id, input_hash, output_summary, evidence_ids, opa_rule_ids, model_id, prompt_version, approval_id, previous_event_hash, event_hash)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                """, event_id, datetime.now(timezone.utc), event_data.get('session_id'), event_data.get('user_id'), event_data.get('user_role'), event_data.get('agent_id'), event_data.get('action_type'), event_data.get('target_system_id'), event_data.get('target_record_id'), event_data.get('input_hash'), event_data.get('output_summary'), json.dumps(event_data.get('evidence_ids', [])), json.dumps(event_data.get('opa_rule_ids', [])), event_data.get('model_id'), event_data.get('prompt_version'), event_data.get('approval_id'), prev_hash, event_hash)
                return event_id

    async def verify_chain(self) -> Dict[str, Any]:
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM audit_events ORDER BY timestamp_utc ASC")
            curr_hash = self.genesis_hash
            for index, row in enumerate(rows):
                if row['previous_event_hash'] != curr_hash:
                    return {"status": "TAMPERED", "broken_at_index": index, "event_id": row['event_id']}
                event_data = dict(row)
                canonical_data = {k: v for k, v in event_data.items() if k not in ['event_id', 'timestamp_utc', 'event_hash', 'previous_event_hash']}
                canonical_json = json.dumps(canonical_data, sort_keys=True, separators=(',', ':'))
                recomputed = hashlib.sha256(f"{curr_hash}{canonical_json}".encode('utf-8')).hexdigest()
                if recomputed != row['event_hash']:
                    return {"status": "TAMPERED", "broken_at_index": index, "event_id": row['event_id']}
                curr_hash = recomputed
            return {"status": "VERIFIED", "events_checked": len(rows)}

    async def demonstrate_tamper(self, event_id: str) -> Dict[str, Any]:
        async with self.db_pool.acquire() as conn:
            await conn.execute("UPDATE audit_events SET output_summary = 'TAMPERED DATA' WHERE event_id = $1", event_id)
        return await self.verify_chain()
```
Note: `datetime.now(timezone.utc)` (not the deprecated `datetime.utcnow()`) is already what the Bible's §7.1 sample uses — no fix needed here, unlike `app/schemas.py`'s `AgentMessage.timestamp` which had to work around the Pydantic-model version (`app/schemas.py:77-87`). `self.genesis_hash`'s literal string was counted programmatically this session (`node -e "console.log('...'.length)"` → `64`) — it is exactly 64 characters, matching both the `sha256` hexdigest length and the `VARCHAR(64)` column; **no length mismatch exists** (an earlier manual eyeball count during this research session miscounted it as 68 — corrected before writing this document).

### FastAPI WebSocket testing pattern (official docs, already this codebase's convention)
```python
# Source: https://fastapi.tiangolo.com/advanced/testing-websockets/ [CITED]
# Matches this codebase's existing backend/tests/test_ws_echo.py pattern exactly.
def test_websocket():
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        data = websocket.receive_json()
        assert data == {"msg": "Hello WebSocket"}
```
For REM-04's "proposal → WebSocket push" test: open the WS connection first (`with client.websocket_connect(...) as ws:`), then — still inside that `with` block — issue the triggering HTTP call through the *same* `TestClient` instance (`client.post("/api/systems/.../generate-capa")` or the approve route), then call `ws.receive_json()` and assert the broadcast frame. Starlette's `TestClient` runs the ASGI app in-process and supports this interleaving; `[CITED: fastapi.tiangolo.com/advanced/testing-websockets/, github.com/fastapi/fastapi/discussions/11139]`.

## Regulatory Citation Map (Section 14, quoted — do not use model recall for these, per Rule 13)

| Feature | Regulation | Section | What it Requires | How This Phase Addresses It |
|---------|-----------|---------|-------------------|------------------------------|
| Audit Trails | 21 CFR Part 11 | 11.10(e) | "Secure, computer-generated, time-stamped audit trails" | Hash-chained `audit_events` (AUDIT-01/02/03) — `[VERIFIED: AegisX-AI-Project-Bible-v6.md:1465]` |
| Access control / identity separation | 21 CFR Part 11 | 11.10(d) | (not tabulated in §14's own table, but referenced directly in §16's Q&A prep) | C2 RBAC + Action Gateway — `[VERIFIED: AegisX-AI-Project-Bible-v6.md:1546]`, quoted: `"identity is separated via the Action Gateway (11.10(d))"` |
| Prompt Security | OWASP Top 10 | ASI02 / LLM01 | "Prevent prompt injection manipulation and tool misuse" | C2 Policy Gateway regex/entropy filters — `[VERIFIED: AegisX-AI-Project-Bible-v6.md:1469-1471]` |
| Access Reviews / privileged access weighting | EU GMP Annex 11 + 21 CFR Part 11 | Section 12 / 11.10(d) | Access control, especially privileged | `[VERIFIED: AegisX-AI-Project-Bible-v6.md:224]`, quoted: `"Access control: 20% — Annex 11 S12 + 21 CFR 11.10(d), privileged access is highest risk."` |
| Agent goal hijack / tool misuse | OWASP | ASI01 / ASI02 | Prevent an agent's tools/goals being hijacked via crafted input | C2's role explicitly maps to these — `[VERIFIED: AegisX-AI-Project-Bible-v6.md:353]`, quoted: `"Enforces tool allowlists, RBAC, and prompt injection detection. Maps to OWASP LLM01, ASI01 (Agent Goal Hijack), and ASI02 (Tool Misuse)."` |

Do not cite any other CFR/Annex 11/ICH Q9 section for this phase's work without finding it in the Bible's own text first — Rule 13 is binding.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|----------------|
| A1 | Shannon-entropy threshold of ~4.5 bits/char, evaluated per whitespace token ≥12 chars, is a reasonable starting point for catching obfuscated jailbreak payloads | Common Pitfalls #1, Pattern 2 | If too low: false-positives block legitimate technical/id-bearing queries (a UUID or hash embedded in a normal question gets rejected). If too high: an actual obfuscated jailbreak payload passes through undetected, defeating SAFE-02's purpose. Must be tuned against real seeded test fixtures and confirmed with the user before being treated as a locked constant. |
| A2 | Only the "IT System Manager" role should be permitted to trigger A7 (Generate CAPA) and to approve/execute a pending action, derived by cross-referencing the RBAC permission matrix's "Cannot trigger Remediation A7" note against A7's own agent id | Pattern 1, Architectural Responsibility Map | If wrong, either QA/Compliance gets an unintended remediation-trigger capability (a real compliance-scope violation) or IT System Manager is incorrectly blocked from approving its own generated proposals. This inference is reasonable but not a literal Bible sentence — confirm at plan/discuss time. |
| A3 | `action_proposals.category` should be computed at read-time from `action_type` via a frozen allowlist, not persisted as a new column, while `justification`/`created_at`/`approved_by`/`approved_at` should be added via an additive migration | Pitfall 4, Alternatives Considered | If wrong (e.g., the demo needs to filter/query by category at the SQL level), a read-time-only `category` becomes awkward for a future `WHERE category = 'GXP_RELEVANT_WRITE'` query; this is a `checkpoint:decision` the planner should surface explicitly, not silently pick. |
| A4 | `POST /api/copilot/query` is out of scope for Phase 5 (deferred to Phase 6's "Ask GxP Copilot" page) and SAFE-01/SAFE-02 should be proven via direct unit tests + the graph node + the write-capable routes built this phase | Summary, Anti-Patterns | If wrong and the planner instead builds `/api/copilot/query` this phase to fully closes the loop, that is extra (not harmful) scope — but ROADMAP.md's own Phase 6 success criteria ("chat interface where a user can type the hero query") strongly implies this endpoint does not exist until then; treated here as a scope boundary, not a blocker. |
| A5 | PROHIBITED-category action proposals should still be audit-logged (as a blocked-attempt event) even though the Bible's C3 workflow sentence only narrates the PENDING/approved happy path | Anti-Patterns, Architectural Responsibility Map | If wrong (Bible intends PROHIBITED to be silently dropped), an extra audit event is logged that has no real record — low-risk either way, but flagging since "PROHIBITED: Blocked immediately" (§2, C3) doesn't explicitly say "and log it." Recommended for completeness of the tamper-evident record (11.10(e)'s spirit), not literally mandated. |

## Open Questions

1. **Exact wire-level identity carrier (header vs. body vs. query param)**
   - What we know: D-01 fixes the *shape* (every request carries `user_id` + `role`, sourced from a client-side role selector, no real auth). CONTEXT.md explicitly leaves the *transport* to Claude's discretion at plan time.
   - What's unclear: Whether to use custom headers (`X-User-Id`/`X-User-Role`), a request body field, or a query param.
   - Recommendation: Custom headers via a `Depends()`-based FastAPI dependency (`app/identity.py`). This keeps identity orthogonal to each route's own request-body schema (no need to add `user_id`/`role` fields to every POST body Pydantic model), is the idiomatic place a future real-auth swap (JWT bearer) would also live, and requires only two `fetch()` header additions in `frontend/src/lib/api.ts`'s new `apiPost` helper.

2. **Role-selector placement in the frontend (persistent app-chrome vs. scoped to Approval Centre)**
   - What we know: CONTEXT.md leaves this to Claude's discretion, based on "where RBAC-gated actions actually originate in the UI."
   - What's unclear: The Assurance Card page (Phase 4, already shipped) is where a "Generate CAPA" button would naturally live next to a verified finding — meaning the role selector needs to be visible/settable *before* a user reaches the Approval Centre, not scoped only to that page.
   - Recommendation: Persistent app-chrome control (e.g., in a shared `AppShell` header), not scoped to one page — since the RBAC-gated action (A7 trigger) originates from the Assurance Cards view, not the Approval Centre.

3. **Whether a `POST /api/actions/{id}/reject` route is in scope**
   - What we know: The real `action_proposals.status` column supports arbitrary VARCHAR(50) values; the Bible's DDL *comment* (not present in the actually-migrated table, only in the Bible's own §4.1 text) lists `PENDING, APPROVED, REJECTED`. REM-01 through REM-04 only name the approve path.
   - What's unclear: Whether the Approval Centre UI (SENT-4-08) needs a reject affordance for a complete demo, or whether "approve" is the only interaction required this phase.
   - Recommendation: Build it — it is a small addition once `approve` exists (same route shape, `status="REJECTED"`, same audit-log call with a different `action_type`), and an approval-only UI with no reject path would look incomplete in a live demo even though the roadmap's Phase 5 success criteria only literally names approval.

## Environment Availability

No new external tools, services, or runtimes are required for this phase — Postgres, Qdrant, and OPA are already up per Phase 1's `docker-compose up -d postgres qdrant opa` gate, and this phase adds no new service dependency.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Postgres | `action_proposals`/`audit_events` reads/writes | ✓ (already running per Phase 1) | 16.15 (per `infra/README.md`'s documented image) | `acquire_pool_or_none()` degrade-don't-raise, already established |
| OPA | Not directly used by C2/C3/A7/audit-trail — no new Rego rules this phase | ✓ (already running) | — | N/A — this phase's decision table entries (RBAC, injection detection) are "Deterministic Python," not "OPA/Rego" |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1, no `pytest-asyncio` — every async test wraps its own body in a plain `def test_*` calling `asyncio.run(...)` (confirmed convention, `[VERIFIED: backend/tests/conftest.py:1-31]`, quoted: `"this suite's convention (\`asyncio.run()\` inside a plain \`def test_*\`, no pytest-asyncio)"`) |
| Config file | none — pytest discovers `backend/tests/` by default; `backend/tests/conftest.py` supplies shared fixtures (`client`, `db_pool`, `reset_db_pool`) |
| Quick run command | `cd backend && python -m pytest tests/test_c2_gateway.py tests/test_c3_gateway.py tests/test_a7_remediation.py tests/test_audit_trail.py -x` |
| Full suite command | `cd backend && python -m pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SAFE-01 | `check_rbac` denies QA/Compliance→A7, allows IT System Manager→A7, denies Auditor→A3 | unit | `pytest tests/test_c2_gateway.py::test_rbac_denies_qa_compliance_a7 -x` | ❌ Wave 0 |
| SAFE-02 | Bible's literal regex phrase is blocked; a benign message with a UUID is not; a base64-obfuscated phrase is blocked by entropy leg | unit | `pytest tests/test_c2_gateway.py::test_injection_detection -x` | ❌ Wave 0 |
| AUDIT-01 | `log_event()` inserts a row whose `previous_event_hash` equals the prior row's `event_hash` (or genesis on first row) | integration (real Postgres) | `pytest tests/test_audit_trail.py::test_log_event_chains_correctly -x` | ❌ Wave 0 |
| AUDIT-02 | `verify_chain()` returns `VERIFIED` on an untouched chain and `TAMPERED` with correct `broken_at_index` after a raw `UPDATE` | integration, negative case required (Rule 6) | `pytest tests/test_audit_trail.py::test_verify_chain_detects_tamper -x` | ❌ Wave 0 |
| AUDIT-03 | `POST /api/audit/demonstrate-tamper` route returns the `TAMPERED` verdict end-to-end via `TestClient` | integration | `pytest tests/test_routes_audit.py::test_demonstrate_tamper_endpoint -x` | ❌ Wave 0 |
| REM-01 | A7 with an `INSUFFICIENT_EVIDENCE`-only finding set produces zero proposals; a HIGH/MEDIUM finding produces one | unit | `pytest tests/test_a7_remediation.py::test_a7_filters_by_confidence -x` | ❌ Wave 0 |
| REM-02 | `route_action` maps each of the five Bible categories correctly for synthetic `action_type` fixtures | unit | `pytest tests/test_c3_gateway.py::test_category_routing -x` | ❌ Wave 0 |
| REM-03 | `GET /api/actions` response contains no field that isn't sourced from the `ActionProposal`/DB row (no free-text LLM field in the response schema) | unit (schema inspection) | `pytest tests/test_routes_actions.py::test_approval_response_is_server_trusted -x` | ❌ Wave 0 |
| REM-04 | End-to-end: `generate-capa` POST → WS receives `action_proposal_created` frame → `approve` POST → `audit_events` has a matching row | integration | `pytest tests/test_routes_actions.py::test_full_approval_loop -x` | ❌ Wave 0 |
| UI-02 | `broadcast_json()` reaches all currently-connected sockets, and a dead connection is pruned without blocking the others | unit | `pytest tests/test_ws_broadcast.py::test_broadcast_prunes_dead_connections -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the quick-run command above (four new modules' test files)
- **Per wave merge:** `cd backend && python -m pytest`
- **Phase gate:** full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_c2_gateway.py` — RBAC matrix + injection detection unit tests
- [ ] `backend/tests/test_c3_gateway.py` — category routing unit tests
- [ ] `backend/tests/test_a7_remediation.py` — CAPA synthesis + confidence-filter tests
- [ ] `backend/tests/test_audit_trail.py` — hash-chain append/verify/tamper tests, including the concurrency test named in Pitfall 5
- [ ] `backend/tests/test_routes_actions.py` — full approval-loop integration test
- [ ] `backend/tests/test_routes_audit.py` — `/api/audit/verify`, `/api/audit/demonstrate-tamper` route tests
- [ ] `backend/tests/test_ws_broadcast.py` — extends `test_ws_echo.py`'s existing pattern for the new broadcast frame type
- Framework install: none — pytest already installed and configured

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | Partial — D-01 explicitly defers real authentication; identity is a client-selected demo value, not verified credentials. Document this as an accepted gap for this phase, same as `app/ws/copilot.py`'s existing docstring already does for `session_id` (`[VERIFIED: backend/app/ws/copilot.py:27-32]`, quoted: `"session_id is accepted as a path parameter but is NOT validated against the sessions table, and no authentication is performed on this connection. Both are Phase 5's job (C2 RBAC, SENT-4-01)"`) |
| V3 Session Management | No — no session table wiring this phase; `session_id` remains an unvalidated path parameter |
| V4 Access Control | Yes | `check_rbac()` — frozen permission matrix, fail-closed on unrecognized role (Pattern 1) |
| V5 Input Validation | Yes | `detect_injection()` — regex + entropy (Pattern 2); every new route's request body validated via Pydantic per existing convention |
| V6 Cryptography | Yes | `hashlib.sha256` only — never hand-roll a hash function; no key management needed since this is a hash chain, not an HMAC/signature scheme |
| V5 SQL injection prevention | Yes | Every new query uses asyncpg `$N` placeholders exclusively; table/column names come only from frozen allowlists, mirroring `c1_verifier.py`'s established discipline — no f-string SQL anywhere in the new modules |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Prompt injection / jailbreak (OWASP LLM01/ASI02) | Tampering / Elevation of Privilege | Deterministic regex + entropy detection before any LLM call (C2, Pattern 2) |
| Agent goal hijack via crafted tool-invocation input (OWASP ASI01) | Elevation of Privilege | RBAC check on every agent-invoking route, fail-closed (C2, Pattern 1) |
| Client-asserted role/identity spoofing | Spoofing | Server independently re-derives `user_id`/`role` from the request on every write-capable route — never trusts a value baked into an approval-dialog payload or cached client state without re-checking against the current request's identity headers |
| Audit-log tampering (retroactive record alteration) | Repudiation / Tampering | Hash chain + `verify_chain()` (AUDIT-01/02); `LOCK TABLE ... IN EXCLUSIVE MODE` prevents a race-condition fork (Pitfall 5) |
| LLM-generated UI / prompt injection via a poisoned finding influencing the approval dialog | Tampering | Approval dialog renders only from server-trusted `ActionProposal` metadata fields (structured Pydantic response), never raw LLM text in a field the UI treats as executable/structural (Bible §11.6, REM-03) |
| SQL injection via `action_type`/`category` used to build a query | Tampering | Frozen-allowlist-only table/column names (mirrors `c1_verifier.RULE_EVIDENCE_TABLES`); all bound values via asyncpg placeholders |

## Sources

### Primary (HIGH confidence)
- `AegisX-AI-Project-Bible-v6.md` §1.3 (Deterministic-First Decision Table), §2 (A0-A7, C1, C2, C3 specs), §4.1 (DDL), §4.3 (Pydantic models), §6 (A7 system prompt), §7.1 (hash-chain `AuditLogger`), §11.6 (Action/Approval Centre), §12 (API table), §14 (Regulatory Citation Map) — all read directly this session, line numbers cited inline throughout
- `infra/postgres/initdb/001_schema.sql` (real, already-migrated schema — read directly, lines 158-249)
- `infra/postgres/initdb/002_change_affects.sql` (established additive-migration precedent — read directly)
- `infra/postgres/seed/001_seed.sql` (confirms `action_proposals`/`audit_events` start empty — read directly)
- `backend/app/{main.py, schemas.py, db.py, opa_client.py, llm_router.py, agents/{a0_orchestrator,a2_compliance,c1_verifier,minimal_specialists}.py, graph/{state,evidence_graph}.py, routes/{findings,evidence_graph}.py, ws/copilot.py}` — all read directly this session
- `backend/tests/{conftest.py, test_ws_echo.py}` — read directly this session, establishing test conventions
- `frontend/src/lib/{api.ts, ws.ts}` — read directly this session
- `.planning/{REQUIREMENTS.md, STATE.md, ROADMAP.md, phases/05-safety-remediation/05-CONTEXT.md}` — read directly this session
- `https://fastapi.tiangolo.com/advanced/testing-websockets/` — official FastAPI docs, fetched directly this session, code example transcribed verbatim above

### Secondary (MEDIUM confidence)
- WebSearch: FastAPI WebSocket broadcast/ConnectionManager patterns (`websocket.org/guides/frameworks/fastapi/`, `betterstack.com/community/guides/scaling-python/fastapi-websockets/`, `github.com/fastapi/fastapi/discussions/6370`) — cross-checked against three independent sources, consistent pattern
- WebSearch: hash-chained tamper-evident audit log patterns (`appmaster.io/blog/tamper-evident-audit-trails-postgresql`, `dev.to/veritaschain/...`) — used only to corroborate the Bible's own already-complete algorithm, not as a source of new design

### Tertiary (LOW confidence)
- WebSearch: Shannon entropy for prompt-injection/obfuscation detection — general industry guidance on entropy-based secret/obfuscation scanning exists, but no source gave a project-specific threshold; the 4.5 bits/char starting value in this document is an engineering estimate, marked `[ASSUMED]` (Assumptions Log A1), not a cited external standard

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages, everything already pinned and verified by reading `requirements.txt` directly
- Architecture (C2/C3/A7 module shape, graph wiring): HIGH — directly mirrors existing, already-shipped patterns (`c1_verifier.py`, `a2_compliance.py`, `evidence_graph.py`) read in full this session
- Hash-chain algorithm: HIGH for the algorithm itself (Bible §7.1 transcribed verbatim, genesis-hash length independently verified programmatically); MEDIUM for the JSONB-canonicalization pitfall's exact fix (reasoned from this codebase's own established `evidence_graph.py` workaround, not independently tested against a live asyncpg connection this session)
- Entropy threshold / injection-detection tuning: LOW — no Bible-specified value exists; flagged as `[ASSUMED]` and routed to the Assumptions Log for user confirmation
- `action_proposals` schema gap resolution: MEDIUM — the gap itself is `[VERIFIED]` by direct file read; the recommended resolution (migration vs. JSONB-packing) is a reasoned recommendation, not a locked decision — explicitly flagged as a `checkpoint:decision` for the planner

**Research date:** 2026-08-23
**Valid until:** 30 days (stable, hackathon-internal codebase; no external API/library version drift risk since no new packages are introduced)
