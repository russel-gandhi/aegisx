---
phase: 05-safety-remediation
reviewed: 2026-08-26T00:00:00Z
depth: standard
files_reviewed: 35
files_reviewed_list:
  - backend/app/agents/a0_orchestrator.py
  - backend/app/agents/a7_remediation.py
  - backend/app/agents/c2_gateway.py
  - backend/app/agents/c3_gateway.py
  - backend/app/audit_trail.py
  - backend/app/graph/state.py
  - backend/app/identity.py
  - backend/app/main.py
  - backend/app/routes/actions.py
  - backend/app/routes/audit.py
  - backend/app/schemas.py
  - backend/app/ws/copilot.py
  - backend/requirements.txt
  - backend/tests/conftest.py
  - backend/tests/test_a7_remediation.py
  - backend/tests/test_audit_trail.py
  - backend/tests/test_c2_gateway.py
  - backend/tests/test_c3_gateway.py
  - backend/tests/test_graph_gateways.py
  - backend/tests/test_graph_topology.py
  - backend/tests/test_hero_loop.py
  - backend/tests/test_hero_tracer.py
  - backend/tests/test_routes_actions.py
  - backend/tests/test_routes_audit.py
  - backend/tests/test_ws_broadcast.py
  - frontend/src/__tests__/Actions.test.tsx
  - frontend/src/__tests__/RoleSelector.test.tsx
  - frontend/src/App.tsx
  - frontend/src/components/ActionProposalCard.tsx
  - frontend/src/components/RoleSelector.tsx
  - frontend/src/lib/api.ts
  - frontend/src/lib/identity.ts
  - frontend/src/lib/ws.ts
  - frontend/src/pages/Actions.tsx
  - frontend/src/pages/Copilot.tsx
  - frontend/src/pages/FindingInvestigation.tsx
  - infra/postgres/initdb/003_action_proposals_workflow.sql
findings:
  critical: 1
  warning: 5
  info: 2
  total: 8
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-08-26T00:00:00Z
**Depth:** standard
**Files Reviewed:** 35
**Status:** issues_found

## Summary

Reviewed the full Phase 5 Safety & Remediation slice: C2 (RBAC + prompt-injection detection), C3 (action-category routing), A7 (remediation synthesis), the hash-chained audit trail, and their HTTP/WS surface plus the frontend approval-centre UI, against the deterministic-first constraint (Bible Section 1.3) and fail-closed requirements called out in the task brief.

The core deterministic-first invariant holds: an AST-gated test suite proves C2 and C3 import no model client, and A7 is confirmed the single node in the fixed topology permitted a model call, gated on C1-verified confidence only. RBAC (`check_rbac`) and identity resolution (`require_identity`) both fail closed on an unrecognized/absent role, and every write-capable route in `routes/actions.py` enforces RBAC before any DB or model call.

However, the audit-chain **write** surface has a real authorization gap: `POST /api/audit/demonstrate-tamper` — a genuine row-mutating endpoint on the tamper-evidence subsystem — has no `check_rbac`-equivalent gate at all, so the "Auditor" role (explicitly read-only per the Bible's own permission matrix) can invoke it to corrupt audit rows, inconsistent with every other write route in this phase. Several other findings degrade the strength of two other Critical-review-bar subsystems: the injection detector's regex/entropy legs are both trivially bypassable, and the hash-chain's ordering relies solely on wall-clock `timestamp_utc` with no monotonic tiebreaker, which is a provable weakness in a tamper-evidence design even though the `LOCK TABLE ... EXCLUSIVE MODE` statement narrows the practical window.

## Critical Issues

### CR-01: `demonstrate-tamper` audit-mutation endpoint has no RBAC gate — any recognized role, including the read-only "Auditor," can corrupt the audit chain

**File:** `backend/app/routes/audit.py:43-75`
**Issue:** Every write-capable route in `routes/actions.py` (`generate_capa`, `approve_action`, `reject_action`) enforces `check_rbac(identity.role, "A7")` before performing any mutation. `post_demonstrate_tamper` performs a real row `UPDATE` against `audit_events` (via `audit_trail.demonstrate_tamper`) but only resolves identity through `require_identity` — it never calls `check_rbac` or any other authorization check. `require_identity` accepts any of the three Bible-defined roles (`IT System Manager`, `QA/Compliance`, `Auditor`), so an actor authenticated as `Auditor` — whose Bible-defined scope is explicitly "Read-only System and Compliance metrics" — can invoke this endpoint and mutate/corrupt an audit_events row. This directly contradicts the RBAC model this same phase establishes everywhere else, and it lands on the audit trail, the one subsystem whose entire purpose is tamper-evidence. No existing test (`test_routes_audit.py`) asserts this endpoint is denied to any role — every test in that file uses `IT_MANAGER_HEADERS` only, which is consistent with there being no gate to test.
**Fix:**
```python
# backend/app/routes/audit.py
from app.agents.c2_gateway import check_rbac

@router.post("/api/audit/demonstrate-tamper", response_model=TamperDemoResponse)
async def post_demonstrate_tamper(
    request: TamperDemoRequest,
    identity: RequestIdentity = Depends(require_identity),
):
    if identity.role != "IT System Manager":
        raise HTTPException(
            status_code=403,
            detail=f"Role {identity.role} may not invoke the audit tamper demo",
        )
    ...
```

## Warnings

### WR-01: `require_identity` never validates `X-User-Id` is non-empty, undermining the "attributable" audit guarantee

**File:** `backend/app/identity.py:45-67`
**Issue:** `require_identity` validates `x_user_role` against `DEMO_ROLES` (fail-closed, 403 on an unrecognized role) but performs no validation on `x_user_id` at all beyond FastAPI's "header present" check — an empty string (`X-User-Id:`) satisfies `Header(...)`'s required-ness. Every write route stores `identity.user_id` directly into `action_proposals.approved_by` and `audit_events.user_id`, which is the system's sole attribution mechanism (ALCOA+ "attributable" dimension the codebase elsewhere treats as load-bearing, e.g. `app/schemas.py`'s `ALCOAScore.attributable` defaulting to `False`). A caller can send a valid role header with a blank or arbitrary `X-User-Id` and still approve/reject/generate CAPAs or invoke the tamper demo, producing audit rows attributed to an empty or spoofed actor.
**Fix:**
```python
async def require_identity(
    x_user_id: str = Header(...),
    x_user_role: str = Header(...),
) -> RequestIdentity:
    if not x_user_id.strip():
        raise HTTPException(status_code=422, detail="X-User-Id must not be empty")
    if x_user_role not in DEMO_ROLES:
        raise HTTPException(status_code=403, detail=f"Unrecognized role: {x_user_role}")
    return RequestIdentity(user_id=x_user_id, role=x_user_role)
```

### WR-02: Prompt-injection detection is trivially bypassable on both legs

**File:** `backend/app/agents/c2_gateway.py:69-125`
**Issue:** `detect_injection` is the *only* safety net against prompt injection in this system (no LLM-based check exists, by design). Its regex leg (`JAILBREAK_PATTERNS`) matches exactly three literal English phrases with no synonym/wildcard tolerance — `"please ignore the previous instructions"`, `"kindly disregard all prior rules"`, or `"override the system's prompt"` (minor rewordings of the exact phrases the tests exercise) all bypass it, since `.search()` requires the literal substring. The entropy leg only evaluates whitespace-delimited tokens ≥12 characters (`MIN_TOKEN_LENGTH_FOR_ENTROPY`); an attacker can defeat it by inserting spaces/hyphens into an encoded payload to keep every token under the 12-character floor (e.g. `"aWdub3Jl cHJldmlv dXMgaW5z dHJ1Y3Rp b25z"`), which reassembles to the same jailbreak instruction on the far side of the LLM's tokenizer while never tripping either leg. Both bypasses are real and demonstrable, and this module is explicitly called out in the review brief as a Critical-review-bar subsystem.
**Fix:** Broaden the regex set to a stemmed/fuzzy match (or a small classifier list of trigger n-grams) rather than three exact phrases, and compute entropy over the whole message with whitespace/punctuation stripped (not per-whitespace-token) so a chunked/padded encoded payload cannot duck under the per-token length floor.

### WR-03: Audit-chain ordering relies solely on wall-clock `timestamp_utc` with no monotonic tiebreaker

**File:** `backend/app/audit_trail.py:119-227`
**Issue:** Both `log_event`'s "find the previous row" query (`SELECT event_hash FROM audit_events ORDER BY timestamp_utc DESC LIMIT 1`, line 136) and `verify_chain`'s full-table walk (`SELECT * FROM audit_events ORDER BY timestamp_utc ASC`, line 206) order rows exclusively by `timestamp_utc`, a plain Python `datetime.now(timezone.utc)` value with no monotonic tiebreaker column (e.g. a `SERIAL`/`BIGSERIAL` id). SQL `ORDER BY` on a column with duplicate values has no defined tie-breaking order. The `LOCK TABLE audit_events IN EXCLUSIVE MODE` statement narrows the window in which two `log_event` calls could race, but it does not guarantee two back-to-back writes receive distinct timestamps — clock resolution and scheduling jitter can still produce identical `timestamp_utc` values for two sequentially-committed rows. If that happens, `verify_chain`'s walk order can differ from `log_event`'s actual chaining order, which is exactly the failure mode a tamper-evident hash chain must not have: a legitimate, untampered chain could report `TAMPERED` (false positive), or in a worse case a genuinely reordered/tampered pair of rows could be missed if the recomputed hash still happens to match under the wrong order.
**Fix:** Add a strictly monotonic tiebreaker (a `BIGSERIAL id` column populated by the same transaction) and order both queries by it (`ORDER BY id ASC` / `ORDER BY id DESC LIMIT 1`) instead of, or in addition to, `timestamp_utc`.

### WR-04: `approve_action` does not verify the proposal's category is actually queueable before treating it as approved-for-out-of-band-execution

**File:** `backend/app/routes/actions.py:311-322`
**Issue:** `approve_action` computes `category = route_action(row["action_type"])` and branches:
```python
if category == "MOCK_WRITE_LOW_RISK":
    new_status = "EXECUTED"
    ...
else:
    # GXP_RELEVANT_WRITE (the only other QUEUED_CATEGORIES member) -- ...
    new_status = "APPROVED"
```
This `else` branch assumes category can only ever be `GXP_RELEVANT_WRITE` at this point (because `generate_capa` only ever persists a row when `category in QUEUED_CATEGORIES`), but that invariant is never re-checked here — `category` is recomputed at approval time from the live `ACTION_CATEGORIES` allowlist, not stored on the row. If `ACTION_CATEGORIES` (`c3_gateway.py`) is ever edited, or a row's `action_type` is otherwise altered between proposal creation and approval, a category that should be `PROHIBITED` (or any other non-queued category) would silently fall into the `else` branch and be marked `APPROVED`/"approved for out-of-band execution" instead of being rejected. This is the one place in the write surface that does not apply the same fail-closed discipline `route_action`'s own default (fails closed to `PROHIBITED` for anything unmapped) and `check_rbac` (fails closed on an unrecognized role) establish everywhere else in this phase.
**Fix:**
```python
category = route_action(row["action_type"])
if category == "MOCK_WRITE_LOW_RISK":
    new_status = "EXECUTED"
    execution_result = f"MOCK-TICKET-{proposal_id}"
elif category == "GXP_RELEVANT_WRITE":
    new_status = "APPROVED"
    execution_result = (
        "Approved for out-of-band execution; this system performs no "
        "write against a validated GxP record."
    )
else:
    raise HTTPException(
        status_code=409,
        detail=f"Proposal {proposal_id} resolves to category {category!r}, which is not approvable",
    )
```

### WR-05: `run_c3` silently drops actions whose category is neither queued nor blocked, and can then report a misleading legacy sentence

**File:** `backend/app/agents/c3_gateway.py:159-195`
**Issue:** `run_c3` iterates `proposed_actions` and only increments `queued` or `blocked_count` when `category in QUEUED_CATEGORIES` or `category in BLOCKED_CATEGORIES` respectively (lines 180-185). A `proposed_actions` entry whose category is `READ` or `DRAFT` (both legitimate Bible-Section-2 categories `ACTION_CATEGORIES` maps to, even though A7 never currently emits them) is counted in neither bucket. If such an entry were ever the *only* entry in `proposed_actions`, `queued == 0 and blocked_count == 0` is still true, so the function returns the zero-actions legacy sentence "Execution complete. Actions queued for approval." even though one action actually existed and was neither queued for approval nor blocked — a misleading summary for a function whose only job (per its own module docstring) is to compose a server-trusted, accurate disposition sentence. Currently unreachable via the real graph (A7's only `action_type` resolves to `GXP_RELEVANT_WRITE`), but this is a latent, provable defect in a function documented as exhaustive over "the five Bible categories."
**Fix:** Track a third `auto_executed` counter for READ/DRAFT categories and include it in the composed sentence, or explicitly branch on all five categories rather than only the two queue-relevant ones.

## Info

### IN-01: `generate_capa` has no idempotency guard against duplicate proposals for the same finding

**File:** `backend/app/routes/actions.py:145-263`
**Issue:** Calling `POST .../generate-capa` twice for the same `finding_id` while the first proposal is still `PENDING_APPROVAL` creates a second, independent `action_proposals` row rather than returning the existing pending proposal or rejecting the duplicate request. This is a minor UX/data-quality gap (duplicate CAPAs in the approval queue for the same underlying gap) rather than a correctness or security defect.
**Fix:** Before calling `persist_proposal`, check for an existing `PENDING_APPROVAL` row with the same `finding_id` and short-circuit to it if found.

### IN-02: `connectCopilotStream` does not URI-encode `sessionId` when building the WebSocket URL

**File:** `frontend/src/lib/ws.ts:64-69`
**Issue:** `` `${resolveWsBase()}/api/copilot/stream/${sessionId}` `` interpolates `sessionId` directly, unlike every REST helper in `lib/api.ts`, which consistently wraps path segments in `encodeURIComponent`. Both current call sites generate `sessionId` locally (`copilot-${Math.random()...}` or the literal constant `"action-approval-centre"`), so this is not exploitable today, but it is an inconsistency with this codebase's own established convention that would become a real bug the moment a session id is ever derived from external/user input.
**Fix:** `` `${resolveWsBase()}/api/copilot/stream/${encodeURIComponent(sessionId)}` ``

---

_Reviewed: 2026-08-26T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
