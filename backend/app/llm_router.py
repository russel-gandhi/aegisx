"""
Multi-provider LLM router (Bible Section 8, Phase 3, D-01).

Ticket: SENT-2-01/SENT-2-02 substrate | Requirements: ORC-02, ORC-03

Source: AegisX-AI-Project-Bible-v6.md Section 8.1 (`PROVIDER_CONFIG`)
and 8.2 (router logic, the `openrouter_fallback` cascade). Transcribed
with corrections, each recorded in `backend/README.md` under
"Bible deviations (backend tier)" and routed to SENT-7-05:

  - `deepseek_r1["model"]`: Bible's "deepseek-reasoner" is retired;
    corrected to "deepseek-v4-pro" (Deviation 4). Out of MVP scope this
    phase — A3/DeepSeek is not exercised by A0/A2/C1.
  - `openrouter_fallback["model"]`: Bible's "auto" corrected to the
    provider's actual model string "openrouter/auto" (Deviation 5).
  - Google entries' `api_key_env`: the Bible specifies "GOOGLE_API_KEY",
    but `.env.example` (D-01) gains `GEMINI_API_KEY`. Both are accepted,
    `GEMINI_API_KEY` checked first (Deviation 6).
  - Both Google entries' `model`: the retired Gemini 2.5 flash id is no
    longer served; corrected to the currently served flash model
    (Deviation 10).
  - `gemini_flash_fast["thinking_budget"]`: Bible's `0` is now rejected
    by Google with HTTP 400; corrected to `1`, the smallest accepted
    value (Deviation 11).
  - `groq_gpt_oss["model"]`: the retired Llama 3.3 70B id is no longer
    served; corrected to "openai/gpt-oss-120b" (Deviation 12).
  - `use_for`: NOT byte-identical to the Bible any more. Quick task
    260826-p1q added a dedicated "narration" key to
    `groq_gpt_oss["use_for"]` (never Bible-listed under any entry). Quick
    task 260826-rsw then moved "remediation" from
    `gemini_flash_thinking["use_for"]` to `groq_gpt_oss["use_for"]`
    alongside it — Bible Section 8.1 lists "remediation" under the
    Google thinking entry; this router now routes it to Groq instead,
    under the total wall-clock ceiling `a7_remediation.synthesize_capa`
    enforces (recorded in `backend/README.md`'s Bible deviations
    section). "orchestrator" and "synthesis" are untouched and remain
    on `gemini_flash_thinking`.

Every other PROVIDER_CONFIG key — provider, base_url, rpm_limit — is
unchanged from the Bible.

House style mirrors `backend/app/opa_client.py`: raw httpx (no
per-provider SDK), explicit `timeout=` on every outbound call, logging
via `logging.getLogger(__name__)` rather than `print`, and
degrade-don't-raise on the caller-facing entry point (`call_llm()` never
raises to its caller — see its docstring).

No LLM provider API key is configured anywhere in this repo (D-01,
03-CONTEXT.md, 03-RESEARCH.md). Every code path here is production-shaped
— real HTTP calls, real response parsing — and is proven correct via
respx-mocked responses shaped exactly like each provider's real API, plus
an explicit degraded-mode test for the no-key/failure case. No
environment flag or "if DEMO_MODE" branch may short-circuit request
construction to return a canned string.
"""

import asyncio
import logging
import os
import re
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel

from app.circuit_breaker import is_available, record_rate_limited, record_success, record_timeout
from app.concurrency_gate import GateBusyError, acquire_slot
from app.http_client import get_shared_client
from app.rate_limiter import TokenBudgetExceededError, acquire_rate_limit, record_token_usage

load_dotenv()

logger = logging.getLogger(__name__)

# Groq `max_completion_tokens` budgets (`_build_openai_compatible_request`),
# named constants so the pair is greppable and tunable from one place.
# Reasoning tokens are charged against this same cap (see that function's
# comment), so an overrun surfaces only as a truncated/malformed response —
# never as an error — which is exactly the failure mode a generous budget
# exists to avoid (260826-rsw Design Note 2).
GROQ_MAX_COMPLETION_TOKENS_DEFAULT = 512
GROQ_MAX_COMPLETION_TOKENS_JSON = 2048

# Delay between successive provider attempts within a single call_llm()
# cascade, to avoid hammering the next provider immediately after the
# previous one failed/rate-limited. Not applied before the first attempt.
LLM_CASCADE_DELAY_SECONDS = float(os.getenv("LLM_CASCADE_DELAY_SECONDS", "1.0"))

# Bible Section 8.1, transcribed with the corrections documented in this
# module's docstring and in backend/README.md Deviations 4-6, 10-13.
#
# 2026-09-01: `gemini_flash_thinking`, `gemini_flash_fast`, and
# `deepseek_r1` removed, not merely deprioritized. Live evidence, not
# speculation: Gemini's real 429 response body named the exact quota --
# `embed_content_free_tier_requests`, `EmbedContentRequestsPerMinutePerUserPerProjectPerModel-FreeTier`
# -- and the AI Studio rate-limits console showed `gemini-3.6-flash` at
# 8/5 RPM (peak usage already over its own free-tier limit). Billing on
# this Google Cloud project reads "inactive or unsupported" directly in
# its own billing page, not merely unconfigured. DeepSeek returned a
# live `402 Payment Required`. Both are structurally broken until
# someone adds real billing, not transiently rate-limited. `ollama_qwen`
# (local, `qwen2.5:7b-instruct`, GPU-verified at 1.74s warm / 7.6s cold)
# replaces all seven tasks these three entries used to serve.
# `groq_gpt_oss` and `openrouter_fallback` are UNCHANGED below -- Groq
# had zero failures all session and OpenRouter is the designed
# last-resort; scrapping providers with no evidence against them would
# throw away real resilience for no reason (see LOCAL-MODELS-BUILD-MAP.md).
PROVIDER_CONFIG: Dict[str, Dict[str, Any]] = {
    "ollama_qwen": {
        "provider": "ollama",
        "model": "qwen2.5:7b-instruct",
        "base_url": "http://127.0.0.1:11434/v1",
        # Local HTTP API, no auth -- see `_send_one`'s own handling of an
        # empty `api_key_env` tuple as "no key required".
        "api_key_env": (),
        # No remote quota to pace against; a generous, effectively-inert
        # guard rather than a calibrated ceiling, mirroring
        # `embeddings.EMBEDDING_PROVIDER_CONFIG["ollama_embedding"]`.
        "rpm_limit": 6000,
        "use_for": [
            "orchestrator", "synthesis",  # was gemini_flash_thinking
            "compliance", "knowledge", "change", "rerank",  # was gemini_flash_fast
            "risk_assessment",  # was deepseek_r1
        ],
    },
    "groq_gpt_oss": {
        "provider": "groq",
        # Deviation 12: retired Llama 3.3 70B id corrected.
        "model": "openai/gpt-oss-120b",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": ("GROQ_API_KEY",),
        "rpm_limit": 300,
        # SENT-8-01, confirmed live 2026-09-02 via the real
        # `x-ratelimit-limit-tokens` response header: this account's real
        # binding constraint on `openai/gpt-oss-120b` is 8,000 tokens per
        # minute, not the 300-request rpm_limit above -- a reasoning model
        # burns hidden reasoning tokens on every call, so request count
        # alone massively understates real load. `None` here (every other
        # entry) means "no known token constraint, request-count limiting
        # only" -- the acquire_rate_limit token check is a no-op for them.
        "tpm_limit": 8000,
        "use_for": ["incident", "access", "high_volume", "narration", "remediation"],
    },
    "openrouter_fallback": {
        "provider": "openrouter",
        # Deviation 5: Bible's "auto" corrected to the provider's actual
        # model string.
        "model": "openrouter/auto",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": ("OPENROUTER_API_KEY",),
        "rpm_limit": 1000,
        "use_for": ["fallback"],
    },
}


# Deviation 18 (backend/README.md): Bible Section 8.2 specifies a single
# hop -- any failing provider cascades exactly once to `openrouter_fallback`
# and stops. User directive 2026-08-29 (live demo hit repeated Groq 429s
# with GEMINI/DEEPSEEK/OPENROUTER keys all genuinely configured and idle)
# changed this to a full multi-provider cascade: on failure, walk this list
# in order, skipping any entry whose underlying `provider` was already
# attempted, ending at `openrouter_fallback` as the guaranteed last resort.
#
# 2026-09-01: reordered local-first. `ollama_qwen` now covers every task
# `gemini_flash_fast`/`gemini_flash_thinking`/`deepseek_r1` used to (see
# PROVIDER_CONFIG's own comment for why those three were removed, not
# just reordered), so it leads the cascade the same way the fastest,
# most-likely-to-succeed hop always has. Groq and OpenRouter are
# unchanged and keep their same relative order -- both proven working
# this session, both still the cascade's hosted safety net if the local
# server is ever down.
FALLBACK_CASCADE: tuple[str, ...] = (
    "ollama_qwen",
    "groq_gpt_oss",
    "openrouter_fallback",
)


# SENT-8-01: rough per-task completion-token budgets, used only to build a
# pre-flight token-cost *estimate* for the rate limiter -- never to bound
# the actual request (that's `max_tokens`/generation config elsewhere, if
# any). "narration" and "rerank" are one-sentence/one-score outputs;
# "orchestrator"/"compliance"/"risk_assessment"/"remediation" are judgment
# tasks whose completion (and, on a reasoning model, hidden reasoning
# trace) runs meaningfully longer. Deliberately conservative (rounds up)
# since under-estimating defeats the point of a pre-flight check.
_TASK_COMPLETION_TOKEN_BUDGET: Dict[str, int] = {
    "narration": 250,
    "rerank": 150,
    "orchestrator": 400,
    "synthesis": 400,
    "compliance": 500,
    "knowledge": 500,
    "change": 500,
    "risk_assessment": 600,
    "remediation": 700,
    "incident": 500,
    "access": 500,
    "high_volume": 500,
    "fallback": 500,
}
_DEFAULT_COMPLETION_TOKEN_BUDGET = 500
# Rough, deliberately simple chars-per-token heuristic for the prompt side
# of the estimate (English text averages ~4 chars/token) -- exactness
# doesn't matter here, only staying in the right order of magnitude so the
# limiter's pre-flight check has *some* signal instead of none.
_CHARS_PER_TOKEN_ESTIMATE = 4


def _estimate_request_tokens(task: str, prompt: str, system_instruction: str) -> int:
    prompt_tokens = (len(prompt) + len(system_instruction)) // _CHARS_PER_TOKEN_ESTIMATE
    completion_budget = _TASK_COMPLETION_TOKEN_BUDGET.get(task, _DEFAULT_COMPLETION_TOKEN_BUDGET)
    return prompt_tokens + completion_budget


# Groq's rate-limit headers report resets as a duration string ("13.305s",
# "57m36s", "1h2m3.5s"), not a plain number -- this parses the h/m/s
# components present into a total seconds float. Returns `None` for an
# unparseable or empty string rather than raising: a header-parsing miss
# must degrade to "no live reset data" (the limiter's existing fallback
# path), never crash the calling request.
_RESET_DURATION_RE = re.compile(
    r"(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+(?:\.\d+)?)s)?"
)


def _parse_reset_duration_seconds(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    match = _RESET_DURATION_RE.fullmatch(value.strip())
    if match is None:
        return None
    hours = float(match.group("hours") or 0)
    minutes = float(match.group("minutes") or 0)
    seconds = float(match.group("seconds") or 0)
    total = hours * 3600 + minutes * 60 + seconds
    return total if total > 0 else None


def _cooldown_seconds_from_429_headers(headers: "httpx.Headers") -> Optional[float]:
    """Best-effort cooldown for the circuit breaker's OPEN state on a 429:
    prefers the token-reset window (usually the actually-binding
    constraint, per SENT-8-01's own finding) over the request-reset
    window, then falls back to a plain `Retry-After` seconds header (a
    different provider's convention) if present. `None` when nothing
    parses, letting the caller fall back to `DEFAULT_COOLDOWN_SECONDS`."""
    reset_tokens = _parse_reset_duration_seconds(headers.get("x-ratelimit-reset-tokens"))
    if reset_tokens is not None:
        return reset_tokens
    reset_requests = _parse_reset_duration_seconds(headers.get("x-ratelimit-reset-requests"))
    if reset_requests is not None:
        return reset_requests
    retry_after = headers.get("retry-after")
    if retry_after is not None:
        try:
            return float(retry_after)
        except ValueError:
            return None
    return None


def _record_token_headers(entry_key: str, headers: "httpx.Headers") -> None:
    """Best-effort: read `x-ratelimit-remaining-tokens`/`x-ratelimit-reset-tokens`
    from a real response (success or 429) and feed them into the rate
    limiter's live tracking. Silently does nothing for a provider that
    doesn't send these headers (Ollama, and any provider not on Groq's
    exact header convention) -- `record_token_usage` already no-ops on a
    `None` remaining-tokens value."""
    remaining_header = headers.get("x-ratelimit-remaining-tokens")
    remaining = int(remaining_header) if remaining_header is not None and remaining_header.isdigit() else None
    reset_seconds = _parse_reset_duration_seconds(headers.get("x-ratelimit-reset-tokens"))
    record_token_usage(entry_key, remaining, reset_seconds)


class LLMResponse(BaseModel):
    text: str
    model_id: str
    provider: str
    degraded: bool = False
    failure_reason: Optional[str] = None


def select_provider(task: str) -> str:
    """Return the single `PROVIDER_CONFIG` key whose `use_for` list
    contains `task`.

    Raises `KeyError` naming the unknown task when no entry matches — a
    typo in a task name must fail loudly at selection time, never
    silently fall back to some default provider (Bible Section 8.2).
    """
    for key, entry in PROVIDER_CONFIG.items():
        if task in entry["use_for"]:
            return key
    raise KeyError(f"No PROVIDER_CONFIG entry has {task!r} in its use_for list")


def _resolve_api_key(entry: Dict[str, Any]) -> Optional[str]:
    """Return the first set environment variable named in the entry's
    `api_key_env` tuple, or `None` if none are set."""
    for env_name in entry["api_key_env"]:
        value = os.getenv(env_name)
        if value:
            return value
    return None


def _degraded(reason: str) -> LLMResponse:
    return LLMResponse(text="", model_id="", provider="", degraded=True, failure_reason=reason)


def _build_google_request(entry: Dict[str, Any], api_key: str, prompt: str,
                           system_instruction: str, json_output: bool) -> Dict[str, Any]:
    body: Dict[str, Any] = {"contents": [{"parts": [{"text": prompt}]}]}
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    generation_config: Dict[str, Any] = {
        "thinkingConfig": {"thinkingBudget": entry["thinking_budget"]},
    }
    if json_output:
        generation_config["responseMimeType"] = "application/json"
    body["generationConfig"] = generation_config
    url = f"{entry['base_url']}/models/{entry['model']}:generateContent"
    headers = {"x-goog-api-key": api_key, "content-type": "application/json"}
    return {"url": url, "headers": headers, "json": body}


def _build_openai_compatible_request(entry: Dict[str, Any], api_key: str, prompt: str,
                                      system_instruction: str, json_output: bool) -> Dict[str, Any]:
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})
    body: Dict[str, Any] = {"model": entry["model"], "messages": messages}
    if json_output:
        # Standard OpenAI-compatible JSON-mode field (260826-rsw Design Note
        # 3). Applies to every provider this builder serves — Groq, DeepSeek,
        # AND OpenRouter — unlike `reasoning_effort`/`max_completion_tokens`
        # below, which are a Groq gpt-oss vendor extension. OpenRouter is
        # A7's own cascade fallback: gating this on Groq alone would mean
        # the fallback silently loses JSON mode and returns prose. If
        # `openrouter/auto` ever rejects this field, that is a 4xx which
        # `call_llm` already turns into a logged non-cascading degraded
        # response (accepted consequence, not a bug to "fix" later).
        body["response_format"] = {"type": "json_object"}
    if entry["provider"] == "groq":
        # `openai/gpt-oss-120b` is a Groq *reasoning* model: reasoning tokens
        # are charged against `max_completion_tokens`, so a tight cap without
        # a low reasoning effort can truncate to `finish_reason: "length"`
        # with null content (Design Note 4, 260826-p1q-PLAN.md). The budget
        # is selected by output shape (260826-rsw Design Note 2):
        # `GROQ_MAX_COMPLETION_TOKENS_DEFAULT` (512) is a generous floor for
        # a one-sentence narration; `GROQ_MAX_COMPLETION_TOKENS_JSON` (2048)
        # is sized for a four-field structured CAPA payload, where reasoning
        # tokens plus ~400-600 content tokens can otherwise overrun the
        # narration-sized floor and surface only as a generic-looking CAPA,
        # never as an error. `reasoning_effort` is a documented Groq gpt-oss
        # field; `reasoning_format` is explicitly NOT supported for these
        # models — do not add it. Both fields are gated strictly on
        # provider=="groq": OpenRouter shares this same builder and may 400
        # on an unrecognized field (unlike `response_format` above, which is
        # the standard field, not a vendor extension).
        body["reasoning_effort"] = "low"
        body["max_completion_tokens"] = (
            GROQ_MAX_COMPLETION_TOKENS_JSON if json_output else GROQ_MAX_COMPLETION_TOKENS_DEFAULT
        )
    url = f"{entry['base_url']}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "content-type": "application/json"}
    return {"url": url, "headers": headers, "json": body}


def _parse_google_response(entry: Dict[str, Any], data: Dict[str, Any]) -> LLMResponse:
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return LLMResponse(text=text, model_id=entry["model"], provider=entry["provider"])


def _parse_openai_compatible_response(entry: Dict[str, Any], data: Dict[str, Any]) -> LLMResponse:
    # A reasoning model (e.g. Groq's openai/gpt-oss-120b) can return
    # `finish_reason: "length"` with a null `content` when reasoning tokens
    # consume the completion budget (Design Note 4). Coerce None to "" here
    # rather than letting a null propagate into LLMResponse's `text: str`
    # field, which would raise a Pydantic ValidationError that call_llm does
    # not catch and that would surface to the route as an uncaught 500.
    text = data["choices"][0]["message"]["content"] or ""
    model_id = data.get("model") or entry["model"]
    return LLMResponse(text=text, model_id=model_id, provider=entry["provider"])


async def _send_one(entry_key: str, task: str, prompt: str, system_instruction: str,
                     timeout: float, json_output: bool) -> LLMResponse:
    """Send a single request to the provider named by `entry_key`.

    Raises `httpx.TimeoutException` or `httpx.HTTPStatusError` on
    failure (propagated to `call_llm()`'s cascade logic) rather than
    catching them here — this function has exactly one caller and that
    caller is the only place the cascade-vs-degrade decision belongs.
    Raises `_MissingKeyError` (module-private) when no configured
    environment variable holds a key for this provider.
    """
    entry = PROVIDER_CONFIG[entry_key]
    # An empty `api_key_env` tuple (Ollama, local, no auth) means "no key
    # required", not "key missing" -- mirrors the same fix in
    # `retrieval.embeddings._resolve_entry`. A non-empty tuple with no
    # value set in the environment still raises `_MissingKeyError` exactly
    # as before.
    if entry["api_key_env"]:
        api_key = _resolve_api_key(entry)
        if api_key is None:
            raise _MissingKeyError(entry_key)
    else:
        api_key = "not-required"

    if entry["provider"] == "google":
        request = _build_google_request(entry, api_key, prompt, system_instruction, json_output)
    else:
        request = _build_openai_compatible_request(entry, api_key, prompt, system_instruction, json_output)

    # Proactive rate limiting (SYSTEM-DESIGN-DIAGNOSIS.md #3, extended
    # SENT-8-01): waits until this provider is back under its own declared
    # `rpm_limit` AND (when the entry declares a `tpm_limit`, or once a
    # prior response has reported a live remaining-token count) its real
    # token budget, before the request goes out, rather than only reacting
    # to a 429 after the fact.
    estimated_tokens = _estimate_request_tokens(task, prompt, system_instruction)
    await acquire_rate_limit(
        entry_key, entry["rpm_limit"], estimated_tokens, entry.get("tpm_limit")
    )

    # Shared, pooled client (SYSTEM-DESIGN-DIAGNOSIS.md #1) -- see
    # app.http_client's module docstring for why this replaced a per-call
    # `async with httpx.AsyncClient()`.
    client = get_shared_client()

    # SENT-8-03: bounded local concurrency, Ollama only -- a hosted
    # provider's own server handles its own concurrency; a local 7B model
    # on an 8GB GPU does not. `GateBusyError` propagates to `call_llm`'s
    # cascade loop exactly like a timeout (see `_classify_failure`),
    # moving on to the next hop instead of piling onto an already
    # saturated local GPU.
    if entry["provider"] == "ollama":
        async with acquire_slot("ollama"):
            response = await client.post(
                request["url"], headers=request["headers"], json=request["json"], timeout=timeout,
            )
    else:
        response = await client.post(
            request["url"], headers=request["headers"], json=request["json"], timeout=timeout,
        )
    # Read rate-limit headers regardless of outcome -- a 429's own headers
    # are the freshest, most authoritative signal available about this
    # provider's real remaining budget, and `raise_for_status()` below must
    # not skip recording them just because this particular call failed.
    _record_token_headers(entry_key, response.headers)
    response.raise_for_status()
    data = response.json()

    if entry["provider"] == "google":
        return _parse_google_response(entry, data)
    return _parse_openai_compatible_response(entry, data)


class _MissingKeyError(Exception):
    """Module-private: raised by `_send_one` when no key is configured for
    the selected provider. Caught only inside `call_llm()`."""

    def __init__(self, entry_key: str):
        self.entry_key = entry_key
        super().__init__(f"No API key configured for {entry_key!r}")


# Status codes that mean "this provider's account/credentials are broken
# right now" rather than "this request is malformed": an expired/invalid
# key (401), no billing/credits (402), or an access-scope rejection (403).
# All three are properties of the specific provider being called, not of
# the request shape -- Groq or OpenRouter having no relationship to
# DeepSeek's billing status is exactly why these must cascade to the next
# untried provider rather than abort the whole call. Discovered live
# (2026-08-31): a real DeepSeek key returning 402 Payment Required was
# silently taking Groq and OpenRouter off the table for every `rerank`
# call, degrading retrieval quality for a reason that had nothing to do
# with either of those providers. Every other 4xx (400 Bad Request, 404,
# 422 Unprocessable Entity, ...) still does not cascade: those indicate a
# problem with the request itself, which the next provider is not
# expected to handle any differently.
_ACCOUNT_SPECIFIC_CASCADABLE_STATUSES = frozenset({401, 402, 403})


def _classify_failure(entry_key: str, exc: Exception) -> tuple[Optional[str], bool]:
    """Classify an exception raised by `_send_one`.

    Returns `(reason, cascadable)`. `reason` is `None` only when `exc` is
    not one of the failure types `call_llm` handles.

    `httpx.RequestError` (checked after the more specific
    `TimeoutException`, since that's a `RequestError` subclass and needs
    its own "timeout:" label, not the generic one) covers connection-level
    failures -- `ConnectError`, `ReadError`, DNS failure, and the like.
    Added 2026-09-01 alongside the local Ollama provider: a hosted
    provider being fully unreachable at the TCP level was rare enough
    that this path had never been exercised, but "the local Ollama
    process isn't running" is a real, likely failure mode for the
    provider now listed FIRST in the cascade -- without this, that
    exact scenario would propagate as an unhandled exception out of
    `call_llm()`, breaking its own documented "never raises" contract at
    the moment it matters most.

    `GateBusyError` (SENT-8-03) is treated identically to a timeout: the
    local concurrency gate refusing a slot means Ollama is saturated right
    now, not that anything is actually broken -- cascading to the next
    provider is the correct response, and the circuit breaker should
    accumulate it the same way a real timeout would.

    `TokenBudgetExceededError` (SENT-8-01) is this router's own pre-flight
    rejection, not a response from the provider -- but it carries exactly
    the same information a real 429 would (this provider is out of
    budget right now), so it cascades and trips the circuit breaker the
    same way.
    """
    if isinstance(exc, _MissingKeyError):
        return f"missing_key:{exc.entry_key}", True
    if isinstance(exc, TokenBudgetExceededError):
        return f"token_budget_exceeded:{entry_key}", True
    if isinstance(exc, GateBusyError):
        return f"concurrency_busy:{entry_key}", True
    if isinstance(exc, httpx.TimeoutException):
        return f"timeout:{entry_key}", True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429 or status >= 500 or status in _ACCOUNT_SPECIFIC_CASCADABLE_STATUSES:
            return f"http_{status}:{entry_key}", True
        return f"http_{status}:{entry_key}", False
    if isinstance(exc, httpx.RequestError):
        return f"connection_error:{entry_key}:{type(exc).__name__}", True
    return None, False


async def call_llm(
    task: str,
    prompt: str,
    system_instruction: str = "",
    timeout: float = 10.0,
    json_output: bool = False,
) -> LLMResponse:
    """Route `task` to its configured provider, call it, and return a
    typed `LLMResponse`.

    Never raises to its caller. On a missing API key, `httpx.TimeoutException`,
    a connection-level `httpx.RequestError` (DNS failure, refused
    connection — the local Ollama process not running is the concrete
    case this exists for), an `httpx.HTTPStatusError` with status 429, any
    5xx status, or an account-specific 401/402/403 (see
    `_ACCOUNT_SPECIFIC_CASCADABLE_STATUSES` — one provider's bad key or
    billing issue must not take the others off the table), cascades
    through `FALLBACK_CASCADE` in order — skipping
    any entry whose underlying `provider` was already attempted (Deviation
    18: this is a genuine multi-hop cascade, not the Bible's original
    single hop to `openrouter_fallback`) — until one succeeds or every
    entry has been tried, including `openrouter_fallback` as the
    guaranteed last resort. A non-cascadable error (400/404/422/... —
    request-shape problems the next provider isn't expected to handle any
    differently) returns a degraded response immediately without
    cascading. If every reachable entry fails,
    returns a degraded `LLMResponse` (`degraded=True`, `failure_reason`
    a `;`-joined trail of every hop's reason) instead of raising.

    Every hop shares the same per-request `timeout` budget the caller
    passed in — a caller wrapping this in its own `asyncio.wait_for` must
    size that outer ceiling for the worst case of `len(FALLBACK_CASCADE)`
    sequential attempts plus `(len(FALLBACK_CASCADE) - 1) *
    LLM_CASCADE_DELAY_SECONDS`, not a single attempt's timeout alone (see
    `a2_compliance.narrate_gap` and `a7_remediation.synthesize_capa` for
    the two call sites that do). `LLM_CASCADE_DELAY_SECONDS` (env
    `LLM_CASCADE_DELAY_SECONDS`, default 1.0s) is slept between a failed
    hop and the next cascade attempt only — never before the first
    attempt — to avoid immediately hammering the next provider.
    """
    entry_key = select_provider(task)
    tried_providers: set[str] = set()
    reasons: list[str] = []
    current_key = entry_key

    while True:
        # SENT-8-02: a provider the circuit breaker already knows is
        # rate-limited/unhealthy is skipped without ever calling
        # `_send_one` -- every concurrent agent call in the same burst
        # that discovers the same failure independently would otherwise
        # each pay a full wasted round trip to re-learn it.
        if not is_available(current_key):
            reason = f"circuit_open:{current_key}"
            reasons.append(reason)
            tried_providers.add(PROVIDER_CONFIG[current_key]["provider"])
            next_key = next(
                (
                    key for key in FALLBACK_CASCADE
                    if key != current_key and PROVIDER_CONFIG[key]["provider"] not in tried_providers
                ),
                None,
            )
            if next_key is None:
                logger.warning(
                    "LLM call skipped (provider=%s): circuit open. No more providers to cascade to.",
                    current_key,
                )
                return _degraded(";".join(reasons))
            logger.warning(
                "LLM call skipped (provider=%s): circuit open. Cascading to %s.",
                current_key, next_key,
            )
            current_key = next_key
            continue

        try:
            response = await _send_one(current_key, task, prompt, system_instruction, timeout, json_output)
            record_success(current_key)
            return response
        except (
            _MissingKeyError, TokenBudgetExceededError, GateBusyError, httpx.TimeoutException,
            httpx.HTTPStatusError, httpx.RequestError,
        ) as exc:
            reason, cascadable = _classify_failure(current_key, exc)

            # Feed the breaker regardless of cascadability -- a 429 or
            # timeout is informative about this provider's health even in
            # the (currently theoretical, since 429/5xx/timeout are all
            # cascadable) case a non-cascadable path reaches here.
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
                record_rate_limited(current_key, _cooldown_seconds_from_429_headers(exc.response.headers))
            elif isinstance(exc, TokenBudgetExceededError):
                record_rate_limited(current_key, exc.retry_after_seconds)
            elif isinstance(exc, (httpx.TimeoutException, httpx.RequestError, GateBusyError)):
                record_timeout(current_key)

            if not cascadable:
                logger.warning(
                    "LLM call failed (provider=%s): %s. Non-cascading error.",
                    current_key, reason,
                )
                return _degraded(reason)

            reasons.append(reason)
            tried_providers.add(PROVIDER_CONFIG[current_key]["provider"])

            next_key = next(
                (
                    key for key in FALLBACK_CASCADE
                    if key != current_key and PROVIDER_CONFIG[key]["provider"] not in tried_providers
                ),
                None,
            )
            if next_key is None:
                logger.warning(
                    "LLM call failed (provider=%s): %s. No more providers to cascade to.",
                    current_key, reason,
                )
                return _degraded(";".join(reasons))

            logger.warning(
                "LLM call failed (provider=%s): %s. Cascading to %s.",
                current_key, reason, next_key,
            )
            if LLM_CASCADE_DELAY_SECONDS > 0:
                await asyncio.sleep(LLM_CASCADE_DELAY_SECONDS)
            current_key = next_key
