# Phase 5: Safety & Remediation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-23
**Phase:** 05-safety-remediation
**Areas discussed:** Identity/role source for RBAC, Demo approval flow, A7 Remediation trigger point, C2 gating scope

---

## Identity/role source for RBAC

| Option | Description | Selected |
|--------|-------------|----------|
| Full auth (JWT/session) | Real login/auth system | |
| Fixed demo identity + role selector | No real auth; a role selector picks IT System Manager / QA-Compliance / Auditor; every request carries user_id + role | ✓ |

**User's choice:** Fixed demo identity context — no real authentication. Role selector offers IT System Manager, QA-Compliance, Auditor. Every request carries `user_id` and `role`.
**Notes:** User answered all four gray areas in a single combined response rather than turn-by-turn. Wire-level transport mechanism (header/param/body) left to Claude's discretion — see CONTEXT.md.

---

## Demo approval flow

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-execute low-risk actions | Some action categories skip human approval | |
| All actions require explicit human approval | No auto-execution path anywhere | ✓ |

**User's choice:** All remediation/actions require explicit human approval. Flow: A7 proposal → C3 gateway → PENDING_APPROVAL → user approval → execution → hash-chained audit event.
**Notes:** Confirmed as the literal shape already implied by Bible §11.6 and Build-Map SENT-4-04 — not a new design choice, just ratified with no shortcut/auto-approve mode for the demo.

---

## A7 Remediation trigger point

| Option | Description | Selected |
|--------|-------------|----------|
| Automatic after failing finding | A7 runs whenever C1 returns INSUFFICIENT_EVIDENCE or a failing check | |
| Explicit user action | A7 only runs when the user clicks "Generate CAPA" on a finding | ✓ |

**User's choice:** Only run through explicit user action ("Generate CAPA"). Do not automatically generate remediation after every finding.
**Notes:** Keeps the Phase 3/4 hero loop (query → finding → Assurance Card) untouched; A7 is an opt-in follow-up, not a side effect of the normal query flow.

---

## C2 gating scope

| Option | Description | Selected |
|--------|-------------|----------|
| All endpoints, including existing reads | C2 RBAC/injection check wraps every route, including Phase 4's read-only evidence/graph/findings endpoints | |
| Write-capable endpoints only | C2 applies only to endpoints that create/approve/execute/mutate state; existing Phase 4 read endpoints stay ungated | ✓ |

**User's choice:** Apply C2 RBAC + injection checks to all write-capable endpoints. Read-only evidence/query endpoints do not require action gating.
**Notes:** Explicitly confirmed this leaves Phase 4's shipped `GET .../evidence-graph`, `GET .../blast-radius`, `GET .../assurance-cards`, and `POST .../evidence-graph/rebuild` outside C2's scope — rated `costly` to reverse in CONTEXT.md since moving the boundary later means retrofitting already-shipped, tested routes.

---

## Claude's Discretion

- Exact request-carrier mechanism for `user_id`/`role` (header vs. query param vs. request body field).
- Whether the role selector lives in persistent app chrome (e.g. `AppShell`) or is scoped to the Approval Centre page.

## Deferred Ideas

None raised in this discussion. (Live auto-refresh for Phase 4's evidence-graph/findings pages was already logged separately in `.planning/STATE.md` Pending Todos during Phase 4 verification — not re-raised here.)
