"""
Startup narration pre-warm (quick task 260826-p1q, Task 3).

Fires off, from `app.main`'s `lifespan`, a background task that narrates
every currently-failing A2 check for both seeded demo systems
(`GXP-MFG-DEMO-01`, `BUS-IT-DEMO-02` -- real seeded rows,
`infra/postgres/seed/001_seed.sql`) before any human loads the page, so a
real user's first `get_assurance_cards` / `/stream` read is almost always
a `narration_cache` hit rather than a cold Groq call.

`prewarm_narration_cache()` is a PLAIN module-level `async def` -- not
logic buried inside `main.py`'s lifespan closure -- so a test can drive it
directly with `asyncio.run()`, exactly like every other coroutine in this
codebase's `asyncio.run()`-per-test convention (`tests/conftest.py`). This
is also what keeps it inert under an ordinary `pytest` run: Starlette's
`TestClient` only runs the ASGI `lifespan` protocol when entered as a
context manager (`with client:`), and `tests/conftest.py`'s session-scoped
`client` fixture deliberately never does that (see `app/main.py`'s
lifespan docstring, and this module's own test file for why that must
never change).

Reuses `app.agents.a2_compliance.narrate_gap` rather than reimplementing
its prompt: `narration_cache` is keyed on a sha256 digest of the exact
prompt string `narrate_gap` builds, so warming through anything other than
`narrate_gap` itself would produce a different digest and warm nothing
while appearing to succeed.

Sequential by design, not an oversight: the asyncpg pool caps at
`max_size=5` (`app/db.py`), and a concurrent pre-warm racing a live
request's own 4-way concurrent fan-out (`app/routes/findings.py`'s
`_MAX_CONCURRENT_CHECKS`) could push connection demand past that cap and
start blocking on the pool's 5.0s acquire timeout. The pre-warm has no
latency requirement of its own -- it is background work with no requesting
user -- so it yields the concurrency budget to real requests rather than
competing with them.

Every failure mode here -- Postgres unreachable at boot, OPA down, no
`GROQ_API_KEY` configured -- must log and return, never propagate: an
unhandled exception inside a fire-and-forget `asyncio.create_task` result
surfaces only as a "Task exception was never retrieved" warning at
shutdown and is otherwise invisible, which would make a startup failure
here silently undetectable in production.
"""

import logging
import os

from app.agents.a2_compliance import A2_CHECKS, narrate_gap
from app.agents.minimal_specialists import run_specialist
from app.db import acquire_pool_or_none

logger = logging.getLogger(__name__)

# Both are real seeded rows (infra/postgres/seed/001_seed.sql) -- the same
# two systems every other Phase 3-5 test and route in this codebase
# exercises against.
DEMO_SYSTEM_IDS = ("GXP-MFG-DEMO-01", "BUS-IT-DEMO-02")

# The specialists whose narrations the assurance-card routes also issue
# (`routes/findings.py`'s `_SPECIALIST_AGENT_IDS`). 2026-11-16: the pre-warm
# only ever covered A2, so its own promise -- that a read after warming
# issues no further narration request -- stopped being true the day the
# assurance grid was widened to A3-A6; the first Command Centre load after
# every boot still paid for five narrations per system.
SPECIALIST_AGENT_IDS = ("A3", "A4", "A5", "A6")

# `AEGISX_PREWARM_NARRATION=0` turns the pre-warm off. Worth doing under
# `uvicorn --reload`: `narration_cache` is in-process, so every restart
# re-narrates every failing check for both demo systems, and the hosted
# provider's free tier caps requests per DAY as well as tokens per minute
# (Groq reported `x-ratelimit-limit-requests: 1000` per model, 2026-11-16).
PREWARM_ENABLED: bool = os.getenv("AEGISX_PREWARM_NARRATION", "1").strip().lower() not in ("0", "false", "no")


async def prewarm_narration_cache() -> int:
    """Narrate every currently-failing `A2_CHECKS` entry, and every gap the
    A3-A6 specialists report, for both seeded demo systems -- strictly
    sequentially, populating `narration_cache` before any human request
    arrives.

    Returns the number of checks narrated (not necessarily the number of
    SUCCESSFUL narrations -- `narrate_gap` itself decides whether a given
    result is cache-worthy per its own degraded/blank-text guards; this
    count is purely "how many failing checks did we attempt to warm").

    Never raises: every failure mode (no pool, no provider key, a
    mid-loop exception) is caught, logged at warning level, and this
    returns the count accumulated so far rather than propagating.
    """
    warmed = 0
    if not PREWARM_ENABLED:
        logger.info("Narration pre-warm disabled via AEGISX_PREWARM_NARRATION.")
        return warmed
    try:
        pool = await acquire_pool_or_none()
        if pool is None:
            logger.warning("Narration pre-warm skipped: Postgres pool unavailable.")
            return warmed

        for system_id in DEMO_SYSTEM_IDS:
            for check_fn in A2_CHECKS:
                check_result = await check_fn(pool, system_id)
                if check_result["passed"]:
                    continue
                await narrate_gap(check_result)
                warmed += 1
            # `run_specialist` runs the agent's own deterministic check and
            # narrates each gap through the same memoized `_narrate_gap` /
            # `_narrate_a3` the assurance-card routes use, so the cache keys
            # match by construction. It never raises and returns no findings
            # when there is no gap.
            for agent_id in SPECIALIST_AGENT_IDS:
                result = await run_specialist(agent_id, {"system_id": system_id})
                warmed += len(result.get("findings", []))
    except Exception:
        logger.warning(
            "Narration pre-warm failed after warming %d check(s); continuing startup.",
            warmed,
            exc_info=True,
        )

    return warmed
