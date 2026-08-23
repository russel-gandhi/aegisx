"""
Hash-chained append-only audit trail (Phase 5, plan 05-01).

Ticket: SENT-4-06 | Requirement: AUDIT-01, AUDIT-02 | Source: Bible
Section 7.1's `AuditLogger`

The algorithm below is transcribed from Bible Section 7.1 (`log_event`,
`verify_chain`), with two deliberate corrections to make the write side
and the read side hash byte-identical bytes over an already-migrated,
real `audit_events` table. Both corrections are routed to SENT-7-05 for
AegisX-AI-Project-Bible-v6.md reconciliation:

1. **JSONB round-trip normalisation** (05-RESEARCH.md Pitfall 2).
   `asyncpg` returns `JSONB` columns (`evidence_ids`, `opa_rule_ids`) as
   raw JSON *text*, not parsed Python objects, unless a custom type codec
   is registered on the connection (this codebase has not registered
   one -- confirmed by `backend/app/routes/evidence_graph.py`'s own
   `isinstance(properties, str): properties = json.loads(properties)`
   workaround). The Bible's own `verify_chain()` example does `dict(row)`
   and hashes it directly, silently assuming `asyncpg` already returns
   parsed objects -- it does not. `_normalise_list_field` below applies
   the identical normalisation `evidence_graph.py` already established
   as this codebase's pattern for this exact asyncpg behaviour, on BOTH
   the write side (`log_event`) and the read side (`verify_chain`), so a
   row's hash never depends on whether the value happened to arrive as a
   native Python list or as JSON text.

2. **Canonical field list, not "whatever keys happened to be passed"**
   (05-RESEARCH.md Pitfall 2). The Bible's `canonical_data` build is
   `{k: v for k, v in event_data.items() if k not in (...)}` on the write
   side and `dict(row)` (all eighteen columns) on the read side. A caller
   omitting an optional key (e.g. `model_id`, `approval_id`,
   `target_record_id`) therefore produces two different key sets for one
   logical event -- the write side's dict has fewer keys than the read
   side's full-row dict, so `json.dumps(..., sort_keys=True)` never
   agrees between the two, and every legitimate row reports TAMPERED even
   though nothing was tampered. `CANONICAL_FIELDS` fixes both sides to
   drive off exactly the same fourteen-field list, via `.get(field)`
   (which returns `None` for a genuinely absent key, not a `KeyError`),
   so the two sides are always byte-identical.

This module never contains a model call -- that constraint is permanent
(Bible Section 1.3). `log_event`/`verify_chain` both take an explicit
`pool` argument rather than acquiring one internally, matching
`c1_verifier.verify_finding(pool, finding)`'s shape; callers use
`acquire_pool_or_none()` and handle `None` themselves.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Tuple

# Bible Section 7.1: `self.genesis_hash = "0000...0000"`. Independently
# verified to be exactly 64 characters (matches both a sha256 hexdigest
# length and the `event_hash VARCHAR(64)` / `previous_event_hash
# VARCHAR(64)` columns) -- see 05-RESEARCH.md Code Examples note.
GENESIS_HASH: str = "0" * 64

# The fourteen `audit_events` columns that participate in the hash, in a
# fixed order (order does not affect the JSON bytes since `_canonical_json`
# always sorts keys, but a fixed order here keeps this list readable and
# diffable). The four excluded columns -- `event_id`, `timestamp_utc`,
# `event_hash`, `previous_event_hash` -- are excluded per Bible Section
# 7.1's own `canonical_data` construction (they are either the row's own
# identity/ordering or the hash values being computed, not data the hash
# covers).
CANONICAL_FIELDS: Tuple[str, ...] = (
    "session_id",
    "user_id",
    "user_role",
    "agent_id",
    "action_type",
    "target_system_id",
    "target_record_id",
    "input_hash",
    "output_summary",
    "evidence_ids",
    "opa_rule_ids",
    "model_id",
    "prompt_version",
    "approval_id",
)

# The two CANONICAL_FIELDS entries backed by a Postgres JSONB column --
# see module docstring, correction 1.
JSONB_LIST_FIELDS: Tuple[str, ...] = ("evidence_ids", "opa_rule_ids")


def _normalise_list_field(value: Any) -> list:
    """Returns `[]` for `None`, `json.loads(value)` for a `str` (the shape
    asyncpg hands back for an unregistered JSONB column type), and
    `list(value)` otherwise (an already-native Python list, e.g. what a
    caller passes into `log_event` before any DB round trip)."""
    if value is None:
        return []
    if isinstance(value, str):
        return json.loads(value)
    return list(value)


def _canonical_json(event_data: Mapping[str, Any]) -> str:
    """Build the fixed, sorted-key JSON string both `log_event` and
    `verify_chain` hash. Driving off `CANONICAL_FIELDS` (not
    `event_data`'s own key set) is correction 2 in this module's
    docstring -- an event dict that omits an optional key still produces
    the same key set as a full `audit_events` row does."""
    canonical_data = {
        field: (
            _normalise_list_field(event_data.get(field))
            if field in JSONB_LIST_FIELDS
            else event_data.get(field)
        )
        for field in CANONICAL_FIELDS
    }
    return json.dumps(canonical_data, sort_keys=True, separators=(",", ":"), default=str)


async def log_event(pool, event_data: Dict[str, Any]) -> str:
    """Append one row to `audit_events`, chained to the previous row's
    `event_hash` (or `GENESIS_HASH` on an empty table).

    The `LOCK TABLE audit_events IN EXCLUSIVE MODE` statement inside this
    transaction is what stops two concurrent `log_event` calls from both
    reading the same `prev_hash` and forking the chain (05-RESEARCH.md
    Pitfall 5). Removing it is never a safe optimisation -- a "no
    observed race in single-threaded tests" result does not mean the race
    cannot happen; it means the test suite has not exercised concurrency,
    and 21 CFR 11.10(e)'s tamper-evidence guarantee depends on this lock
    holding under real concurrent writers.
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("LOCK TABLE audit_events IN EXCLUSIVE MODE")
            prev_row = await conn.fetchrow(
                "SELECT event_hash FROM audit_events ORDER BY timestamp_utc DESC LIMIT 1"
            )
            prev_hash = prev_row["event_hash"] if prev_row is not None else GENESIS_HASH

            canonical_json = _canonical_json(event_data)
            event_hash = hashlib.sha256(
                f"{prev_hash}{canonical_json}".encode("utf-8")
            ).hexdigest()
            event_id = f"EVT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
            # audit_events.timestamp_utc is `TIMESTAMP` (naive, no time
            # zone) per infra/postgres/initdb/001_schema.sql:184 -- an
            # aware datetime.now(timezone.utc) raises
            # asyncpg.exceptions.DataError ("can't subtract offset-naive
            # and offset-aware datetimes") against that column type.
            # Mirrors app/schemas.py's AgentMessage.timestamp fix: strip
            # tzinfo after computing in UTC, producing a byte-identical
            # naive-UTC value rather than switching the column type.
            timestamp_utc = datetime.now(timezone.utc).replace(tzinfo=None)

            evidence_ids = _normalise_list_field(event_data.get("evidence_ids"))
            opa_rule_ids = _normalise_list_field(event_data.get("opa_rule_ids"))

            await conn.execute(
                """
                INSERT INTO audit_events
                (event_id, timestamp_utc, session_id, user_id, user_role, agent_id,
                 action_type, target_system_id, target_record_id, input_hash,
                 output_summary, evidence_ids, opa_rule_ids, model_id,
                 prompt_version, approval_id, previous_event_hash, event_hash)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                        $14, $15, $16, $17, $18)
                """,
                event_id,
                timestamp_utc,
                event_data.get("session_id"),
                event_data.get("user_id"),
                event_data.get("user_role"),
                event_data.get("agent_id"),
                event_data.get("action_type"),
                event_data.get("target_system_id"),
                event_data.get("target_record_id"),
                event_data.get("input_hash"),
                event_data.get("output_summary"),
                json.dumps(evidence_ids),
                json.dumps(opa_rule_ids),
                event_data.get("model_id"),
                event_data.get("prompt_version"),
                event_data.get("approval_id"),
                prev_hash,
                event_hash,
            )
            return event_id


async def verify_chain(pool) -> Dict[str, Any]:
    """Walk every `audit_events` row in chronological order and recompute
    each row's hash from its own data plus the previous row's hash.

    Returns `{"status": "TAMPERED", "broken_at_index": index, "event_id":
    ...}` at the first row whose `previous_event_hash` does not match the
    running `curr_hash`, or whose own recomputed hash does not match its
    stored `event_hash`. Returns `{"status": "VERIFIED", "events_checked":
    len(rows)}` when the whole table walks clean, including the trivial
    case of zero rows.

    `_canonical_json(dict(row))` runs the exact same JSONB normalisation
    used on the write side (module docstring, correction 1) -- this is
    what makes a legitimate, untouched row verify rather than false-
    positive as TAMPERED.
    """
    rows = await pool.fetch("SELECT * FROM audit_events ORDER BY timestamp_utc ASC")
    curr_hash = GENESIS_HASH
    for index, row in enumerate(rows):
        if row["previous_event_hash"] != curr_hash:
            return {
                "status": "TAMPERED",
                "broken_at_index": index,
                "event_id": row["event_id"],
            }
        event_data = dict(row)
        canonical_json = _canonical_json(event_data)
        recomputed = hashlib.sha256(
            f"{curr_hash}{canonical_json}".encode("utf-8")
        ).hexdigest()
        if recomputed != row["event_hash"]:
            return {
                "status": "TAMPERED",
                "broken_at_index": index,
                "event_id": row["event_id"],
            }
        curr_hash = recomputed
    return {"status": "VERIFIED", "events_checked": len(rows)}
