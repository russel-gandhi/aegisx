"""
Evidence graph builder + Blast Radius traversal (Phase 4, plans
04-01/04-02/04-04).

Ticket: SENT-3-01 (graph construction) / SENT-3-03 (Blast Radius) |
Requirement: GRAPH-01 / GRAPH-02
Source: AegisX-AI-Project-Bible-v6.md Section 10.1 (`build_evidence_graph` /
`find_downstream_impacts`), Section 14.3 (the illustrative relationship-type
list and the nine Graph Questions this module's `blast_radius()` answers),
and Section 1.3's deterministic-first constraint.

**Blast Radius (plan 04-04, SENT-3-03) is the deterministic-first boundary
applied to impact analysis.** Bible Section 14.3 (line 1750) permits a model
to explain or summarize an already-computed impact, but states plainly that
it "should not invent graph relationships" -- every value `blast_radius()`,
`assess_gxp_impact()`, and `rank_highest_impact()` return comes from
`nx.descendants`/`G.successors` reachability and node-type buckets alone.
No model call appears anywhere in this module.

This module must never contain a model call. Bible Section 1.3 places
graph relationship derivation in the Python/NetworkX tier permanently, not
as a stub-stage convenience -- a model may never invent, infer, or rank a
graph relationship. Every node and edge here traces back to a real
Postgres row: either a declared foreign key column (`EDGE_SPECS`) or an
explicit `change_affects` junction row (`_add_change_affects_edges`,
D-03). No edge is ever derived from two rows merely sharing a `system_id`
or from text matching between free-text columns.

Node id convention (resolves 04-RESEARCH.md Open Question 1 / Pitfall 4):
`graph_nodes.node_id` is a single VARCHAR(100) primary key shared by every
entity type in the graph. Seed data happens to use disjoint id prefixes
per domain table (`URS-*`, `TC-*`, `RSK-*`, ...), but that is a seed-data
habit, not a schema constraint -- a future row whose raw id collided with
another table's raw id would otherwise silently overwrite an unrelated
node in `graph_nodes` rather than erroring. Every node id written anywhere
in this module is therefore type-prefixed via `make_node_id`/
`split_node_id` (`"{node_type}:{entity_id}"`), never a raw domain primary
key.

Table and column names used to build SQL statements come exclusively from
the frozen `NODE_SPECS`/`RELATION_TYPES`/`EDGE_SPECS` allowlists below --
never from request data or from a database row -- and are joined into the
query string by plain string concatenation, exactly as
`app.agents.c1_verifier.RULE_EVIDENCE_TABLES`/`RULE_OPA_INPUT` and their
`_select_*_query` helpers already establish for this codebase (threat
T-04-02). Every bound value (`system_id`, the `via_parent`/`change_affects`
id lists) crosses into SQL only through an asyncpg `$1`-style placeholder
(threat T-04-01). The one exception -- `change_affects.entity_type`, a
database value that names a node type -- is validated against the frozen
`CHANGE_AFFECTS_ENTITY_TYPES` allowlist before it is ever used to build a
node id, and an out-of-allowlist value is logged and skipped rather than
reaching a SQL statement or an invented node type (T-04-02).

EDGE_SPECS direction convention. Every `EdgeSpec` declares `source_type`/
`relation_type`/`target_type` as the *drawn* edge direction (e.g.
`TEST_CASE --HAS_RESULT--> TEST_RESULT`, parent to child), never the
reverse. `link_column_owner` says which side's already-fetched rows carry
`source_column`:
  - `"source"` (default): the source_type's own fetched rows carry
    `source_column`, whose value is the target's entity id (a plain
    parent-references-target foreign key, e.g.
    `documents.system_id -> gxp_systems.id`).
  - `"target"`: the FK lives on the *child* table (`target_type`) instead,
    pointing back at the parent (`source_type`) -- true for the three
    relationships whose foreign key column lives on the child row
    (`test_results.test_case_id`, `change_actions.change_id`,
    `supplier_assessments.supplier_id`). The target_type's own fetched
    rows carry `source_column`, whose value is the *source*'s (parent's)
    entity id; the edge is still drawn source_type -> target_type
    (parent -> child), using each child row's own primary key as the
    target endpoint.
`source_column` is always selected into the owning side's fetched rows by
`_fetch_rows`/`_extra_select_columns` (see below), so no extra query is
issued during edge derivation -- `build_graph`'s edge pass reads only
already-fetched dicts.

Known Bible/schema gap, not implemented (routed to SENT-7-05): Bible
Section 14.3 also lists `ACCESS_REVIEW --CONTROLS--> ACCESS_RECORD`, but
`access_reviews` and `access_records` share no foreign key -- both only
reference `gxp_systems(id)` independently. D-03 explicitly rejects
same-`system_id` blanket association as a substitute edge source, so this
relationship type has no derivable source under this module's rules and is
deliberately omitted from both `RELATION_TYPES` and `EDGE_SPECS`.
`HAS_RESULT`, `HAS_ACTION`, and `ASSESSED_BY` are foreign-key-derived
additions beyond Section 14.3's own (illustrative, non-exhaustive) list.
"""

import json
import logging
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple

import networkx as nx

logger = logging.getLogger(__name__)


class NodeSpec(NamedTuple):
    table: str
    property_columns: Tuple[str, ...]
    scope: Any
    # scope is one of:
    #   "id"          -- the system row itself, selected by its own id
    #   "system_id"   -- a table directly scoped by a system_id column
    #   ("via_parent", parent_node_type, fk_column) -- a table reachable
    #       only through a parent node type's already-fetched rows; the
    #       query is `WHERE fk_column = ANY($1::varchar[])` bound to the
    #       parent rows' ids, issued only when that id list is non-empty.


class EdgeSpec(NamedTuple):
    source_type: str
    relation_type: str
    target_type: str
    source_column: str
    link_column_owner: str = "source"  # "source" or "target" -- see module docstring


# Frozen allowlist: node type -> NodeSpec. Table names reach SQL only from
# here. Insertion order is load-bearing: every parent type precedes any
# type whose scope is ("via_parent", parent, ...) -- TEST_CASE before
# TEST_RESULT, SUPPLIER before SUPPLIER_ASSESSMENT, CHANGE before
# CHANGE_ACTION -- so `_fetch_rows`'s via_parent branch always has the
# parent's ids already collected in `fetched_by_type` by the time it runs.
NODE_SPECS: Dict[str, NodeSpec] = {
    "SYSTEM": NodeSpec(
        "gxp_systems",
        ("name", "lifecycle_state", "gxp_impact", "readiness_score"),
        "id",
    ),
    "DOCUMENT": NodeSpec(
        "documents", ("doc_type", "title", "version", "status"), "system_id"
    ),
    "TEST_CASE": NodeSpec("test_cases", ("status",), "system_id"),
    "TEST_RESULT": NodeSpec(
        "test_results", ("pass_fail", "tester"), ("via_parent", "TEST_CASE", "test_case_id")
    ),
    "REQUIREMENT": NodeSpec("requirements", ("req_text",), "system_id"),
    "RISK": NodeSpec(
        "risks", ("risk_summary", "severity", "probability", "owner"), "system_id"
    ),
    "DESIGN_ELEMENT": NodeSpec("design_elements", ("description",), "system_id"),
    "INCIDENT": NodeSpec(
        "incidents",
        ("title", "severity", "status", "rca_started", "patient_safety_relevant"),
        "system_id",
    ),
    "ACCESS_REVIEW": NodeSpec(
        "access_reviews",
        ("review_type", "status", "reviewer", "accounts_in_scope"),
        "system_id",
    ),
    "ACCESS_RECORD": NodeSpec(
        "access_records", ("user_id", "is_privileged", "user_status"), "system_id"
    ),
    "SUPPLIER": NodeSpec("suppliers", ("name", "status"), "system_id"),
    "SUPPLIER_ASSESSMENT": NodeSpec(
        "supplier_assessments", ("result",), ("via_parent", "SUPPLIER", "supplier_id")
    ),
    "PERIODIC_EVALUATION": NodeSpec("periodic_evaluations", ("status",), "system_id"),
    "CHANGE": NodeSpec("changes", ("description", "status"), "system_id"),
    "CHANGE_ACTION": NodeSpec(
        "change_actions", ("description", "status"), ("via_parent", "CHANGE", "change_id")
    ),
}

# Frozen allowlist of permitted graph_edges.relation_type values. `_add_edge`
# rejects anything outside it. Populated by EDGE_SPECS (six FK-derived
# relation types plus AFFECTS, shared with the change_affects-derived
# edges below).
RELATION_TYPES: frozenset = frozenset(
    {
        "VERIFIED_BY",
        "HAS_RESULT",
        "HAS_ACTION",
        "ASSESSED_BY",
        "GOVERNS",
        "ASSOCIATED_WITH",
        "AFFECTS",
    }
)

# The complete FK-derived edge rule set. See module docstring for the
# source_type/relation_type/target_type/source_column/link_column_owner
# contract. Order is not load-bearing (all edges are derived after every
# node type has been fetched), but is kept in Bible Section 14.3's
# citation order where one exists.
EDGE_SPECS: Tuple[EdgeSpec, ...] = (
    EdgeSpec("REQUIREMENT", "VERIFIED_BY", "TEST_CASE", "test_case_id"),
    EdgeSpec("TEST_CASE", "HAS_RESULT", "TEST_RESULT", "test_case_id", "target"),
    EdgeSpec("CHANGE", "HAS_ACTION", "CHANGE_ACTION", "change_id", "target"),
    EdgeSpec("SUPPLIER", "ASSESSED_BY", "SUPPLIER_ASSESSMENT", "supplier_id", "target"),
    EdgeSpec("DOCUMENT", "GOVERNS", "SYSTEM", "system_id"),
    EdgeSpec("RISK", "ASSOCIATED_WITH", "SYSTEM", "system_id"),
    EdgeSpec("INCIDENT", "AFFECTS", "SYSTEM", "system_id"),
)

# The only entity_type values a change_affects row may carry (D-03).
# Validated in `_add_change_affects_edges` before any value derived from
# it is used to build a node id -- a row naming anything else is logged
# and skipped, never reaching a node type resolution (T-04-02).
CHANGE_AFFECTS_ENTITY_TYPES: frozenset = frozenset(
    {"REQUIREMENT", "TEST_CASE", "DOCUMENT", "DESIGN_ELEMENT", "RISK"}
)


def make_node_id(node_type: str, entity_id: str) -> str:
    """The one place node ids are formed: `"{node_type}:{entity_id}"`."""
    return node_type + ":" + entity_id


def split_node_id(node_id: str) -> Tuple[str, str]:
    """Inverse of `make_node_id`. Splits on the first `:` only, so an
    entity id containing a colon round-trips."""
    node_type, _, entity_id = node_id.partition(":")
    return node_type, entity_id


def _add_node(G: nx.DiGraph, node_type: str, row: dict) -> str:
    """Adds one node to `G`, computing its id via `make_node_id` and
    building `properties` from exactly that node type's declared
    `property_columns` -- no `SELECT *` spread, so an unlisted column
    (including any extra edge-link column `_fetch_rows` selected) can
    never leak into an API response (threat T-04-04)."""
    spec = NODE_SPECS[node_type]
    entity_id = row["id"]
    node_id = make_node_id(node_type, entity_id)
    properties = {col: row[col] for col in spec.property_columns}
    G.add_node(node_id, node_type=node_type, entity_id=entity_id, properties=properties)
    return node_id


def _add_edge(G: nx.DiGraph, source_id: str, target_id: str, relation_type: str) -> None:
    """Raises ValueError when `relation_type` is outside `RELATION_TYPES`.
    Returns without adding when either endpoint is absent from `G`
    (critical finding 3 / T-04-07: several link columns this module reads
    -- `requirements.test_case_id`, `change_affects.entity_id` -- carry no
    database foreign key constraint of their own, so a dangling value must
    be dropped here at build time rather than relying on the database to
    catch it)."""
    if relation_type not in RELATION_TYPES:
        raise ValueError(f"relation_type {relation_type!r} is outside RELATION_TYPES")
    if source_id not in G or target_id not in G:
        logger.warning(
            "Dropping edge %s -[%s]-> %s: endpoint missing from graph",
            source_id,
            relation_type,
            target_id,
        )
        return
    G.add_edge(source_id, target_id, relation_type=relation_type)


def _extra_select_columns(node_type: str) -> Tuple[str, ...]:
    """Columns to SELECT for `node_type` beyond its declared
    `property_columns`: the via_parent scope's own fk_column (needed both
    to bind the `= ANY($1::varchar[])` filter and, since that filter can
    match rows belonging to several different parents at once, to know
    which parent each returned row belongs to) plus any `EDGE_SPECS.
    source_column` this node type owns, on whichever side (`source_type`
    for the default owner, `target_type` for `link_column_owner="target"`).
    Never exposed in a node's persisted `properties` dict -- `_add_node`
    reads `NODE_SPECS[node_type].property_columns` only (T-04-04)."""
    spec = NODE_SPECS[node_type]
    extra: set = set()
    if isinstance(spec.scope, tuple) and spec.scope[0] == "via_parent":
        extra.add(spec.scope[2])
    for edge_spec in EDGE_SPECS:
        if edge_spec.link_column_owner == "target" and edge_spec.target_type == node_type:
            extra.add(edge_spec.source_column)
        elif edge_spec.link_column_owner != "target" and edge_spec.source_type == node_type:
            extra.add(edge_spec.source_column)
    return tuple(sorted(c for c in extra if c not in spec.property_columns))


def _fetch_rows_query(node_type: str) -> str:
    """Builds the SELECT for `node_type` via plain string concatenation
    (never an f-string over request data), mirroring
    `c1_verifier._select_one_by_id_query`/`_select_many_by_column_query`.
    `node_type` is only ever a key already validated against `NODE_SPECS`;
    every column and table name comes from `NODE_SPECS`/`EDGE_SPECS`."""
    spec = NODE_SPECS[node_type]
    columns = ", ".join(("id",) + spec.property_columns + _extra_select_columns(node_type))
    if isinstance(spec.scope, tuple) and spec.scope[0] == "via_parent":
        _, _parent_type, fk_column = spec.scope
        return (
            "SELECT " + columns + " FROM " + spec.table + " WHERE " + fk_column
            + " = ANY($1::varchar[])"
        )
    scope_column = spec.scope if isinstance(spec.scope, str) else "id"
    return "SELECT " + columns + " FROM " + spec.table + " WHERE " + scope_column + " = $1"


async def _fetch_rows(
    pool, node_type: str, system_id: str, fetched_by_type: Dict[str, List[dict]]
) -> List[dict]:
    """Reads one node type's rows. Plain-scoped types (`"id"`/`"system_id"`)
    are bound to `system_id`. `("via_parent", parent_type, fk_column)`
    types are bound to the parent type's already-fetched ids
    (`fetched_by_type[parent_type]`, populated earlier in `build_graph`'s
    NODE_SPECS loop -- insertion order guarantees this); an empty parent
    id list returns `[]` without issuing a query."""
    spec = NODE_SPECS[node_type]
    if isinstance(spec.scope, tuple) and spec.scope[0] == "via_parent":
        _, parent_type, _fk_column = spec.scope
        parent_ids = [r["id"] for r in fetched_by_type.get(parent_type, [])]
        if not parent_ids:
            return []
        rows = await pool.fetch(_fetch_rows_query(node_type), parent_ids)
    else:
        rows = await pool.fetch(_fetch_rows_query(node_type), system_id)
    return [dict(r) for r in rows]


async def _add_change_affects_edges(pool, G: nx.DiGraph, change_ids: List[str]) -> None:
    """Reads `change_affects` for `change_ids` and draws `AFFECTS` edges
    from each `CHANGE` node to `make_node_id(entity_type, entity_id)`
    (D-03). Returns without querying when `change_ids` is empty.

    `entity_type` is validated against `CHANGE_AFFECTS_ENTITY_TYPES`
    before use -- this is the one place a database row's own value could
    otherwise steer node-type resolution (T-04-02); an out-of-allowlist
    value is logged and skipped, never reaching a node id or a SQL
    statement. A valid `entity_type` whose `entity_id` does not resolve to
    a node already in `G` is silently dropped by `_add_edge`'s existing
    endpoint-presence check (T-04-07)."""
    if not change_ids:
        return
    rows = await pool.fetch(
        "SELECT change_id, entity_type, entity_id FROM change_affects "
        "WHERE change_id = ANY($1::varchar[])",
        change_ids,
    )
    for row in rows:
        entity_type = row["entity_type"]
        if entity_type not in CHANGE_AFFECTS_ENTITY_TYPES:
            logger.warning(
                "Dropping change_affects row (change_id=%s, entity_id=%s): "
                "entity_type %r is outside CHANGE_AFFECTS_ENTITY_TYPES",
                row["change_id"],
                row["entity_id"],
                entity_type,
            )
            continue
        source_id = make_node_id("CHANGE", row["change_id"])
        target_id = make_node_id(entity_type, row["entity_id"])
        _add_edge(G, source_id, target_id, "AFFECTS")


async def build_graph(pool, system_id: str) -> nx.DiGraph:
    """Reads domain tables for one system, returns an in-memory
    `nx.DiGraph`. Writes nothing. Node attrs: node_type, entity_id,
    properties. Edge attrs: relation_type.

    Three passes: (1) fetch and add every node type in NODE_SPECS
    insertion order, so every via_parent scope's parent ids are already
    collected by the time it runs; (2) one loop over EDGE_SPECS, deriving
    every FK-based edge from data already fetched in pass 1 -- no extra
    query is issued; (3) `_add_change_affects_edges` over the already-
    fetched CHANGE row ids, the one non-FK edge source in the whole graph.
    """
    G = nx.DiGraph()
    fetched_by_type: Dict[str, List[dict]] = {}

    for node_type in NODE_SPECS:
        rows = await _fetch_rows(pool, node_type, system_id, fetched_by_type)
        fetched_by_type[node_type] = rows
        for row in rows:
            _add_node(G, node_type, row)

    for edge_spec in EDGE_SPECS:
        if edge_spec.link_column_owner == "target":
            # FK lives on the child (target_type) row; it names the
            # parent's (source_type's) id. Edge is still drawn
            # source_type -> target_type (parent -> child).
            for row in fetched_by_type.get(edge_spec.target_type, []):
                parent_entity_id = row.get(edge_spec.source_column)
                if not parent_entity_id:
                    continue
                source_id = make_node_id(edge_spec.source_type, parent_entity_id)
                target_id = make_node_id(edge_spec.target_type, row["id"])
                _add_edge(G, source_id, target_id, edge_spec.relation_type)
        else:
            # FK lives on the source_type row; it names the target's id.
            for row in fetched_by_type.get(edge_spec.source_type, []):
                target_entity_id = row.get(edge_spec.source_column)
                if not target_entity_id:
                    continue
                source_id = make_node_id(edge_spec.source_type, row["id"])
                target_id = make_node_id(edge_spec.target_type, target_entity_id)
                _add_edge(G, source_id, target_id, edge_spec.relation_type)

    change_ids = [r["id"] for r in fetched_by_type.get("CHANGE", [])]
    await _add_change_affects_edges(pool, G, change_ids)

    return G


async def persist_graph(pool, system_id: str, G: nx.DiGraph) -> Dict[str, int]:
    """Deletes this system's cache rows and inserts the graph, in one
    transaction. Returns {"node_count": int, "edge_count": int}. This
    function is the only writer of the two cache tables anywhere in the
    codebase (D-01: the cache never holds a fact that is not derivable
    from domain state)."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Edge delete precedes node delete so the graph_edges FK to
            # graph_nodes holds throughout.
            await conn.execute(
                "DELETE FROM graph_edges WHERE source_id IN "
                "(SELECT node_id FROM graph_nodes WHERE system_id = $1) "
                "OR target_id IN (SELECT node_id FROM graph_nodes WHERE system_id = $1)",
                system_id,
            )
            await conn.execute("DELETE FROM graph_nodes WHERE system_id = $1", system_id)

            for node_id, attrs in G.nodes(data=True):
                node_type, _ = split_node_id(node_id)
                # SYSTEM's own row is scoped to itself; every other node
                # type's system_id is the system this graph was built for.
                node_system_id = attrs["entity_id"] if node_type == "SYSTEM" else system_id
                await conn.execute(
                    "INSERT INTO graph_nodes (node_id, system_id, node_type, properties) "
                    "VALUES ($1, $2, $3, $4::jsonb)",
                    node_id,
                    node_system_id,
                    attrs["node_type"],
                    json.dumps(attrs["properties"]),
                )

            for source_id, target_id, attrs in G.edges(data=True):
                await conn.execute(
                    "INSERT INTO graph_edges (source_id, target_id, relation_type) "
                    "VALUES ($1, $2, $3)",
                    source_id,
                    target_id,
                    attrs["relation_type"],
                )

    return {"node_count": G.number_of_nodes(), "edge_count": G.number_of_edges()}


async def load_graph(pool, system_id: str) -> nx.DiGraph:
    """Rebuilds the in-memory graph from the `graph_nodes`/`graph_edges`
    cache tables only. Reads no domain table."""
    G = nx.DiGraph()
    node_rows = await pool.fetch(
        "SELECT node_id, node_type, properties FROM graph_nodes WHERE system_id = $1",
        system_id,
    )
    for row in node_rows:
        node_type, entity_id = split_node_id(row["node_id"])
        properties = row["properties"]
        if isinstance(properties, str):
            properties = json.loads(properties)
        G.add_node(row["node_id"], node_type=node_type, entity_id=entity_id, properties=properties)

    edge_rows = await pool.fetch(
        "SELECT ge.source_id, ge.target_id, ge.relation_type "
        "FROM graph_edges ge JOIN graph_nodes gn ON gn.node_id = ge.source_id "
        "WHERE gn.system_id = $1",
        system_id,
    )
    for row in edge_rows:
        G.add_edge(row["source_id"], row["target_id"], relation_type=row["relation_type"])

    return G


# ---------------------------------------------------------------------------
# Blast Radius (plan 04-04, SENT-3-03, GRAPH-02)
#
# `blast_radius()` answers all nine of Bible Section 14.3's Graph Questions
# from a single `nx.descendants` traversal over an already-loaded graph.
# Deliberately no caching, memoisation, or size limit here -- the seeded
# demo graphs are single-digit-to-low-double-digit node counts, and adding
# an invalidation path this phase does not need would be a premature
# optimisation (04-RESEARCH.md's "minimal-but-real, not stub" bar).
# ---------------------------------------------------------------------------

# Fixed total ordering used only as a tie-break in `rank_highest_impact`.
# Contains every NODE_SPECS key exactly once (asserted by
# test_unit_node_type_impact_rank_contains_every_node_specs_key_exactly_once).
NODE_TYPE_IMPACT_RANK: Tuple[str, ...] = (
    "SYSTEM",
    "INCIDENT",
    "RISK",
    "REQUIREMENT",
    "TEST_CASE",
    "DOCUMENT",
    "DESIGN_ELEMENT",
    "CHANGE",
    "CHANGE_ACTION",
    "ACCESS_REVIEW",
    "ACCESS_RECORD",
    "SUPPLIER",
    "SUPPLIER_ASSESSMENT",
    "PERIODIC_EVALUATION",
    "TEST_RESULT",
)

# What "affected controls" means in this schema (Bible Section 14.3 Graph
# Question 7). `ACCESS_REVIEW --CONTROLS--> ACCESS_RECORD` itself has no
# derivable edge under D-03 (see module docstring's Bible-deviation note
# above), so this bucket is correctly empty for every source node today --
# a true statement about the graph's shape, not a gap in this function.
CONTROL_NODE_TYPES: frozenset = frozenset({"ACCESS_REVIEW", "ACCESS_RECORD"})


def assess_gxp_impact(G: nx.DiGraph, downstream: Set[str]) -> str:
    """`HIGH` when any downstream `SYSTEM` node's `properties["gxp_impact"]`
    is true, or any downstream `INCIDENT` node's
    `properties["patient_safety_relevant"]` is true; `MEDIUM` when the set
    is otherwise non-empty; `NONE` when empty (Bible Section 14.3 Graph
    Question 8). A missing key is treated as false rather than raising --
    `properties` is one of the allowlisted `property_columns` sets, so a
    node persisted before these property columns existed must not crash
    this function."""
    for node_id in downstream:
        attrs = G.nodes[node_id]
        properties = attrs.get("properties") or {}
        if attrs.get("node_type") == "SYSTEM" and properties.get("gxp_impact"):
            return "HIGH"
        if attrs.get("node_type") == "INCIDENT" and properties.get("patient_safety_relevant"):
            return "HIGH"
    return "MEDIUM" if downstream else "NONE"


def rank_highest_impact(G: nx.DiGraph, downstream: Set[str]) -> Optional[str]:
    """The downstream node with the most descendants of its own; ties
    broken by `NODE_TYPE_IMPACT_RANK` index, then by node id ascending
    (Bible Section 14.3 Graph Question 9). `None` for an empty set.

    Expressed as a single `max()` over one sort key whose first element is
    the negated descendant count, so the whole ordering is one total order
    -- the answer can never depend on set/dict iteration order, which is
    the entire point of this function existing separately from a plain
    `max(..., key=len)`."""
    if not downstream:
        return None

    def _sort_key(node_id: str) -> Tuple[int, int, str]:
        node_type = G.nodes[node_id].get("node_type")
        try:
            type_rank = NODE_TYPE_IMPACT_RANK.index(node_type)
        except ValueError:
            type_rank = len(NODE_TYPE_IMPACT_RANK)
        return (-len(nx.descendants(G, node_id)), type_rank, node_id)

    return min(downstream, key=_sort_key)


def blast_radius(G: nx.DiGraph, source_node_id: str) -> Dict[str, Any]:
    """Answers all nine of Bible Section 14.3's Graph Questions for
    `source_node_id` from one `nx.descendants` traversal over `G`.

    Raises `networkx.NetworkXError` when `source_node_id` is not a node of
    `G` -- the exception type `nx.descendants`/`G.successors` already raise
    for an absent node, propagated rather than caught here so the calling
    route can translate it to an HTTP 404 (a change record with no derived
    edges, or a node id belonging to a different system's graph, is a
    valid and expected state, not a server error).

    Never includes the source in any returned list -- the descendant set is
    defensively discarded of the source before bucketing, rather than
    relying on `nx.descendants` excluding it by default: on a graph
    containing a cycle back to the source it would not, and every one of
    the nine questions is about what is downstream *of* the node, not the
    node itself. Every list is sorted ascending, so the response is
    byte-stable across runs and a test can compare it directly.
    """
    if source_node_id not in G:
        raise nx.NetworkXError(f"source_node_id {source_node_id!r} is not in the graph")

    direct: Set[str] = set(G.successors(source_node_id))
    all_downstream: Set[str] = nx.descendants(G, source_node_id)
    all_downstream.discard(source_node_id)
    direct.discard(source_node_id)
    indirect: Set[str] = all_downstream - direct

    def _by_type(*node_types: str) -> List[str]:
        return sorted(
            n for n in all_downstream if G.nodes[n].get("node_type") in node_types
        )

    return {
        "source_node_id": source_node_id,
        "direct_dependencies": sorted(direct),
        "indirect_dependencies": sorted(indirect),
        "affected_requirements": _by_type("REQUIREMENT"),
        "affected_tests": _by_type("TEST_CASE", "TEST_RESULT"),
        "affected_risks": _by_type("RISK"),
        "affected_changes": _by_type("CHANGE", "CHANGE_ACTION"),
        "affected_controls": _by_type(*CONTROL_NODE_TYPES),
        "affected_systems": _by_type("SYSTEM"),
        "potential_gxp_impact": assess_gxp_impact(G, all_downstream),
        "highest_impact_downstream": rank_highest_impact(G, all_downstream),
    }
