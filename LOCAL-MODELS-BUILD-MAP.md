# Local Models Build Map — Embeddings + LLM Ops via Ollama

**Date:** 2026-08-31 · **Hardware:** RTX 4060 Laptop (8GB VRAM, currently 112MiB used — fully free), 24GB RAM, i7-13650HX · **Trigger:** free-tier quota exhaustion on both Gemini (embeddings *and* `gemini-3.6-flash` text-gen) and DeepSeek (402, no billing) confirmed live today.

## What's already true, before writing a line of code

- **Ollama is already installed** on this machine (`ollama` client 0.21.2), just not running (`ollama serve` hasn't been started). No fresh install needed.
- **GPU is fully free** — 8188MiB total, 112MiB used. Nothing competing for VRAM.
- **`EMBEDDING_DIMENSIONS = 768`** is already the app's configured vector size, which happens to match `nomic-embed-text`'s default output dimensionality — a real compatibility point, though it doesn't remove the vector-space-mismatch problem (see Risks).
- **This codebase already has the right shape for adding a provider** — `llm_router.py`'s `PROVIDER_CONFIG`/cascade pattern and `embeddings.py`'s parallel structure exist specifically so a new provider is "add a config entry + a request builder," not a redesign.

## Scope: 12 distinct LLM tasks, 2 embedding tasks, 16 test files

Every `task=` string `call_llm()`/`call_embedding()` currently routes:

| Task | Current provider | Used by |
|---|---|---|
| `orchestrator`, `synthesis` | `gemini_flash_thinking` | A0 routing, Copilot answer synthesis |
| `compliance`, `knowledge`, `change`, `rerank` | `gemini_flash_fast` | A2, A1, A4, hybrid-search reranking |
| `risk_assessment` | `deepseek_r1` | A3 |
| `incident`, `access`, `high_volume`, `narration`, `remediation` | `groq_gpt_oss` | A5, A6, narration, A7 |
| `fallback` | `openrouter_fallback` | cascade's last resort |
| `embed_document`, `embed_query` | Gemini `gemini-embedding-001` | ingestion, retrieval |

16 test files mock specific provider URLs (`generativelanguage.googleapis.com`, `api.groq.com`, etc.) via `respx`. Every one of those is a claim about which provider a task hits — moving default routing changes what those tests need to mock, which is the single largest hidden cost in this migration, not the provider code itself.

**One thing that does NOT change, regardless of this migration:** C1 (evidence verification), C2 (RBAC + injection detection), and C3 (action-category routing) make zero LLM calls by design (Bible §1.3, enforced and tested — `test_graph_topology.py`/`test_c1_verifier.py` assert this). Nothing about local-vs-hosted touches the deterministic core this product's whole thesis rests on.

## The technical approach, and why it's cheaper than it sounds

**Ollama exposes an OpenAI-compatible endpoint** (`http://localhost:11434/v1/chat/completions`). `llm_router.py` already has `_build_openai_compatible_request`/`_parse_openai_compatible_response` — the exact shape Groq/DeepSeek/OpenRouter already use. Adding Ollama as a `PROVIDER_CONFIG` entry is mechanically the same as adding a 5th OpenAI-compatible provider, not new request/response logic. `json_output` → `response_format: {"type": "json_object"}` should work unchanged (Ollama supports this on recent versions — verify against the installed 0.21.2 server once running).

**Embeddings need genuinely new code**, not reuse — Gemini's embed request/response shape is Google-native, not OpenAI-shaped, so `embeddings.py`'s existing builder doesn't transfer. Ollama's `/api/embeddings` (or its own OpenAI-compatible `/v1/embeddings`) needs one new builder function, structurally simple (single text in, vector out — no batching-shape complexity to match, since Ollama's embedding endpoint doesn't do Gemini's `:batchEmbedContents` batching in the same way; batching would mean N sequential calls or checking if Ollama's OpenAI-compat endpoint accepts a list input).

## Day 1 — Embeddings fully local (the part that's actually safe to fully finish)

This is the piece worth *completing*, not piloting, in the 2 days — it's lower-risk (embeddings are pure computation, no JSON-reliability/reasoning-quality question), it directly fixes the failure that started this whole investigation, and it doesn't touch the fan-out/concurrency question below.

1. `ollama serve` + `ollama pull nomic-embed-text` (or `mxbai-embed-large` if quality testing prefers it — both trivially fit 8GB).
2. New `app/retrieval/ollama_embeddings.py` (or extend `embeddings.py` with a second provider config) — one request builder, no batching-endpoint complexity to replicate exactly, since local has no rate limit forcing the same batching optimization to matter as much (though keep batching for throughput, not for quota-avoidance).
3. **Wipe and rebuild the Qdrant collection** rather than attempt a mixed-space migration — there's minimal real data indexed right now (a handful of test uploads), so this is genuinely cheap today. Re-upload the fixture documents through the real pipeline afterward as the verification step.
4. Route `embed_document`/`embed_query` to the new local provider as primary (Gemini stays configured as a fallback entry, or removed — your call on whether free-tier Gemini embeddings are worth keeping as a cascade tier at all, given today's evidence it's the *better-calibrated* of the two Gemini quotas).
5. Update `backend/tests/test_retrieval_embeddings.py` and the `respx`-mocked embedding tests to target `localhost:11434` shapes.
6. Live-verify: real document upload (reuse `urs_extract.md`, or the real DOCX that failed today) → real local embedding → real Qdrant write → real retrieval. This is the one test that must pass by end of Day 1.

**Day 1 exit criterion:** the exact failure from earlier today (105-chunk document, `429` on embeddings) cannot recur, because there's no external embedding call left to rate-limit.

## Day 2 — LLM ops: pilot two tasks for real, don't attempt all twelve

This is where I'd scope down from "switch everything" to "prove it works for the tasks that actually failed today, then decide." Reasoning below in Feasibility.

1. `ollama pull` a generation model — `qwen2.5:7b-instruct` or `llama3.1:8b-instruct` are the reasonable starting picks for JSON-reliability on 8GB (both quantize to ~4.5-5GB at Q4_K_M, leaving headroom).
2. Add the Ollama chat entry to `PROVIDER_CONFIG`, reusing the existing OpenAI-compatible builder.
3. Route **`narration`** and **`rerank`** to it first — these are the two tasks that actually degraded in today's live failures (narration via Groq worked fine today, but rerank via `gemini_flash_fast` is what hit the tightest-calibrated quota, 5 RPM real vs. 60 configured). Leave `orchestrator`/`synthesis`/`compliance`/`knowledge`/`risk_assessment` on their current hosted providers for now.
4. Test-suite: `backend/tests/test_narration_cascade_cache.py`, `test_hybrid_search.py`'s rerank tests, and any `respx` mock targeting those two tasks' current provider need updating.
5. Live-verify the same golden path as before (grounded query, off-topic refusal, injection block) with these two tasks now local, everything else unchanged.

**Day 2 exit criterion:** the two specific tasks that failed live today run entirely without an external network call, verified against the real golden-path test again.

## Feasibility verdict

**Local embeddings, fully done and tested, in Day 1: realistic.** Small scope, no quality/reasoning risk, directly fixes today's actual incident, and the OpenAI-compat reuse pattern keeps new code minimal.

**All 12 LLM tasks moved to local, fully tested, in Day 2: not realistic to the standard this codebase has held itself to.** Three concrete reasons, not hand-waving:

1. **Concurrency changes the pipeline's actual latency shape.** `routes/findings.py` and A0's fan-out call multiple agents *concurrently* via `asyncio.gather`, relying on hosted providers handling parallel requests. One Ollama instance with one model loaded serializes requests on one GPU — a query that fans out to 6 LLM-backed checks would queue instead of parallelize, multiplying wall-clock time. This isn't a config change, it's a real behavioral difference worth measuring before committing all 12 tasks to it.
2. **JSON-reliability and reasoning quality are unverified for this specific workload.** A2/A1/rerank all depend on structured JSON output and reasonably careful instruction-following (`AgentFinding` schemas, rerank scoring, compliance narration). A 7-8B local model is not guaranteed to match Gemini/Groq's reliability on this out of the box — it needs actual measurement against this project's own prompts, not an assumption.
3. **16 test files' worth of `respx` mocks encode "which provider does this task hit."** Moving all 12 tasks is 12 tasks' worth of test rewiring, not 2. Given Day 1 already spends real time on the embedding piece, 12-task test rework plus live re-verification of the full golden path is more than a remaining single day supports at the level of rigor this project's own conventions expect (real tests, not smoke tests, per `CLAUDE.md` Rule 6 for anything critical-path).

**Recommendation:** Day 1 = embeddings fully local (real fix, real deadline-appropriate scope). Day 2 = narration + rerank piloted locally (the two tasks that actually broke today), with the remaining 10 tasks staying on their current hosted/cascade providers — cascade already has 4-deep fallback per task, so those aren't at the same acute risk embeddings and rerank were. Full 12-task migration becomes a **third phase**, scoped and estimated separately once Day 2's pilot gives real data on local-model latency and JSON-reliability for this workload — the same "measure before committing" principle already applied to the embedding-fallback decision earlier.

## Risks worth naming now, not discovering later

- **Vector space mismatch is a one-way door for existing indexed data.** Anything indexed under Gemini's embedding space is meaningless once queried against a local model's space. Fine today (trivial existing corpus); would need an actual re-embedding migration plan the day this has real production data.
- **Model quality regression is a real possibility, not a formality to verify.** If `qwen2.5:7b` narrates a compliance finding less precisely than `gemini-3.6-flash`/`groq_gpt_oss` did, that's a product-quality regression, not just a plumbing change — Day 2's live verification needs to actually read the narration output, not just check the HTTP status came back 200.
- **This laptop now needs to run Postgres + Qdrant + OPA + backend + frontend + Ollama simultaneously.** 24GB RAM should comfortably cover this, but it's worth watching, especially once a 7-8B model is loaded into VRAM alongside everything else contending for system RAM.
