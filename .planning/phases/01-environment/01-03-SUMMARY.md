---
phase: 01-environment
plan: "03"
subsystem: infra
tags: [docker-compose, qdrant, opa, healthcheck, environment]

requires:
  - phase: 01-environment (plan 01-01)
    provides: "root docker-compose.yml with postgres service, infra/health-check.sh gate, .env/.env.example pattern"
  - phase: 01-environment (plan 01-02)
    provides: "policies/ directory (D-01 tier, committed, mount target for OPA)"
provides:
  - "docker-compose.yml qdrant service — built from infra/qdrant, curl-capable derived image, healthy on 127.0.0.1:6333, qdrant_data named volume"
  - "docker-compose.yml opa service — built from infra/opa (fallback derived image), healthy on 127.0.0.1:8181, ./policies mounted read-only"
  - "infra/qdrant/Dockerfile — curl-capable derived Qdrant image"
  - "infra/opa/Dockerfile — curl-capable derived OPA image (named fallback, RESEARCH.md A1 disproven)"
  - "all three ENV-01 services (postgres, qdrant, opa) pass bash infra/health-check.sh with no arguments"
affects:
  - "01-04 (infra/verify-persistence.sh and infra/README.md will document/exercise the qdrant_data volume and full up/down lifecycle this plan completed)"
  - "Phase 2 SENT-1-03 (Rego rules land in policies/, the read-only mount this plan proved live)"

actuals:
  tokens: 1000
  tasks: 2
  commits: 2

tech-stack:
  added:
    - "qdrant/qdrant:v1.19.0 (Docker image, pinned exact tag)"
    - "openpolicyagent/opa:1.19.1-debug (Docker image, pinned exact tag, as build base)"
    - "cgr.dev/chainguard/curl (Docker image, digest-pinned, build-time-only donor image for OPA's curl binary)"
  patterns:
    - "Derived-image pattern for healthcheck-capable containers: FROM <vendor pinned tag> + minimal HTTP-client layer, referenced via Compose build: context rather than a bare image: reference"
    - "Cross-Chainguard-image COPY (COPY --from=<donor> / /) as the fallback pattern when the target base has no package manager at all (not just no HTTP client) — works because both images share the same Wolfi/glibc ABI"

key-files:
  created:
    - infra/qdrant/Dockerfile
    - infra/opa/Dockerfile
  modified:
    - docker-compose.yml

key-decisions:
  - "RESEARCH.md Assumption A1 (OPA's -debug tag ships a working wget applet) was runtime-verified FALSE: the busybox build in openpolicyagent/opa:1.19.1-debug has no wget/curl/nc applet at all, and the image has no apk binary (despite /etc/apk metadata being present) to install one — so the plan's own named fallback was triggered"
  - "Fallback implementation used a cross-Chainguard-image COPY (COPY --from=cgr.dev/chainguard/curl / /) rather than an apt-get-style package install, because the OPA base (Wolfi, via chainguard/busybox) has no package manager reachable at build time either — this differs from the plan's literal wording ('installing an HTTP client the same way infra/qdrant/Dockerfile does') but satisfies its intent (OPA's own ENTRYPOINT and runtime user verified unchanged after the copy)"
  - "cgr.dev/chainguard/curl pinned by SHA256 digest, not a tag — Chainguard's free-tier registry only publishes a rolling :latest tag for this image (versioned tags require a paid subscription), so a digest pin is the only mechanism available to satisfy D-04's exact-reproducibility intent for this build-time-only donor image"

requirements-completed: [ENV-01]

coverage:
  - id: D1
    description: "Qdrant v1.19.0 runs from a locally built curl-capable derived image, reports healthy to Compose via a real /readyz HTTP probe, answers on 127.0.0.1:6333 only, persists to the qdrant_data named volume"
    requirement: "ENV-01"
    verification:
      - kind: integration
        ref: "docker inspect .State.Health.Status == healthy; docker inspect .NetworkSettings.Ports shows 127.0.0.1 only; node fetch http://127.0.0.1:6333/readyz returns 200; docker volume ls shows gxp-sentinel_qdrant_data"
        status: pass
    human_judgment: false
  - id: D2
    description: "OPA 1.19.1-debug (via fallback derived image) runs healthy, serves ./policies read-only on 127.0.0.1:8181, and bash infra/health-check.sh with no args reports ALL HEALTHY for all three ENV-01 services"
    requirement: "ENV-01"
    verification:
      - kind: integration
        ref: "docker inspect .State.Health.Status == healthy; docker inspect .NetworkSettings.Ports shows 127.0.0.1 only; node fetch http://127.0.0.1:8181/health returns 200; docker compose exec -T opa sh -c 'touch /policies/should_fail' exits non-zero; bash infra/health-check.sh (no args) exits 0 and prints ALL HEALTHY"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-08-20
status: complete
---

# Phase 1 Plan 03: Qdrant + OPA Up Healthy Summary

Expanded the ENV-01 one-command bring-up to all three services: added a curl-capable derived Qdrant image (`infra/qdrant/Dockerfile`) and, after the OPA `-debug` tag's assumed `wget` applet turned out not to exist at all, a fallback derived OPA image (`infra/opa/Dockerfile`) built by copying a digest-pinned Chainguard `curl` image's rootfs onto the same Wolfi base — both now report `healthy` to Compose via real HTTP probes, and `bash infra/health-check.sh` with no arguments prints `ALL HEALTHY` for postgres, qdrant, and opa together.

## Performance

- **Duration:** 25 min
- **Started:** 2026-08-20T13:35:00Z (approx, first precondition check)
- **Completed:** 2026-08-20
- **Tasks:** 2
- **Files modified:** 3 (1 modified, 2 created)

## Accomplishments

- Qdrant v1.19.0 up healthy end-to-end from a locally built, curl-capable derived image, answering only on `127.0.0.1:6333`, persisting to the `qdrant_data` named volume
- OPA 1.19.1-debug up healthy end-to-end (via a named fallback derived image, since the assumed `wget` applet did not exist), answering only on `127.0.0.1:8181`, serving `./policies` as a genuinely read-only bundle root
- `bash infra/health-check.sh` with no arguments now covers and passes the full ENV-01 set: postgres, qdrant, opa

## Task Commits

1. **Task 1: Qdrant up healthy end-to-end on a curl-capable derived image** — `d61ad97` (feat)
2. **Task 2: OPA up healthy end-to-end serving the read-only policy bundle mount** — `2dbe06c` (feat)

**Plan metadata:** (this commit, pending)

## Files Created/Modified

- `infra/qdrant/Dockerfile` - Derived `FROM qdrant/qdrant:v1.19.0` image adding curl (`--no-install-recommends`, apt lists cleaned in the same layer); vendor's `Config.User` (`0:0`) preserved exactly, verified by `docker image inspect` before writing the Dockerfile
- `infra/opa/Dockerfile` - Fallback derived `FROM openpolicyagent/opa:1.19.1-debug` image; multi-stage `COPY --from=curltool / /` from a digest-pinned `cgr.dev/chainguard/curl` (same Wolfi base, ABI-compatible); OPA's own `ENTRYPOINT ["/opa"]` and runtime user (`1000:1000`) verified unchanged after the copy
- `docker-compose.yml` - Added `qdrant` service (`build: context: ./infra/qdrant`, loopback-only `6333` publish, `qdrant_data` volume, `/readyz` healthcheck) and `opa` service (`build: context: ./infra/opa`, loopback-only `8181` publish, `./policies:/policies:ro`, `/health` curl healthcheck, explicit `--addr=0.0.0.0:8181`); added `qdrant_data` to the top-level `volumes:` block

## Decisions Made

- **OPA pre-flight result (settles RESEARCH.md Assumption A1): the `-debug` tag's busybox has NO wget applet, no curl, no nc, and no package manager reachable at build time.** Ran the plan's prescribed pre-flight (`docker run --rm --entrypoint wget openpolicyagent/opa:1.19.1-debug --help`) — it failed with `exec: "wget": executable file not found in $PATH`. Further investigation (`busybox --list` inside the container) confirmed no HTTP or raw-socket applet exists in this specific busybox build at all, and `apk --version` reported `apk: not found` despite `/etc/apk` metadata being present in the image (the image was built via `apko` without leaving the `apk` tool inside — standard Chainguard/Wolfi distroless behavior). This ruled out the plan's literal fallback wording ("installing an HTTP client the same way infra/qdrant/Dockerfile does" — i.e. `apt-get install curl`), since there is no package manager to invoke.
- **Fallback implementation: cross-Chainguard-image COPY instead of a package install.** Used a multi-stage `Dockerfile` (`FROM cgr.dev/chainguard/curl@sha256:... AS curltool` / `FROM openpolicyagent/opa:1.19.1-debug` / `COPY --from=curltool / /`), because Chainguard's own `curl` image is built from the same Wolfi distribution as `openpolicyagent/opa`, making its curl binary and shared libraries ABI-compatible with the target. Verified after the copy that OPA's own `ENTRYPOINT` (`/opa`) and runtime user (`1000:1000`) were unchanged — the derived image adds curl without altering OPA's own binary or privilege posture.
- **Digest-pinned the donor curl image rather than a version tag.** `cgr.dev/chainguard/curl` only publishes a rolling `:latest` tag on Chainguard's free tier (no versioned tags without a paid subscription). Pinned to the exact digest pulled this session (`sha256:8cb68f34d752c6d0136bf9f64ae8a03e0eafc0933e53271307d3ee0889b979bc`) to satisfy D-04's exact-reproducibility intent for this build-time-only donor image — `grep -c ':latest' docker-compose.yml` remains 0, and the Dockerfile itself carries no floating tag either.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] OPA `-debug` tag has no HTTP client AND no package manager — plan's literal fallback wording ("apt-get-style install") did not apply**
- **Found during:** Task 2, running the prescribed pre-flight check
- **Issue:** The plan's named fallback assumed the same `apt-get install curl` pattern used for Qdrant would work for OPA too. Investigation showed the OPA `-debug` base (Wolfi via `chainguard/busybox`) has no package manager binary reachable at build time at all (`apk: not found`, despite `/etc/apk` metadata existing), so no in-container package install is possible against this base.
- **Fix:** Used a multi-stage Dockerfile that `COPY --from=`s a full working curl binary + its shared libraries from a separate, purpose-built Chainguard `curl` image built on the same Wolfi distribution — verified working by test-building and running `curl --version` before applying it to the real Dockerfile, and by confirming OPA's own `ENTRYPOINT`/`USER` were unchanged afterward.
- **Files modified:** `infra/opa/Dockerfile`
- **Commit:** `2dbe06c`

**2. [Rule 3 - Blocking issue] Acceptance criterion `grep -c 'openpolicyagent/opa:1.19.1-debug' docker-compose.yml == 1` no longer applies once the fallback (build: context) path was taken**
- **Found during:** Task 2, adapting the plan's automated `<verify>` line after the fallback was confirmed necessary
- **Issue:** The plan's acceptance criteria and `<verify>` script were written for the primary path (`image: openpolicyagent/opa:1.19.1-debug` directly in docker-compose.yml). Once the service switched to `build: context: ./infra/opa` per the plan's own fallback instructions, the tag reference moved into `infra/opa/Dockerfile` and the literal grep against `docker-compose.yml` no longer matches — this is an artifact of the plan text not being updated for its own fallback branch, not a new issue introduced by this plan.
- **Fix:** Verified the equivalent intent directly: `grep -n 'FROM openpolicyagent/opa:1.19.1-debug' infra/opa/Dockerfile` returns exactly one match, `grep -c ':latest' docker-compose.yml` is still 0, and every other Task 2 acceptance criterion (healthy status, loopback-only port, read-only mount, full health-check gate) was run and passed exactly as written.
- **Files modified:** none (verification-only adaptation, documented here for traceability)
- **Commit:** n/a (no code change — verification method substitution)

---

**Total deviations:** 2 auto-fixed (both Rule 3 - blocking issues arising from the same root cause: RESEARCH.md's Assumption A1 was disproven at implementation time)
**Impact on plan:** Both deviations are contained entirely within Task 2's already-anticipated fallback branch (the plan explicitly named "the same derived-image pattern" as the contingency and asked for the pre-flight result to be settled in this SUMMARY). No scope creep — no new service, no new persistent state, no architectural change.

## Issues Encountered

- The `docker inspect -f '{{...}}' "$(docker compose ps -q <svc>)"` command-substitution form triggered the worktree-isolation safety guard on complex commands; resolved by splitting each check into two plain commands (get the container ID, then inspect it) — no functional impact, just a verification-workflow adjustment.
- Git Bash's automatic path-mangling turned `--entrypoint sh` into a Windows path when double-slash-escaped; resolved by using the plain `sh` entrypoint name (Docker's own path handling was fine; only the doubled-slash workaround attempt was the problem).

## User Setup Required

None - no external service configuration required. `.env` (gitignored, not committed) was created locally in this worktree only to satisfy the Task 1 precondition check (`bash infra/health-check.sh postgres` exiting 0) inherited from plan 01-01; it is not part of this plan's deliverables and was not modified beyond the existing `.env.example` template's documented keys.

## Threat Flags

| Flag | File | Description |
|------|------|--------------|
| threat_flag: new-build-surface | `infra/opa/Dockerfile` | The plan's `<threat_model>` (T-01-SC) covers only Debian package mirrors as a build-time trust boundary for `infra/qdrant/Dockerfile`. The OPA fallback introduces a second, different build-time supply-chain dependency: `cgr.dev/chainguard/curl`, a third-party registry namespace not previously pulled into this environment. Mitigated the same way as T-01-SC's intent — pinned by exact SHA256 digest (not `:latest`), sourced from Chainguard's own published namespace (not a fork), and its only effect is adding a static binary + shared libs at build time; it is not present in any runtime request path (OPA's own binary/entrypoint/user were verified unchanged after the copy). Recommend folding this into the phase's threat register if plan 01-04 or a later security-focused phase revisits Phase 1's STRIDE coverage. |

## Next Phase Readiness

- All three ENV-01 services (postgres, qdrant, opa) are healthy under Compose's own health state, each with a real native healthcheck whose probe binary is proven present, not assumed
- `./policies` is served to OPA read-only and ready for SENT-1-03's Rego bundle (Phase 2)
- `bash infra/health-check.sh` with no arguments is the single mechanical ENV-01 gate for the full service set
- Plan 01-04 (persistence verification script + `infra/README.md`) can now exercise the complete `docker-compose down` / `down -v` lifecycle against all three named-volume-backed services

## Self-Check: PASSED

Files verified to exist:
- FOUND: `infra/qdrant/Dockerfile`
- FOUND: `infra/opa/Dockerfile`
- FOUND: `docker-compose.yml`

Commits verified in `git log`:
- FOUND: `d61ad97` — feat(01-03): bring Qdrant up healthy via curl-capable derived image
- FOUND: `2dbe06c` — feat(01-03): bring OPA up healthy serving the read-only policy bundle mount

Live re-verification at summary time: `docker compose config --quiet` OK, `docker compose up -d --wait --wait-timeout 180 postgres qdrant opa` reports all three `Healthy`, `bash infra/health-check.sh` (no args) → `ALL HEALTHY` (exit 0), `docker compose exec -T opa sh -c 'touch /policies/should_fail'` fails (read-only confirmed), `grep -c ':latest' docker-compose.yml` is 0.

---
*Phase: 01-environment*
*Completed: 2026-08-20*
