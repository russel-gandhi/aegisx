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
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel

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
PROVIDER_CONFIG: Dict[str, Dict[str, Any]] = {
    "gemini_flash_thinking": {
        "provider": "google",
        # Deviation 10: retired Gemini 2.5 flash id corrected.
        "model": "gemini-3.6-flash",
        "thinking_budget": 512,
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        # Deviation 6: GEMINI_API_KEY checked first, GOOGLE_API_KEY accepted
        # as a documented alias when the first is unset.
        "api_key_env": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "rpm_limit": 60,
        "use_for": ["orchestrator", "synthesis"],
    },
    "gemini_flash_fast": {
        "provider": "google",
        # Deviation 10: retired Gemini 2.5 flash id corrected.
        "model": "gemini-3.6-flash",
        # Deviation 11: Bible's 0 is now rejected with HTTP 400; 1 is the
        # smallest accepted value.
        "thinking_budget": 1,
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key_env": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "rpm_limit": 60,
        # Deviation 17 (backend/README.md Deviation 12): "rerank" added
        # here rather than routed through a local cross-encoder. This
        # entry already serves A1's own "knowledge" task, and its
        # thinking_budget=1 is the fastest Google configuration in this
        # table -- reranking sits on the interactive Copilot path.
        # Bible Section 15.3 itself allows this: "if the selected
        # reranking model/provider depends on configuration, follow the
        # existing LLM routing architecture." Not a Section 1.3
        # violation (D-08): reranking scores retrieval relevance, it does
        # not evaluate a compliance threshold, an RBAC decision, or an
        # injection judgment.
        "use_for": ["compliance", "knowledge", "change", "rerank"],
    },
    "deepseek_r1": {
        "provider": "deepseek",
        # Deviation 4: Bible's "deepseek-reasoner" is retired.
        "model": "deepseek-v4-pro",
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": ("DEEPSEEK_API_KEY",),
        "rpm_limit": 30,
        "use_for": ["risk_assessment"],
    },
    "groq_gpt_oss": {
        "provider": "groq",
        # Deviation 12: retired Llama 3.3 70B id corrected.
        "model": "openai/gpt-oss-120b",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": ("GROQ_API_KEY",),
        "rpm_limit": 300,
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
# attempted (so a Google-family retry never fires twice against the same
# quota), ending at `openrouter_fallback` as the guaranteed last resort.
# `gemini_flash_fast` represents the whole "google" provider here (lower
# thinking_budget than `gemini_flash_thinking`, so it is also the faster of
# the two to fail if Google itself is down) -- trying both Google entries
# would just retry the same API key/quota twice for no benefit.
FALLBACK_CASCADE: tuple[str, ...] = (
    "gemini_flash_fast",
    "deepseek_r1",
    "groq_gpt_oss",
    "openrouter_fallback",
)


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


async def _send_one(entry_key: str, prompt: str, system_instruction: str,
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
    api_key = _resolve_api_key(entry)
    if api_key is None:
        raise _MissingKeyError(entry_key)

    if entry["provider"] == "google":
        request = _build_google_request(entry, api_key, prompt, system_instruction, json_output)
    else:
        request = _build_openai_compatible_request(entry, api_key, prompt, system_instruction, json_output)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            request["url"], headers=request["headers"], json=request["json"], timeout=timeout,
        )
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


def _classify_failure(entry_key: str, exc: Exception) -> tuple[Optional[str], bool]:
    """Classify an exception raised by `_send_one`.

    Returns `(reason, cascadable)`. `reason` is `None` only when `exc` is
    not one of the three failure types `call_llm` handles (unreachable in
    practice, since `_send_one` only ever raises `_MissingKeyError`,
    `httpx.TimeoutException`, or `httpx.HTTPStatusError` — kept explicit
    rather than assumed so a future new exception type fails loudly
    instead of silently mis-classifying as cascadable).
    """
    if isinstance(exc, _MissingKeyError):
        return f"missing_key:{exc.entry_key}", True
    if isinstance(exc, httpx.TimeoutException):
        return f"timeout:{entry_key}", True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429 or status >= 500:
            return f"http_{status}:{entry_key}", True
        return f"http_{status}:{entry_key}", False
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
    an `httpx.HTTPStatusError` with status 429, or any 5xx status, cascades
    through `FALLBACK_CASCADE` in order — skipping any entry whose
    underlying `provider` was already attempted (Deviation 18: this is a
    genuine multi-hop cascade, not the Bible's original single hop to
    `openrouter_fallback`) — until one succeeds or every entry has been
    tried, including `openrouter_fallback` as the guaranteed last resort.
    A non-cascadable error (any other 4xx) returns a degraded response
    immediately without cascading. If every reachable entry fails,
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
        try:
            return await _send_one(current_key, prompt, system_instruction, timeout, json_output)
        except (_MissingKeyError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            reason, cascadable = _classify_failure(current_key, exc)
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
