"""
Trust Centre configuration-transparency route (Bible Section 11.8).

Ticket: n/a | Requirement: bible Section 11.8's own call-out
Source: AegisX-AI-Project-Bible-v6.md Section 11.8 -- "displaying current
LLM provider configurations, the active OPA Rego policy bundle version, and
the live Audit Chain Integrity widget." The chain-integrity widget itself is
already served by the existing `GET /api/audit/verify` route (`audit.py`) --
this route covers the two pieces of that spec nothing currently exposes:
the LLM cascade and the OPA bundle.

Read-only, process-wide (not per-system) configuration. Never returns an
`api_key_env` value or any resolved key -- only `requires_api_key`, a
boolean derived from whether that tuple is non-empty. This is a
transparency artifact (EU AI Act-style disclosure, matching Section 11.2's
own "Model Attribution" requirement), not a secret to protect from the
authenticated operators this page is built for.
"""

import os

from fastapi import APIRouter

from app.llm_router import FALLBACK_CASCADE, PROVIDER_CONFIG
from app.retrieval.embeddings import EMBEDDING_PROVIDER_CONFIG
from app.schemas import LLMProviderInfo, TrustCentreResponse

router = APIRouter()

# Bible Section 1 / infra/docker-compose.yml: the OPA sidecar loads every
# `.rego` file under this directory as one bundle. Listing the same
# directory here (rather than hardcoding a file list) means this route can
# never silently drift from what the OPA container is actually serving.
_POLICIES_DIR = os.path.join(
    os.path.dirname(  # aegisx/ repo root -- policies/ is a sibling of backend/, not inside it
        os.path.dirname(  # aegisx/backend
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # aegisx/backend/app
        )
    ),
    "policies",
)


def _provider_info(key: str, entry: dict) -> LLMProviderInfo:
    return LLMProviderInfo(
        provider_key=key,
        provider=entry["provider"],
        model=entry["model"],
        use_for=list(entry["use_for"]),
        requires_api_key=bool(entry["api_key_env"]),
    )


@router.get("/api/trust-centre", response_model=TrustCentreResponse)
async def get_trust_centre() -> TrustCentreResponse:
    llm_cascade = [_provider_info(key, PROVIDER_CONFIG[key]) for key in FALLBACK_CASCADE]

    embedding_key, embedding_entry = next(iter(EMBEDDING_PROVIDER_CONFIG.items()))
    embedding_provider = _provider_info(embedding_key, embedding_entry)

    try:
        policy_files = sorted(
            f for f in os.listdir(_POLICIES_DIR) if f.endswith(".rego") and not f.endswith("_test.rego")
        )
    except OSError:
        policy_files = []

    return TrustCentreResponse(
        llm_cascade=llm_cascade,
        embedding_provider=embedding_provider,
        opa_policy_files=policy_files,
        opa_policy_count=len(policy_files),
    )
