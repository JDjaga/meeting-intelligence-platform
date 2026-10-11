# ProjectActionGraph — Full Explanation Guide

What the software is, how every folder/file works, which AI techniques are used
and why, and an honest note on fine-tuning.

---

## 1. What this software is (one paragraph)

You give it a meeting — a transcript (`.txt/.srt/.vtt`), a document (`.pdf/.docx`)
or a recording (`.mp3/.wav`/…) — and it returns the meeting in structured form:
**action items** (what + owner + deadline), **decisions** (what was agreed),
**blockers** (what is stuck) and **follow-ups**. Every item carries the **exact
transcript quote** that proves it and a **confidence score**; unsure items wait in
a **human review queue**. History is kept, so open work **carries into the next
meeting** and **overdue** items surface. A 7-page dashboard shows all of this plus
**analytics**, an **evaluation harness** scores extraction quality
(precision/recall/F1 for explicit vs implicit + hallucination rate), and a
**chat assistant** answers questions about your meetings with cited evidence.

Pipeline in one line:

```
upload → text (transcribe if audio) → structured extraction → evidence grounding
→ confidence + review routing → SQLite → pages / analytics / chat / evaluation
```

---

## 2. Folder-by-folder, file-by-file

### `run.py` (project root)
Starts the web server (`uvicorn app.main:app`, http://127.0.0.1:8000).
Why uvicorn: the standard ASGI server for FastAPI; `reload=True` for development.

### `requirements.txt`
Pinned dependencies so installs are reproducible (no "works on my machine").
FastAPI/Uvicorn (server), Jinja2 (templates), Pydantic (schemas),
python-multipart (file uploads), python-dotenv (.env secrets), pandas+numpy (analytics),
faster-whisper + imageio-ffmpeg (speech-to-text), pypdf + python-docx
(document reading), pytest (tests). (No OpenAI dependency — Gemini only.)

### `app/config.py` + `.env`
Single place for settings: DB path, upload folder, model name, provider choice,
review threshold (0.60). Everything comes from environment variables with safe
defaults — **no secrets in code**, and the app runs with zero config.
Private values live only in the single `.env` file (see `.env.example` for the
format): `GEMINI_API_KEY`, backend/model choices, threshold. `.env` is listed in
`.gitignore` alongside the database and uploads, so `git push` can never leak them.

### `app/llm/backends.py` — Gemini + HF caller with fallback chain
One `generate_json(system, user)` interface for chat and extraction. Gemini is called
via standard-library REST (no SDK install), trying the primary model then
`MIP_GEMINI_FALLBACK` (wrong model names and quota are the common failures); Hugging
Face reuses the whisper-bundled `huggingface_hub`. Keyless providers are skipped and
every exception falls through, so the app degrades instead of crashing. And as a final
net, `extract_meeting()` catches any provider failure and re-runs the offline rules
engine (`provider="rules-fallback"`) — uploads can never HTTP 500.

### `app/schemas.py` — the AI contract
Pydantic models `ActionItem | Decision | Blocker | MeetingExtraction`.
This is the single most important file: it defines exactly what the AI is allowed
to output (`action, owner, deadline, confidence, evidence, commitment_type`).
Downstream code never parses free text — it only touches validated objects.
`evidence` has a minimum-length validator so empty/garbage quotes are rejected
at the boundary.

### `app/llm/prompts.py`
The system prompt + user template for the real LLM path: JSON-only output,
explicit-vs-implicit rules, "quote exactly or skip the item", confidence rubric.
Prompt engineering lives here, separate from code, so it can be tuned without
touching logic.

### `app/llm/providers.py` — two interchangeable extractors
- `RuleBasedProvider` (default, offline): deterministic pattern engine that finds
  explicit promises ("I'll finish X by Friday", "Action: …") and implicit ones
  ("I'll take a look", "someone should…", "let's…", "maybe…"). It resolves owners
  from speaker tags, deadlines from relative words (Friday/tomorrow/EOD → real
  dates), then de-duplicates overlapping hits and drops junk idioms
  ("sleep on it", "thanks"). Output is validated through the same Pydantic
  schemas, so the rest of the system cannot tell it apart from an LLM.
- `GeminiProvider` (used when `GEMINI_API_KEY` is set in `.env`): sends the prompts
  through `llm/backends.py` (stdlib REST, no SDK) and validates the JSON reply into
  `MeetingExtraction`; any failure falls back to rules.
- `get_provider()`: picks Gemini when a key exists, otherwise rules — the app
  never crashes for lack of a key or internet.

### `app/llm/extractor.py` — trust layer
`extract_meeting()` runs a provider, then `ground_and_score()` enforces honesty:
evidence must be a **verbatim transcript substring** or confidence is crushed to
≤0.35 and the item is forced into review; missing owner caps confidence;
implicit items are capped (never high-confidence); anything below threshold gets
`needs_review` + a machine-readable reason. This is where "AI mistakes" become
"human checkpoints" instead of silent errors.

### `app/stt/transcriber.py` — file ingestion
- `.txt/.md/.srt/.vtt` → text (subtitle timestamps stripped).
- `.pdf` → pypdf text extraction; `.docx` → python-docx paragraphs.
- Audio → faster-whisper (`tiny` model). `.wav` is decoded with the Python
  standard library and resampled with numpy; other formats are converted with a
  bundled static ffmpeg — this deliberately **bypasses the fragile PyAV/ffmpeg
  stack** that breaks on Windows. Clear errors are raised for unsupported types
  instead of silent failures.

### `app/database.py` — memory
SQLite via standard library (no ORM version conflicts). Tables: `meetings`,
`decisions`, `actions` (with `status, needs_review, review_reason,
carried_from`), `blockers`. Helpers: `unresolved_actions()`,
`overdue_actions()`, and `carry_forward()` which copies still-open items from an
old meeting into a new one as `carried` — the "history" feature.

### `app/analytics/metrics.py` — the data-analytics half
Pure SQL + standard library (dashboard never breaks if pandas is missing):
`overview()` KPIs, `owner_workload()`, `status_breakdown()`,
`commitment_split()`, `confidence_histogram()`, `overdue_by_owner()`,
`actions_per_meeting()`, `review_queue()`. These feed both the pages and the
Chart.js charts.

### `app/eval/evaluate.py` — the report card
Token-overlap matching (prediction ≈ gold at F1 ≥ 0.5 **and** same
explicit/implicit type = true positive), then precision/recall/F1 per type plus
a **hallucination rate** (evidence not found verbatim). `evaluate_file()` runs a
gold set through any extractor and reports per-case plus macro scores.
Current offline baseline: explicit F1 **1.00**, implicit F1 **0.73**,
hallucination **0.00** (`data/eval_results.json`).

### `app/chat/qa.py` — workspace assistant
Offline-first Q&A over your meetings: small talk + help answered directly;
meeting questions resolved against **structured data first** (overdue, deadlines,
per-owner workload, decisions, blockers, review queue, summaries); anything else
falls back to stemmed transcript search across all meetings with
meeting-labelled quotes. With an API key, an LLM rephrases from the same
material and non-verbatim quotes are dropped. Never returns "I don't know"
without telling you what it *can* answer.

### `app/main.py` — pages + API
FastAPI routes. Pages: `/` Home (hero + how-it-works + demos + KPIs),
`/meetings`, `/meetings/{id}` (pipeline strip + chat removed → now on
Decisions), `/actions` (status/type/owner/**meeting**/search filters),
`/decisions` (+ assistant), `/analytics`, `/review` (+ meeting filter),
`/upload` (+ workspace reset). Action items, decisions and review lists are grouped by
meeting (newest first, transcript order inside) via `group_by_meeting()`, so imports
never interleave. APIs: `/api/stats`, `/api/review`,
`/api/export/actions`, `/api/chat`, `/api/meetings/{id}/chat`,
approve/status/reset POSTs.

### `app/templates/` + `app/static/app.css`
Jinja2 pages sharing `base.html` (header, sticky nav, footer, review actions JS).
Professional light theme, aligned 1200px column, empty states on every list,
responsive tables. No Streamlit, no JS build step — Chart.js via CDN with
server-rendered tables as fallback.

### `data/`
`sample_transcripts/` (3 messy meetings used by seeding + eval),
`eval_gold.json` (hand-labelled truth: 3 cases × 5 gold actions),
`eval_results.json` (latest scores), `meetings.db` (your workspace, starts empty),
`uploads/` (original uploaded files), `analytics/` (pandas CSV/JSON exports).

### `samples/` — your test kit
4 upload-ready transcripts (sales, standup, onboarding, implicit-heavy
brainstorm) + spoken `.wav`/`.mp3` versions + narration scripts + README telling
you what to check after each upload.

### `scripts/`
`seed.py` (loads the 3 demo meetings), `evaluate.py` (runs the harness, prints
the P/R/F1 table), `analytics_report.py` (pandas deep-dive → CSVs + summary).

### `tests/test_extraction.py`
3 smoke tests: structured+grounded output, review routing of low-confidence
items, evaluation harness sanity. Run with `pytest -q`.

---

## 3. AI techniques used — and why each one

| Technique | Where | Why this one |
|---|---|---|
| Structured outputs (Pydantic) | `schemas.py`, providers | Free-form LLM text needs fragile parsing; schemas make output machine-usable and testable. The reliability core of the project. |
| Prompt engineering | `prompts.py` | Cheapest way to control behaviour: JSON-only, quote-or-skip, confidence rubric — no training needed. |
| Evidence grounding | `extractor.py` | Kills hallucinations by construction: no verbatim quote → no trust. Measured as hallucination rate = 0.0. |
| Confidence + human-in-the-loop | `extractor.py`, review page | Ambiguity is inevitable in meetings; routing (< 0.60, no owner, weak evidence) to humans beats pretending the AI is sure. |
| Explicit vs implicit modelling | providers, eval | The product insight: soft commitments ("I'll take a look") are where meetings leak. Scored separately so the weakness is visible. |
| Speech-to-text | `transcriber.py` | Meetings arrive as audio; faster-whisper `tiny` runs on CPU with no key. |
| Extractive QA + stemming + intent routing | `chat/qa.py` | Answers from *your* data with citations work fully offline; LLM only upgrades phrasing. |
| Evaluation harness | `eval/`, `scripts/evaluate.py` | Without P/R/F1 split by type + hallucination rate, "AI works" is a feeling. This makes it a number — and the resume line. |
| Deterministic fallback provider | `providers.py` | Guarantees the demo, tests, analytics and eval run anywhere, free, with zero errors. A real-LLM-only project would be dead without a key. |

Supporting (non-AI but necessary): FastAPI (modern API+pages in one), SQLite-stdlib
(zero-dependency storage), pandas (analytics credibility), Chart.js (no-build
charts), pytest (regression safety).

---

## 4. Where fine-tuning happened — honest answer

**Nowhere: no model was fine-tuned in this project.** No weights were trained, no
training loop exists, and none is needed for the current design. Saying otherwise
would be false, so do not claim it.

What *was* tuned (the legitimate, non-model kind):
- **Prompt tuning** — wording of `SYSTEM_PROMPT` and the confidence rubric.
- **Threshold tuning** — review cutoff 0.60; implicit caps; grounding penalty 0.35.
- **Pattern tuning** — regexes, junk/idiom list, dedup rules, implicit-first ordering
  (this pass took implicit F1 0.49 → 0.73).
- **Matching tuning** — overlap threshold 0.5 in evaluation.

If you ever want *actual* fine-tuning, the path is ready: `data/eval_gold.json`
is already labelled data — grow it to ~200+ meetings, train a classifier head
(explicit/implicit/none per sentence) or instruction-tune an open model on
transcript→JSON pairs, and compare against the `eval_results.json` baseline with
the same harness. That would be a genuine fine-tuning story on top of this base.
