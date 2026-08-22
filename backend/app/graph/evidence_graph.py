"""
Evidence graph tracer (Phase 4, plan 04-01).

Ticket: SENT-3-01 | Requirement: GRAPH-01
Source: AegisX-AI-Project-Bible-v6.md Section 10.1 (`build_evidence_graph` /
`find_downstream_impacts`) and Section 1.3's deterministic-first
constraint.

This module must never contain a model call. Bible Section 1.3 places
graph relationship derivation in the Python/NetworkX tier permanently, not
as a stub-stage convenience -- a model may never invent, infer, or rank a
graph relationship. Every node and edge here traces back to a real
Postgres row and a real foreign-key-shaped column value.

Node id convention (resolves 04-RESEARCH.md Open Question 1 / Pitfall 4):
`graph_nodes.node_id` is a single VARCHAR(100) primary key shared by every
entity type in the graph. Today's seed data happens to use disjoint id
prefixes per domain table (`URS-*`, `TC-*`, `RSK-*`, ...), but that is a
seed-data habit, not a schema constraint -- a future row whose raw id
collided with another table's raw id would otherwise silently overwrite an
unrelated node in `graph_nodes` rather than erroring. Every node id
written anywhere in this module is therefore type-prefixed via
`make_node_id`/`split_node_id` (`"{node_type}:{entity_id}"`), never a raw
domain primary key.

Table and column names used to build SQL statements come exclusively from
the frozen `NODE_SPECS`/`RELATION_TYPES` allowlists below -- never from
request data or from a database row -- and are joined into the query
string by plain string concatenation, exactly as
`app.agents.c1_verifier.RULE_EVIDENCE_TABLES` and
`_select_one_by_id_query` already establish for this codebase (threat
T-04-02). Every bound value (`system_id` in particular, a user-facing path
parameter) crosses into SQL only through an asyncpg `$1`-style placeholder
(threat T-04-01).
"""

import json
import logging
from typing import Any, Dict, List, NamedTuple, Tuple

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
    #       only through a parent node type's rows (unused by this plan's
    #       three node types; implemented by plan 04-02).


# Frozen allowlist: node type -> NodeSpec. Table names reach SQL only from
# here. This plan populates SYSTEM, REQUIREMENT, TEST_CASE only; plan 04-02
# extends this dict. Order matters: TEST_CASE precedes REQUIREMENT so the
# VERIFIED_BY edge pass (over already-fetched REQUIREMENT rows) always has
# both endpoints already present in the graph.
NODE_SPECS: Dict[str, NodeSpec] = {
    "SYSTEM": NodeSpec(
        "gxp_systems",
        ("name", "lifecycle_state", "gxp_impact", "readiness_score"),
        "id",
    ),
    "TEST_CASE": NodeSpec("test_cases", ("status",), "system_id"),
    "REQUIREMENT": NodeSpec("requirements", ("req_text",), "system_id"),
}

# Frozen allowlist of permitted graph_edges.relation_type values.
# `_add_edge` rejects anything outside it. This plan: VERIFIED_BY only;
# plan 04-02 extends it.
RELATION_TYPES: frozenset = frozenset({"VERIFIED_BY"})


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
    `property_columns` -- no `SELECT *` spread, so an unlisted column can
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
    (critical finding 3: `graph_edges` has real foreign keys to
    `graph_nodes` in both directions, and `requirements.test_case_id`
    carries no FK constraint of its own, so a dangling value must be
    dropped here at build time rather than relying on the database to
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


def _fetch_rows_query(node_type: str) -> str:
    """Builds `SELECT <property_columns + id> FROM <table> WHERE <scope> = $1`
    via plain string concatenation (never an f-string over request data),
    mirroring `c1_verifier._select_one_by_id_query`. `node_type` is only
    ever a key already validated against `NODE_SPECS`."""
    spec = NODE_SPECS[node_type]
    columns = ", ".join(("id",) + spec.property_columns)
    scope_column = spec.scope if isinstance(spec.scope, str) else "id"
    return "SELECT " + columns + " FROM " + spec.table + " WHERE " + scope_column + " = $1"


async def _fetch_rows(pool, node_type: str, system_id: str) -> List[dict]:
    """Reads one node type's rows scoped to one system, using its
    `NodeSpec.scope`. The `("via_parent", ...)` branch is unused by this
    plan's three node types (SYSTEM/REQUIREMENT/TEST_CASE all scope by a
    plain column name) and is implemented in plan 04-02."""
    spec = NODE_SPECS[node_type]
    if isinstance(spec.scope, tuple):
        # via_parent -- not needed by this plan's node types.
        return []
    rows = await pool.fetch(_fetch_rows_query(node_type), system_id)
    return [dict(r) for r in rows]


async def build_graph(pool, system_id: str) -> nx.DiGraph:
    """Reads domain tables for one system, returns an in-memory
    `nx.DiGraph`. Writes nothing. Node attrs: node_type, entity_id,
    properties. Edge attrs: relation_type.

    Iterates NODE_SPECS in insertion order (TEST_CASE before REQUIREMENT),
    then does a single VERIFIED_BY edge pass over the already-fetched
    REQUIREMENT rows, so `_add_edge`'s endpoint-presence check always has
    both endpoints available by the time it runs.
    """
    G = nx.DiGraph()
    fetched_by_type: Dict[str, List[dict]] = {}

    for node_type in NODE_SPECS:
        rows = await _fetch_rows(pool, node_type, system_id)
        fetched_by_type[node_type] = rows
        for row in rows:
            _add_node(G, node_type, row)

    requirement_rows = fetched_by_type.get("REQUIREMENT", [])
    if requirement_rows:
        # test_case_id is the FK driving the VERIFIED_BY edge, not a
        # display property of REQUIREMENT (its property_columns is
        # ("req_text",) only, per T-04-04's no-SELECT-* discipline), so it
        # is fetched separately here rather than folded into
        # `_fetch_rows`'s property-column selection.
        link_rows = await pool.fetch(
            "SELECT id, test_case_id FROM requirements WHERE system_id = $1",
            system_id,
        )
        test_case_by_requirement = {r["id"]: r["test_case_id"] for r in link_rows}
        for row in requirement_rows:
            test_case_id = test_case_by_requirement.get(row["id"])
            if not test_case_id:
                continue
            source_id = make_node_id("REQUIREMENT", row["id"])
            target_id = make_node_id("TEST_CASE", test_case_id)
            _add_edge(G, source_id, target_id, "VERIFIED_BY")

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
