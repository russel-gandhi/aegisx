# policies/

Rego policy bundle root (D-01, D-02).

## What lands here

This directory is the OPA policy bundle root and the host side of OPA's read-only bind mount at `/policies` inside the container (`./policies:/policies:ro` in `docker-compose.yml`). OPA loads only `.rego`, `.json`, `.yaml`, and `.yml` files from this tree — a `.md` file here is inert and safe, which is why this README can live alongside the bundle without being picked up as policy input.

The bundle will eventually contain all 10 Rego rules from Bible Section 3.3, each mapped to a EU GMP Annex 11 / 21 CFR 11 / ICH Q9 clause, plus their `opa test` fixtures (synthetic positive and negative cases).

## Owning tickets (Stage 1)

| Ticket | Contract |
|---|---|
| SENT-1-03 | All 10 Rego rules implemented, unit-tested with `opa test` against synthetic positive + negative fixtures, independent of the app. **Critical review** — unit + negative + edge-case + integration coverage per Rule 6. |
| SENT-1-04 | Consumes this bundle over REST via `evaluate_opa_policy()`, wiring the FastAPI backend to the live OPA sidecar. |

## Regulatory citations

Regulatory citations embedded in rule comments (Annex 11 sections, 21 CFR 11 clauses, ICH Q9 references) must come from the Bible's Section 14 citation map, never from model recall (Rule 13).

This directory is intentionally empty of `.rego` sources until Stage 1 (ROADMAP Phase 2) begins; it exists now, committed, so a fresh clone has a real host directory for OPA's mount rather than a Docker-fabricated root-owned one.

## Rule bundle (Stage 1)

`policies/gxp_rules.rego` implements all 10 rules from Bible Section 3.3 in `package sentinel.gxp`, served at `/v1/data/sentinel/gxp/violation`. Three rule-level corrections to the Bible's literal text, plus the deterministic-clock test mechanism, are recorded in [`BIBLE-DEVIATIONS.md`](./BIBLE-DEVIATIONS.md) and routed to the `SENT-7-05` bible-reconciliation review — no rule ID, severity, citation, description, or threshold constant was changed.

| Rule ID | Severity | Table | Seeded record that triggers it |
|---|---|---|---|
| `ANNEX11-S4-DOC-001` | HIGH | `documents` | `DOC-2026-OM-99` (Gap 1: DRAFT O&M manual) |
| `ANNEX11-S12-ACC-001` | HIGH | `access_reviews` | `AR-2026-05` (Gap 2: 98 days overdue) |
| `ICH-Q9-RSK-001` | MEDIUM | `risks` | `RSK-2024-11` (Gap 3: review >12 months stale) |
| `ANNEX11-S13-INC-001` | HIGH | `incidents` | `INC-849201` (Gap 4: P1 open 47 days, no RCA) |
| `ANNEX11-S4-TRC-001` | HIGH | `requirements` + `test_cases` | `URS-042` / `TC-2026-042` (Gap 5: DRAFT test evidence) |
| `ANNEX11-S3-SUP-001` | MEDIUM | `suppliers` | `SUP-2026-01` (Gap 6: reassessment overdue) |
| `ANNEX11-S11-PE-001` | HIGH | `periodic_evaluations` | `PE-2024-01` (Gap 7: overdue 24 months) |
| `ANNEX11-S16-BCK-001` | HIGH | `gxp_systems` | `GXP-MFG-DEMO-01.last_backup_test_ns` (Gap 8: stale backup test) |
| `ANNEX11-S12-ACC-002` | **CRITICAL** | `access_records` | `ACC-2026-99` (Gap 9: privileged account, departed user) |
| `ANNEX11-S10-CHG-001` | HIGH | `changes` + `change_actions` | `CR-2026-089` / `CA-2026-089-1` (Gap 10: closed change, open action) |

**Running the gate:** `bash policies/opa-gate.sh` runs the `opa test` unit suite (42 fixtures — unit, negative, threshold-boundary, absent-key, absent-field, whole-bundle-integration, and healthy-system coverage) and a live REST probe against the running `opa` container, then prints `OPA GATE OK` / `OPA GATE FAILED`.

**Restart after every edit:** `docker-compose.yml` runs the `opa` service as `opa run --server /policies` with no `--watch` flag, so the live server only loads the bundle once at container start. Any edit to `policies/*.rego` requires `docker compose restart opa && bash infra/health-check.sh opa` before a REST-level check (including `opa-gate.sh`'s live-probe leg) will reflect it.

**Why tests live in a separate package:** `policies/gxp_rules_test.rego` declares `package sentinel.gxp_test`, not `package sentinel.gxp`. `opa run --server /policies` loads every `.rego` file in this tree, so test rules written directly into `package sentinel.gxp` would surface as extra keys under the live `/v1/data/sentinel/gxp` response and pollute the exact data path `evaluate_opa_policy()` (plan 02-05) reads. The sibling `_test` package keeps that response surface to a single `violation` key while `opa test policies/` still discovers and runs every test.
