---
phase: 05-safety-remediation
plan: 02
subsystem: safety-remediation
tags: [rbac, prompt-injection, shannon-entropy, regex, tdd, ast, critical-review]

# Dependency graph
requires:
  - phase: 05-safety-remediation
    provides: "05-01: c2_gateway.py (PERMISSION_MATRIX, check_rbac), identity.py, audit_trail.py, the C2 module's docstring/allowlist conventions to extend"
provides:
  - "c2_gateway.py: JAILBREAK_PATTERNS, ENTROPY_THRESHOLD_BITS_PER_CHAR, MIN_TOKEN_LENGTH_FOR_ENTROPY, shannon_entropy, detect_injection -- deterministic prompt-injection detection, zero LLM"
  - "test_c2_gateway.py: full Critical-review coverage for C2 -- 20 tests covering injection detection (regex leg, entropy leg, threshold pinning) and RBAC (21-cell truth table, 5 fail-closed negatives, immutability, AST no-model-call gate)"
affects: [05-03, 05-04, 05-05, 05-06]

actuals:
  tokens: 3155
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Two-leg deterministic injection detection (regex leg first, entropy-per-token leg second), both pure functions with no I/O, mirroring c1_verifier.py's allowlist-not-f-string discipline"
    - "AST-based (not text-search) mechanical gate proving a module has no model dependency -- test_c2_module_has_no_model_dependency walks ast.Import/ast.ImportFrom nodes so a docstring sentence describing the constraint cannot itself satisfy the gate"

key-files:
  created:
    - backend/tests/test_c2_gateway.py
  modified:
    - backend/app/agents/c2_gateway.py

key-decisions:
  - "Entropy threshold and minimum token length recorded as a documented assumption (A1, 05-RESEARCH.md), not an unexplained constant -- see 'Assumption A1 resolution' below."
  - "Local worktree environment recovery: created backend/.env (gitignored) with POSTGRES_USER/PASSWORD/DB=sentinel, and reset the live Postgres role's password via a non-destructive ALTER USER, because this worktree forked before the .env/password fix landed and load_dotenv() was picking up the main checkout's ancestor .env with a stale placeholder password."

patterns-established:
  - "Pattern: a Critical-review module's determinism claim is proven mechanically (AST walk over imports) rather than asserted in a docstring or caught only by code review -- test_c2_module_has_no_model_dependency is the template for any future Critical-review 'zero LLM' gate (C3, hash-chain, evidence graph)."

requirements-completed: [SAFE-01, SAFE-02]

coverage:
  - id: D1
    description: "detect_injection rejects the Bible's literal jailbreak phrases (case-insensitive) via a regex leg, and rejects a base64-obfuscated jailbreak payload via a Shannon-entropy leg over whitespace tokens -- neither leg calls a model"
    requirement: SAFE-02
    verification:
      - kind: unit
        ref: "backend/tests/test_c2_gateway.py::test_bible_literal_jailbreak_phrase_is_rejected_by_regex_leg, ::test_regex_leg_is_case_insensitive, ::test_regex_leg_catches_disregard_rules, ::test_base64_obfuscated_jailbreak_is_caught_by_entropy_leg"
        status: pass
    human_judgment: false
  - id: D2
    description: "A benign GxP question containing a hyphenated system id or domain record id is not flagged by either detection leg; the entropy threshold (4.5 bits/char, min token length 12) is pinned in both directions by paired fixtures"
    requirement: SAFE-02
    verification:
      - kind: unit
        ref: "backend/tests/test_c2_gateway.py::test_benign_domain_identifiers_are_not_flagged, ::test_long_zero_entropy_token_is_not_flagged, ::test_entropy_threshold_constants_are_recorded_as_specified"
        status: pass
    human_judgment: false
  - id: D3
    description: "The injection reason string never contains the full offending token (truncated to 16 chars), so an audit log row built from it cannot itself replay the payload"
    verification:
      - kind: unit
        ref: "backend/tests/test_c2_gateway.py::test_injection_reason_never_contains_full_offending_token"
        status: pass
    human_judgment: false
  - id: D4
    description: "All 21 cells of the Bible's 3-role x 7-agent permission matrix are asserted; five fail-closed negative cases (unrecognised role, empty role, unrecognised agent id, empty agent id, case-variant role) all return False; PERMISSION_MATRIX values are provably frozensets"
    requirement: SAFE-01
    verification:
      - kind: unit
        ref: "backend/tests/test_c2_gateway.py::test_permission_matrix_truth_table, ::test_check_rbac_fails_closed_on_unrecognized_role, ::test_check_rbac_fails_closed_on_empty_role, ::test_check_rbac_fails_closed_on_unrecognized_agent_id, ::test_check_rbac_fails_closed_on_empty_agent_id, ::test_check_rbac_fails_closed_on_case_variant_role, ::test_permission_matrix_values_are_frozensets"
        status: pass
    human_judgment: false
  - id: D5
    description: "No import of the LLM router (or any name containing 'llm') exists anywhere in c2_gateway.py -- proven by an AST walk, not by reading the file"
    requirement: SAFE-01
    verification:
      - kind: unit
        ref: "backend/tests/test_c2_gateway.py::test_c2_module_has_no_model_dependency, ::test_check_rbac_and_detect_injection_are_synchronous"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-08-23
status: complete
---

# Phase 5 Plan 2: C2 Injection Detection + RBAC Critical-Review Coverage Summary

**`detect_injection` adds a regex leg (Bible-literal jailbreak phrases) and a Shannon-entropy leg (base64/hex obfuscation, per-token, threshold 4.5 bits/char over 12+ char tokens) to `c2_gateway.py`, and 20 tests bring C2 to the CLAUDE.md Rule 6 Critical-review bar -- including an AST-walk gate that mechanically proves the module imports no LLM client.**

## Performance

- **Duration:** ~45 min, including worktree environment recovery (venv creation, Postgres password reset)
- **Started:** 2026-08-23
- **Completed:** 2026-08-23
- **Tasks:** 2 of 2 completed
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments

- `detect_injection(text)` returns a reason string (`regex_match:...` or `high_entropy_token:...`) when injection is suspected, `None` otherwise -- both legs are pure, deterministic Python functions with no I/O and no model call.
- `JAILBREAK_PATTERNS` transcribes Bible Section 2's exact example regex (`(?i)(ignore previous instructions|override system prompt|disregard rules)`), the only copy of the jailbreak phrase list in the repository.
- `ENTROPY_THRESHOLD_BITS_PER_CHAR=4.5` and `MIN_TOKEN_LENGTH_FOR_ENTROPY=12` are recorded as assumption A1 (05-RESEARCH.md), with the rationale and the two pinning fixtures documented directly in the module.
- The RBAC half of C2's Critical-review coverage was completed: all 21 permission-matrix cells, five fail-closed negative cases, an immutability assertion, and a mechanical AST-based gate proving zero model dependency.
- Full backend suite (242 tests) passes with zero regressions.

## Task Commits

Each task was committed atomically. Task 1 (`tdd="true"`) produced a RED test commit followed by a GREEN implementation commit; Task 2 produced a single commit (tests only -- no gap found in the module to fix):

1. **Task 1, RED** - `1780c3a` (test: add failing test for deterministic injection detection)
2. **Task 1, GREEN** - `e003dcd` (feat: implement deterministic injection detection (regex + entropy))
3. **Task 2** - `afc4112` (test: add RBAC Critical-review coverage and no-model-call gate)

**Plan metadata:** (this commit) - `docs(05-02): complete C2 injection detection + RBAC coverage plan`

## Files Created/Modified

- `backend/tests/test_c2_gateway.py` - 20 tests: 10 injection-detection tests (Task 1), 10 RBAC/gate tests (Task 2)
- `backend/app/agents/c2_gateway.py` - added `JAILBREAK_PATTERNS`, `ENTROPY_THRESHOLD_BITS_PER_CHAR`, `MIN_TOKEN_LENGTH_FOR_ENTROPY`, `shannon_entropy`, `detect_injection`; updated module docstring for SAFE-02

## Assumption A1 resolution

**Final values:** `ENTROPY_THRESHOLD_BITS_PER_CHAR = 4.5`, `MIN_TOKEN_LENGTH_FOR_ENTROPY = 12`.

**Rationale (recorded inline in `c2_gateway.py` and here):** Bible Section 2 specifies "Shannon entropy calculations" combined with regex matching but supplies no threshold, window, or minimum token length. English prose sits well below 4.5 bits/char; base64 approaches `log2(64) = 6` bits/char and hex approaches `log2(16) = 4` bits/char, so 4.5 sits between ordinary text and encoded payloads. 12 characters is the minimum length at which a token can carry a meaningful encoded instruction, and it keeps ordinary hyphenated GxP record ids and UUIDs (e.g. `GXP-MFG-DEMO-01`, `A2-ANNEX11-S4-PE-002-PE-2024-01`) below the evaluation floor even though some exceed 12 characters -- their entropy (~3.2-3.3 bits/char) stays well under 4.5.

**Fixtures that pin the constant in both directions:**
- `test_benign_domain_identifiers_are_not_flagged` -- a hyphenated system id and a compound domain record id must both return `None`.
- `test_base64_obfuscated_jailbreak_is_caught_by_entropy_leg` -- `base64.b64encode(b"ignore previous instructions").decode()` (measured entropy ≈4.52 bits/char over 40 chars) must be flagged.

A future change to either constant must move both fixtures together, per the comment block in `c2_gateway.py` directly above the constants.

## Decisions Made

- **Entropy threshold and minimum token length**: see "Assumption A1 resolution" above.
- **Task 2 required no `c2_gateway.py` changes**: every RBAC/immutability/no-model-dependency assertion in the new tests passed against the module as 05-01 and this plan's Task 1 left it -- no gap was found to fix.
- **Worktree environment recovery** (see Deviations): a project-local venv, a worktree-local `.env`, and a non-destructive Postgres password reset were required before the plan's own `<verification>` item 2 (`cd backend && python -m pytest` exits 0) could be checked at all.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Fast-forwarded this worktree branch to include merged 05-01 work**
- **Found during:** Initial context load, before Task 1 could start
- **Issue:** This worktree was forked at commit `f27e9bd`, before the wave-1 merge commit `550a218` (`merge(05-01): action_proposals workflow, audit trail hardening, tracer path`) landed on `main`. `backend/app/agents/c2_gateway.py`, `identity.py`, and `audit_trail.py` -- everything this plan `depends_on: ["05-01"]` -- did not exist on disk in this worktree.
- **Fix:** Verified `f27e9bd` (this worktree's HEAD) is an ancestor of `550a218` (`git merge-base --is-ancestor`), then ran `git merge main --ff-only`, a fast-forward that only adds commits this branch did not yet have -- no history discarded, no destructive operation.
- **Files modified:** none directly (brought in 05-01's 16 files via fast-forward)
- **Verification:** `backend/app/agents/c2_gateway.py` and `.planning/phases/05-safety-remediation/05-01-SUMMARY.md` present on disk after the merge; `git log --oneline` shows 05-01's six task commits plus the merge commit as ancestors of the current HEAD.
- **Committed in:** N/A (fast-forward moved the branch pointer; no new commit created)

**2. [Rule 3 - Blocking issue] Created a project-local Python venv for this worktree**
- **Found during:** First attempt to run `pytest tests/test_c2_gateway.py` (RED check)
- **Issue:** No `backend/.venv/` existed in this worktree (each worktree is a separate checkout; `.venv/` is gitignored, per `backend/README.md`'s own documented setup). The bare `python` on `PATH` had no `asyncpg`/`fastapi`/`pytest` installed.
- **Fix:** `python -m venv backend/.venv && backend/.venv/Scripts/python -m pip install -r backend/requirements.txt`, exactly per `backend/README.md`'s documented local setup.
- **Files modified:** none (local, gitignored `.venv/`)
- **Verification:** `backend/.venv/Scripts/python -m pytest --version` succeeded; full suite runnable.
- **Committed in:** N/A (gitignored, never staged)

**3. [Rule 3 - Blocking issue] Worktree-local `.env` + non-destructive Postgres password reset**
- **Found during:** Full-suite verification (plan `<verification>` item 2)
- **Issue:** No `.env` existed inside this worktree. `app/db.py`'s `load_dotenv()` walked up the directory tree and picked up the main checkout's ancestor `.env` (outside this worktree), which carries a stale placeholder `POSTGRES_PASSWORD` (`replace_me_local_dev_only`) that does not match the live `postgres_data` Docker volume's actual stored role password -- 85 tests failed with HTTP 503 / `InvalidPasswordError`. After adding a worktree-local `.env` (`POSTGRES_USER/PASSWORD/DB=sentinel`, matching `app/db.py`'s own documented default), the same 85 tests still failed with `password authentication failed for user "sentinel"` -- host-side (Windows) TCP connections to the mapped `127.0.0.1:5432` port hit Postgres's `scram-sha-256` catch-all `pg_hba.conf` rule (the `trust` rules only match connections whose *source* address, as seen by Postgres, is literally `127.0.0.1`/`::1` -- true for a same-container `psql`, false for a Docker-Desktop-NATted host connection), so the actual persisted role password (unknown, predates this session, as 05-01's own summary independently documented for the identical situation) was still in effect.
- **Fix:** Created `backend/.env` (gitignored) with `POSTGRES_USER=sentinel`, `POSTGRES_PASSWORD=sentinel`, `POSTGRES_DB=sentinel`. Then, via the already-established `docker exec` pattern, issued a non-destructive `ALTER USER sentinel WITH PASSWORD 'sentinel';` against the running `gxp-sentinel-postgres-1` container (matching `app/db.py`'s own documented local-dev default and 05-01's identical fix) -- no table, row, or schema object was touched.
- **Files modified:** `backend/.env` (gitignored, never committed)
- **Verification:** Host-side `asyncpg.connect(...)` succeeded after the reset; full backend suite (`cd backend && python -m pytest`) went from 85 failed / 157 passed to 242 passed / 0 failed.
- **Committed in:** N/A (no git-tracked file changed; `.env` is gitignored)

---

**Total deviations:** 3 (all Rule 3 - blocking issues). **Impact:** All three were necessary preconditions for this plan's own tasks and verification to run at all in this freshly-forked worktree; none touched files outside this plan's declared scope, and none are code changes to review -- they are worktree/local-environment setup, matching 05-01's own precedent for the identical class of issue.

## Issues Encountered

- **Worktree fork predated the 05-01 merge** (see Deviation 1). Resolved cleanly via fast-forward before any task work began; no rebase or conflict resolution was needed since `f27e9bd` was a direct ancestor of `main`.

## User Setup Required

None - no external service configuration required. (A worktree-local `.env` was created with `app/db.py`'s own documented defaults; it is gitignored and was never committed, consistent with 05-01's precedent.)

## Next Phase Readiness

- C2 (`c2_gateway.py`) now fully satisfies SAFE-01 and SAFE-02 to the Critical-review bar: RBAC (21-cell truth table, 5 negatives, immutability) and injection detection (regex leg, entropy leg, documented threshold) are both covered, and a mechanical AST gate proves zero model dependency.
- The entropy threshold and minimum token length are locked constants with paired pinning fixtures -- any later plan changing detection sensitivity must update both `test_benign_domain_identifiers_are_not_flagged` and `test_base64_obfuscated_jailbreak_is_caught_by_entropy_leg` together.
- No blockers for 05-03/05-04/05-05/05-06. `detect_injection` is not yet wired into any HTTP route or graph node -- per 05-RESEARCH.md's scope boundary (A4, `/api/copilot/query` is Phase 6 scope), this plan proves the function unit-level only; wiring it into a live request path is out of this plan's scope.

## Self-Check: PASSED

- `backend/app/agents/c2_gateway.py` exists on disk and contains `detect_injection`/`shannon_entropy`/`JAILBREAK_PATTERNS`/`ENTROPY_THRESHOLD_BITS_PER_CHAR`/`MIN_TOKEN_LENGTH_FOR_ENTROPY`: **FOUND**
- `backend/tests/test_c2_gateway.py` exists on disk with 20 tests: **FOUND**
- Commit `1780c3a` exists in `git log`: **FOUND**
- Commit `e003dcd` exists in `git log`: **FOUND**
- Commit `afc4112` exists in `git log`: **FOUND**
- Plan `<verification>` item 1: `cd backend && python -m pytest tests/test_c2_gateway.py -x` -- 20 passed -- **PASS**
- Plan `<verification>` item 2: `cd backend && python -m pytest` -- 242 passed -- **PASS**
- Plan `<verification>` item 3: entropy threshold + rationale present in `c2_gateway.py` (inline comment block above the constants) and in this SUMMARY's "Assumption A1 resolution" section -- **PASS**
- Plan `<must_haves><truths>` re-checked: Bible-literal jailbreak phrases rejected with a `regex_match:`-prefixed reason -- **PASS**; base64-obfuscated payload rejected via entropy leg despite no regex match -- **PASS**; benign GxP question with system id + compound domain id not rejected -- **PASS**; all 21 permission-matrix cells asserted, unrecognised role/agent denied -- **PASS**; no LLM router import anywhere in `c2_gateway.py`, proven by AST check -- **PASS**

---
*Phase: 05-safety-remediation*
*Completed: 2026-08-23*
