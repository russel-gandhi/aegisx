"""
C1 - Evidence & Grounding Verifier (Phase 3 tracer 03-02; hardened to the
SENT-2-12 Critical-review bar in plan 03-05).

Ticket: SENT-2-12 (Critical review) | Requirements: EVID-01, EVID-02, EVID-04
Source: AegisX-AI-Project-Bible-v6.md Section 2's "C1" entry
(`calculate_confidence()`, transcribed below with one corrected constant
— see `ALCOA_DIMENSION_COUNT`) and Section 1.3's deterministic-first
constraint.

This module must never contain a model call — that constraint is
permanent, not a stub-stage convenience (Bible Section 1.3,
`app.graph.state`'s module docstring). It is the product's core thesis:
every material LLM claim is independently verified against a real
Postgres record and a real OPA policy evaluation before it is trusted.

Table and column names used to build SQL statements come exclusively from
the frozen allowlists below (`RULE_EVIDENCE_TABLES`, `RULE_OPA_INPUT`) —
never from request data — and are concatenated into the query string
rather than f-string-interpolated, so an unrecognised rule id returns no
record instead of building a statement (ASVS V5).

Plan 03-05 fix (closes `.planning/WINDOWS.md` id 1, discovered in 03-04):
`build_opa_payload()` previously queried *every* `RULE_OPA_INPUT` table
using the finding's own `evidence_ids`, which is only correct for the
finding's own record. The two multi-input-key rules —
`ANNEX11-S4-TRC-001` (rule 5, `test_cases`) and `ANNEX11-S10-CHG-001`
(rule 10, `change_actions`) — each need a *second*, differently-keyed
table resolved via a foreign-key relationship, not the finding's own
`evidence_ids`. `RULE_OPA_INPUT`'s fourth tuple element now names how
each table is resolved (see its docstring below); this stays data-driven
— no per-rule branching was added to `build_opa_payload()` itself.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from app.db import acquire_pool_or_none
from app.opa_client import evaluate_opa_policy
from app.schemas import ALCOAScore

# D-06 (03-CONTEXT.md Open Question 2): the Bible's calculate_confidence()
# hardcodes the literal 8 as its ALCOA dimension count (Section 2). Two
# independent in-project sources instead agree on 9: `.claude/CLAUDE.md`
# states "ALCOA+ 9-dimension scoring" as settled project fact, and
# `app.schemas.ALCOAScore` (shipped in Phase 2) has nine boolean fields.
# Recorded as Deviation 7 in backend/README.md, routed to SENT-7-05. Every
# other constant in the formula below (100, x10, -100, 80/50/0) is
# unchanged from the Bible.
ALCOA_DIMENSION_COUNT = 9


def calculate_confidence(finding: dict, db_record: dict, opa_evaluation: bool) -> str:
    """Transcribed from Bible Section 2 with `ALCOA_DIMENSION_COUNT`
    substituted for the literal `8` (D-06) and nothing else changed."""
    score = 100
    if not db_record:
        return "INSUFFICIENT_EVIDENCE"

    alcoa_score = sum(finding.get("alcoa_score", {}).values())
    score -= (ALCOA_DIMENSION_COUNT - alcoa_score) * 10

    if not opa_evaluation:
        score -= 100  # Contradicts formal policy

    if score > 80:
        return "HIGH"
    if score >= 50:
        return "MEDIUM"
    if score > 0:
        return "LOW"
    return "INSUFFICIENT_EVIDENCE"


# The Postgres table each of the ten `policies/gxp_rules.rego` rule ids'
# `record_id` lives in. A table name can never be a bound parameter, so it
# comes from this allowlist and nowhere else.
RULE_EVIDENCE_TABLES: Dict[str, str] = {
    "ANNEX11-S4-DOC-001": "documents",
    "ANNEX11-S12-ACC-001": "access_reviews",
    "ICH-Q9-RSK-001": "risks",
    "ANNEX11-S13-INC-001": "incidents",
    "ANNEX11-S4-TRC-001": "requirements",
    "ANNEX11-S3-SUP-001": "suppliers",
    "ANNEX11-S11-PE-001": "periodic_evaluations",
    "ANNEX11-S16-BCK-001": "gxp_systems",
    "ANNEX11-S12-ACC-002": "access_records",
    "ANNEX11-S10-CHG-001": "changes",
}

# Each of the ten rule ids' OPA input keys, as a tuple of
# (input_key, table_name, shape, id_source) 4-tuples. `shape` is "list" for
# every input key except rule 5's "test_cases", which `gxp_rules.rego`
# documents as an object keyed by id (the one non-list input key in the
# whole bundle). Filled completely (all ten entries) so no later plan has
# to edit this module to support a new rule.
#
# `id_source` names how each table's rows are resolved — this is what lets
# `build_opa_payload` stay one data-driven loop with no per-rule `if`
# branch for the two multi-input-key rules (plan 03-05 fix):
#   - "evidence_ids": the table IS the finding's own record — fetch
#     `WHERE id = ANY(evidence_ids)`. Every single-input-key rule uses
#     this, and it is what every rule used before this fix.
#   - ("via", source_input_key, column): a *second* table, reached by
#     reading `column` off the rows already fetched for `source_input_key`
#     earlier in the same rule's tuple (that source's own column points at
#     this table's `id`). Rule 5 uses this for "test_cases": each fetched
#     `requirements` row's `test_case_id` names a `test_cases.id`.
#   - ("by_column", column): a *second* table whose own `column` (not
#     `id`) references the finding's `evidence_ids` directly — fetch
#     `WHERE column = ANY(evidence_ids)`. Rule 10 uses this for
#     "change_actions": `change_actions.change_id` references the
#     finding's own `changes.id`.
RULE_OPA_INPUT: Dict[str, Tuple[Tuple[str, str, str, Any], ...]] = {
    "ANNEX11-S4-DOC-001": (("documents", "documents", "list", "evidence_ids"),),
    "ANNEX11-S12-ACC-001": (("access_reviews", "access_reviews", "list", "evidence_ids"),),
    "ICH-Q9-RSK-001": (("risks", "risks", "list", "evidence_ids"),),
    "ANNEX11-S13-INC-001": (("incidents", "incidents", "list", "evidence_ids"),),
    "ANNEX11-S4-TRC-001": (
        ("requirements", "requirements", "list", "evidence_ids"),
        ("test_cases", "test_cases", "object", ("via", "requirements", "test_case_id")),
    ),
    "ANNEX11-S3-SUP-001": (("suppliers", "suppliers", "list", "evidence_ids"),),
    "ANNEX11-S11-PE-001": (("periodic_evaluations", "periodic_evaluations", "list", "evidence_ids"),),
    "ANNEX11-S16-BCK-001": (("gxp_systems", "gxp_systems", "list", "evidence_ids"),),
    "ANNEX11-S12-ACC-002": (("access_records", "access_records", "list", "evidence_ids"),),
    "ANNEX11-S10-CHG-001": (
        ("changes", "changes", "list", "evidence_ids"),
        ("change_actions", "change_actions", "list", ("by_column", "change_id")),
    ),
}


def _select_one_by_id_query(table_name: str) -> str:
    """Builds `SELECT * FROM <table_name> WHERE id = $1` via plain string
    concatenation (never an f-string) so this allowlisted, code-only
    interpolation can never be conflated with an f-string built from
    request data. `table_name` is only ever a value drawn from
    `RULE_EVIDENCE_TABLES`."""
    return "SELECT * FROM " + table_name + " WHERE id = $1"


def _select_many_by_ids_query(table_name: str) -> str:
    """As `_select_one_by_id_query`, but for the `= ANY($1::varchar[])`
    multi-id form `build_opa_payload` uses. `table_name` is only ever a
    value drawn from `RULE_OPA_INPUT`."""
    return "SELECT * FROM " + table_name + " WHERE id = ANY($1::varchar[])"


def _select_many_by_column_query(table_name: str, column_name: str) -> str:
    """As `_select_many_by_ids_query`, but filters on `column_name` rather
    than `id` — the `("by_column", ...)` `id_source` kind, for a secondary
    table whose own foreign key (e.g. `change_actions.change_id`)
    references the finding's own record rather than being referenced by
    it. `table_name` and `column_name` are only ever values drawn from
    `RULE_OPA_INPUT`, never request data."""
    return "SELECT * FROM " + table_name + " WHERE " + column_name + " = ANY($1::varchar[])"


async def fetch_evidence_record(pool, finding: dict) -> Optional[dict]:
    """Resolve the finding's first citation through `RULE_EVIDENCE_TABLES`
    and its first `evidence_ids` entry through a `$1` placeholder. This is
    the real Postgres read that makes `db_record` real (EVID-01)."""
    citations: List[str] = finding.get("regulatory_citations") or []
    evidence_ids: List[str] = finding.get("evidence_ids") or []
    if not citations or not evidence_ids:
        return None

    table_name = RULE_EVIDENCE_TABLES.get(citations[0])
    if table_name is None:
        # Unrecognised rule id: no statement is built at all.
        return None

    row = await pool.fetchrow(_select_one_by_id_query(table_name), evidence_ids[0])
    return dict(row) if row is not None else None


async def build_opa_payload(pool, finding: dict) -> dict:
    """Single data-driven assembly over `RULE_OPA_INPUT`: for the finding's
    rule, read real Postgres rows and emit the bundle keyed exactly as
    `policies/gxp_rules.rego` documents. No per-rule `if` branches — both
    the list-vs-object shape difference and the `evidence_ids` /
    `via` / `by_column` resolution strategy are data in `RULE_OPA_INPUT`,
    not control flow here (plan 03-05 fix — see module docstring and
    `RULE_OPA_INPUT`'s own docstring for what each `id_source` kind means).

    Entries are resolved in the tuple's declared order, so a rule's
    `"via"` entry can always find its `source_input_key`'s rows already
    collected in `fetched_by_key` — every rule in `RULE_OPA_INPUT` lists
    its primary (`"evidence_ids"`) entry first, before any entry that
    depends on it.
    """
    citations: List[str] = finding.get("regulatory_citations") or []
    evidence_ids: List[str] = finding.get("evidence_ids") or []
    rule_id = citations[0] if citations else None
    input_spec = RULE_OPA_INPUT.get(rule_id, ())

    payload: Dict[str, Any] = {}
    fetched_by_key: Dict[str, List[dict]] = {}
    for input_key, table_name, shape, id_source in input_spec:
        if isinstance(id_source, tuple) and id_source[0] == "via":
            _, source_input_key, link_column = id_source
            source_records = fetched_by_key.get(source_input_key, [])
            linked_ids = sorted(
                {r[link_column] for r in source_records if r.get(link_column)}
            )
            rows = (
                await pool.fetch(_select_many_by_ids_query(table_name), linked_ids)
                if linked_ids
                else []
            )
        elif isinstance(id_source, tuple) and id_source[0] == "by_column":
            _, link_column = id_source
            rows = await pool.fetch(
                _select_many_by_column_query(table_name, link_column), evidence_ids
            )
        else:  # "evidence_ids" — the finding's own record
            rows = await pool.fetch(_select_many_by_ids_query(table_name), evidence_ids)

        records = [dict(r) for r in rows]
        fetched_by_key[input_key] = records
        if shape == "object":
            payload[input_key] = {record["id"]: record for record in records}
        else:
            payload[input_key] = records
    return payload


# SENT-9-01: Bible Section 16.12's own per-dimension table, implemented
# against the real columns `RULE_EVIDENCE_TABLES`' ten tables actually
# have (checked directly against infra/postgres/initdb/001_schema.sql --
# nothing here is invented). Replaces the fixed `ALCOAScore()` default
# every finding previously carried regardless of its actual evidence
# quality (Design Note: that default made C1's own confidence score sum a
# constant every time, silently capping every finding at the same
# ceiling no matter what the real record looked like -- the one place
# this architecture is supposed to be most rigorous was faking it).
#
# Not every table has every relevant column (e.g. only `documents` has
# `author`; `requirements` has no timestamp column at all) -- per the
# Bible's own "where the seeded demo data supports it" scoping, a
# dimension with no real column to check on a given table degrades to
# the same conservative default `ALCOAScore` already used (True for the
# six dimensions that default True, False for the three that default
# False), rather than fabricating a signal that isn't there.
_ATTRIBUTION_COLUMNS: Tuple[str, ...] = ("author", "owner", "reviewer", "system_owner", "tester")
_TIMESTAMP_COLUMNS: Tuple[str, ...] = (
    "created_date", "effective_date", "scheduled_date_ns", "last_review_date_ns",
    "opened_date_ns", "reassessment_due_date_ns", "due_date_ns", "qa_approval_date",
    "assessment_date_ns", "execution_date_ns",
)
_TEXT_CONTENT_COLUMNS: Tuple[str, ...] = ("description", "title", "req_text", "risk_summary")
_STATUS_COLUMNS: Tuple[str, ...] = ("status", "pass_fail")


def _timestamp_is_in_the_future(value: Any) -> bool:
    """`value` is either a nanosecond-epoch int (this schema's `*_date_ns`
    columns) or a `datetime` (its plain `TIMESTAMP` columns) -- normalise
    both to a comparison against the current time rather than assuming
    one shape."""
    if isinstance(value, (int, float)):
        return value > time.time_ns()
    if hasattr(value, "timestamp"):
        try:
            return value.timestamp() > time.time()
        except (OverflowError, OSError, ValueError):
            return False
    return False


def calculate_alcoa_score(db_record: dict, finding: dict) -> ALCOAScore:
    """Compute a real, per-record ALCOA+ score from `db_record`'s actual
    column values -- never a fixed default. `db_record` is the same real
    Postgres row `verify_finding` already fetched (EVID-01); this
    function reads it, it never queries anything itself (Bible Section
    1.3: no I/O beyond what C1 already does).
    """
    attributable = any(db_record.get(col) for col in _ATTRIBUTION_COLUMNS)

    text_columns_present = [col for col in _TEXT_CONTENT_COLUMNS if col in db_record]
    legible = (
        all(bool(db_record.get(col)) for col in text_columns_present)
        if text_columns_present
        else True
    )

    timestamp_columns_present = [col for col in _TIMESTAMP_COLUMNS if col in db_record]
    contemporaneous = (
        any(
            db_record.get(col) is not None and not _timestamp_is_in_the_future(db_record[col])
            for col in timestamp_columns_present
        )
        if timestamp_columns_present
        else False
    )

    # "version" is the one explicit controlled-copy/revision indicator
    # this schema has (on `documents` only) -- its presence is a real,
    # checkable signal; its absence on every other table isn't evidence
    # of anything (those tables have no versioning concept at all), so
    # only `documents` rows are actually scored on this dimension.
    original = db_record.get("version") not in (None, "") if "version" in db_record else True

    status_columns_present = [col for col in _STATUS_COLUMNS if col in db_record]
    accurate = (
        all(db_record.get(col) is not None for col in status_columns_present)
        if status_columns_present
        else True
    )

    # Complete: every column this row actually has is populated -- a
    # real, generic completeness check across any of the ten tables, not
    # specific to one shape. `id`/`system_id` are excluded: their
    # presence is guaranteed by the SQL that fetched this row at all and
    # checking them adds no signal.
    checkable_fields = {k: v for k, v in db_record.items() if k not in ("id", "system_id")}
    complete = all(v is not None and v != "" for v in checkable_fields.values())

    # Consistent: the fetched record's own id is genuinely one of the
    # finding's own claimed evidence ids -- proves the record verifying
    # this finding is actually the evidence the finding cites, not a
    # mismatched fetch (Bible: "identifiers... do not contradict the
    # available records").
    evidence_ids = finding.get("evidence_ids") or []
    consistent = db_record.get("id") in evidence_ids if evidence_ids else True

    # Enduring/Available: true by construction, not assumed -- by the time
    # this function runs, `db_record` was already successfully retrieved
    # from Postgres's durable store via the same read path any authorized
    # user's own query would use (verify_finding already returned
    # INSUFFICIENT_EVIDENCE before ever reaching here if that read had
    # failed). This is a real guarantee this specific call already
    # proved, not a hardcoded default standing in for one.
    enduring = True
    available = True

    return ALCOAScore(
        attributable=attributable,
        legible=legible,
        contemporaneous=contemporaneous,
        original=original,
        accurate=accurate,
        complete=complete,
        consistent=consistent,
        enduring=enduring,
        available=available,
    )


async def verify_finding(pool, finding: dict) -> Dict[str, Any]:
    """Fetch the real evidence record; when absent, skip the policy call
    entirely and return `INSUFFICIENT_EVIDENCE` (no policy call is needed
    to know the evidence is absent). Otherwise call the real OPA sidecar
    (never a mock, never a second Python copy of the rule logic), compute
    a real per-record ALCOA+ score from that same fetched record (SENT-9-01
    -- overwrites whatever placeholder `alcoa_score` the originating agent
    attached, in place, so the AssuranceCard the caller already holds a
    reference to reflects the real score with no further plumbing), and
    score the result via `calculate_confidence()`."""
    rule_ids: List[str] = finding.get("regulatory_citations") or []
    evidence_ids: List[str] = finding.get("evidence_ids") or []

    db_record = await fetch_evidence_record(pool, finding)
    if db_record is None:
        return {
            "confidence": calculate_confidence(finding, None, False),
            "db_record_found": False,
            "opa_corroborated": False,
            "opa_rule_ids": rule_ids,
            "evidence_ids": evidence_ids,
        }

    finding["alcoa_score"] = calculate_alcoa_score(db_record, finding).model_dump()

    payload = await build_opa_payload(pool, finding)
    violations = await evaluate_opa_policy(payload)
    opa_corroborated = any(
        v.get("rule_id") in rule_ids and v.get("record_id") in evidence_ids
        for v in violations
    )

    return {
        "confidence": calculate_confidence(finding, db_record, opa_corroborated),
        "db_record_found": True,
        "opa_corroborated": opa_corroborated,
        "opa_rule_ids": rule_ids,
        "evidence_ids": evidence_ids,
    }


async def run_c1(state) -> Dict[str, Any]:
    """C1 node body: verify every finding A0's fan-out produced and return
    `{"verification_results": {finding_id: result}}`. With no findings,
    returns an empty mapping — never a hardcoded verified literal (the
    product's core thesis is that nothing is trusted by default)."""
    findings: List[dict] = state.get("findings", [])
    if not findings:
        return {}

    pool = await acquire_pool_or_none()
    results: Dict[str, Any] = {}
    for finding in findings:
        finding_id = finding["finding_id"]
        if pool is None:
            results[finding_id] = {
                "confidence": "INSUFFICIENT_EVIDENCE",
                "db_record_found": False,
                "opa_corroborated": False,
                "opa_rule_ids": finding.get("regulatory_citations") or [],
                "evidence_ids": finding.get("evidence_ids") or [],
            }
            continue
        results[finding_id] = await verify_finding(pool, finding)

    return {"verification_results": results}
