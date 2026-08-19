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
