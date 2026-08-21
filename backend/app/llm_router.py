"""
Multi-provider LLM router (Bible Section 8, Phase 3, D-01).

Ticket: SENT-2-01/SENT-2-02 substrate | Requirements: ORC-02, ORC-03

Source: AegisX-AI-Project-Bible-v6.md Section 8.1 (`PROVIDER_CONFIG`)
and 8.2 (router logic, the `openrouter_fallback` cascade). Transcribed
with three corrections, each recorded in `backend/README.md` under
"Bible deviations (backend tier)" and routed to SENT-7-05:

  - `deepseek_r1["model"]`: Bible's "deepseek-reasoner" is retired;
    corrected to "deepseek-v4-pro" (Deviation 4). Out of MVP scope this
    phase — A3/DeepSeek is not exercised by A0/A2/C1.
  - `openrouter_fallback["model"]`: Bible's "auto" corrected to the
    provider's actual model string "openrouter/auto" (Deviation 5).
  - Google entries' `api_key_env`: the Bible specifies "GOOGLE_API_KEY",
    but `.env.example` (D-01) gains `GEMINI_API_KEY`. Both are accepted,
    `GEMINI_API_KEY` checked first (Deviation 6).

Every other PROVIDER_CONFIG key — provider, base_url, rpm_limit,
thinking_budget, use_for — is unchanged from the Bible.

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

import logging
import os
from typing import Any, Dict, Optional

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Bible Section 8.1, transcribed with the three corrections documented in
# this module's docstring and in backend/README.md Deviations 4-6.
PROVIDER_CONFIG: Dict[str, Dict[str, Any]] = {
    "gemini_flash_thinking": {
        "provider": "google",
        "model": "gemini-2.5-flash",
        "thinking_budget": 512,
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        # Deviation 6: GEMINI_API_KEY checked first, GOOGLE_API_KEY accepted
        # as a documented alias when the first is unset.
        "api_key_env": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "rpm_limit": 60,
        "use_for": ["orchestrator", "synthesis", "remediation"],
    },
    "gemini_flash_fast": {
        "provider": "google",
        "model": "gemini-2.5-flash",
        "thinking_budget": 0,
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key_env": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "rpm_limit": 60,
        "use_for": ["compliance", "knowledge", "change"],
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
    "groq_llama": {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": ("GROQ_API_KEY",),
        "rpm_limit": 300,
        "use_for": ["incident", "access", "high_volume"],
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
                                      system_instruction: str) -> Dict[str, Any]:
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})
    body = {"model": entry["model"], "messages": messages}
    url = f"{entry['base_url']}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "content-type": "application/json"}
    return {"url": url, "headers": headers, "json": body}


def _parse_google_response(entry: Dict[str, Any], data: Dict[str, Any]) -> LLMResponse:
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return LLMResponse(text=text, model_id=entry["model"], provider=entry["provider"])


def _parse_openai_compatible_response(entry: Dict[str, Any], data: Dict[str, Any]) -> LLMResponse:
    text = data["choices"][0]["message"]["content"]
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
        request = _build_openai_compatible_request(entry, api_key, prompt, system_instruction)

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


async def call_llm(
    task: str,
    prompt: str,
    system_instruction: str = "",
    timeout: float = 10.0,
    json_output: bool = False,
) -> LLMResponse:
    """Route `task` to its configured provider, call it, and return a
    typed `LLMResponse`.

    Never raises to its caller. On any of the following, cascades exactly
    once to `openrouter_fallback` (Bible Section 8.2): a missing API key
    for the selected provider, `httpx.TimeoutException`, an
    `httpx.HTTPStatusError` with status 429, or any 5xx status. If the
    cascade target is itself unusable (missing key, or also fails),
    returns a degraded `LLMResponse` (`degraded=True`, non-empty
    `failure_reason`) instead of raising. This is what makes each
    calling agent's own Bible-specified fallback the last resort rather
    than the first — the router absorbs provider-level failures before
    they ever reach agent logic.

    No retry beyond the single cascade: a slow provider is A0's fallback
    trigger, not a retry trigger.
    """
    entry_key = select_provider(task)

    try:
        return await _send_one(entry_key, prompt, system_instruction, timeout, json_output)
    except _MissingKeyError as e:
        reason = f"missing_key:{e.entry_key}"
        cascadable = True
    except httpx.TimeoutException:
        reason = f"timeout:{entry_key}"
        cascadable = True
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 429 or status >= 500:
            reason = f"http_{status}:{entry_key}"
            cascadable = True
        else:
            logger.warning(
                "LLM call failed (provider=%s, host=%s, status=%s): non-cascading error.",
                entry_key, httpx.URL(str(e.request.url)).host, status,
            )
            return _degraded(f"http_{status}:{entry_key}")

    logger.warning(
        "LLM call failed (provider=%s): %s. Cascading to openrouter_fallback.",
        entry_key, reason,
    )

    if entry_key == "openrouter_fallback":
        # Already the fallback itself — nothing left to cascade to.
        return _degraded(reason)

    try:
        return await _send_one("openrouter_fallback", prompt, system_instruction, timeout, json_output)
    except _MissingKeyError:
        logger.warning(
            "openrouter_fallback also unavailable (no key). Returning degraded response."
        )
        return _degraded(f"{reason};missing_key:openrouter_fallback")
    except httpx.TimeoutException:
        logger.warning("openrouter_fallback timed out. Returning degraded response.")
        return _degraded(f"{reason};timeout:openrouter_fallback")
    except httpx.HTTPStatusError as e:
        logger.warning(
            "openrouter_fallback failed (status=%s). Returning degraded response.",
            e.response.status_code,
        )
        return _degraded(f"{reason};http_{e.response.status_code}:openrouter_fallback")
