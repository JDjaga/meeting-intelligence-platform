# 4. LLM Engineering (the extraction brain)

## `app/llm/prompts.py`
`SYSTEM_PROMPT` orders the model to return **JSON only** and states 5 rules: extract
explicit vs implicit separately; evidence must be an exact copied substring; how to set
confidence; ISO deadlines; decisions ≠ actions ≠ blockers. `USER_TEMPLATE` slots in the
title/date/attendees/transcript. Prompt engineering lives here, in one place, so the
behaviour can be tuned without touching code.

## `app/llm/providers.py` — two providers, one interface
- **`GeminiProvider`** (real LLM): sends the prompts via `llm/backends.py` (stdlib REST,
  temperature 0.1) and validates the JSON reply. Used when `GEMINI_API_KEY` is set in `.env`.
- **`RuleBasedProvider`** (offline fallback): deterministic pattern engine that returns the
  **same validated objects with real verbatim evidence**. Engineering inside:
  - *Implicit-first ordering*: hedged phrasing ("I'll sync up…", "let's…") is claimed by
    implicit patterns before the greedy explicit "I will…" pattern can steal it.
  - *Case-sensitive explicit matching*: owner names must be capitalised, so "team will
    sleep on it" is not mistaken for a commitment.
  - *Junk filter* (`JUNK_RE`): idioms/pleasantries ("sleep on it", "thanks", "wrap up")
    are never emitted as tasks; lone-verb captures ("Send") fall back to the full quote.
  - *Dedup* (`_is_dup`): two patterns matching one sentence produce one item.
  - *Deadline resolution* (`_resolve_deadline`): "Friday", "tomorrow", "EOD", ISO dates →
    real dates relative to the meeting date.
  - *Owner attribution* (`_owner_near`): nearest "Name:" speaker tag before the evidence.
- `get_provider()` picks Gemini when a key exists, else rules. The rest of the system
  cannot tell which ran — that interchangeability is the point.

## `app/llm/backends.py` — Gemini + Hugging Face caller
One `generate_json(system, user)` interface. Gemini is called via stdlib `urllib` REST
(no SDK install), trying the primary model then `MIP_GEMINI_FALLBACK` (wrong names,
quota and 404s are the common failures). Hugging Face uses the whisper-bundled
`huggingface_hub`. Providers without keys are skipped; every exception falls through to
the next backend, so chat/extraction degrades instead of crashing.

## Failure-proof extraction (`extractor.extract_meeting`)
Even with backends, an LLM call can still fail (bad key, no internet). So the
orchestrator wraps **every** provider call: on any exception it logs
`[extract] <name> failed (…)` and re-runs the offline rules engine, returning
   `provider="rules-fallback"`. An upload can therefore never return HTTP 500.

## `app/llm/extractor.py` — trust layer
`extract_meeting()` → provider extracts → `ground_and_score()` enforces honesty:
- evidence quote not found verbatim in transcript → confidence crushed to ≤ 0.35 +
  forced review (this is the **hallucination guard**; it is why hallucination rate is 0.0);
- owner missing → capped at 0.59 (routes to review);
- implicit capped at 0.70 (soft promises are never high-confidence);
- confidence < 0.60 → `needs_review = True` with a machine-written reason.
