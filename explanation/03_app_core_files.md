# 3. App Core Files (what each file does)

## `app/schemas.py` — the contract everything obeys
Defines `ActionItem` (`action | owner | deadline | confidence | evidence | commitment_type`),
`Decision`, `Blocker`, `MeetingExtraction` as Pydantic v2 models. Validators reject evidence
shorter than 5 chars and clamp confidence to 0–1. **Why it matters:** downstream code
(dashboard, analytics, eval) never parses text — it reads fields. If the LLM returns
garbage, validation fails loudly instead of corrupting your data.

## `app/main.py` — pages + APIs
FastAPI app. Page routes render Jinja templates with data from `analytics/metrics.py`;
API routes mutate state (upload ingest, approve/done, chat, reset, demo loader).
Helper `_meeting_record()` assembles one meeting + its actions/decisions/blockers for
the chat engine. `base_ctx()` injects the review-queue badge count into every page.

## `app/config.py` — knobs, no hardcoding
`DB_PATH`, `UPLOAD_DIR`, `GEMINI_API_KEY`/`MIP_GEMINI_MODEL` (empty = offline mode),
`MIP_PROVIDER` (`auto|gemini|rules`), `REVIEW_THRESHOLD` (default 0.60). Change behaviour
with environment variables, not code edits.

## `app/database.py` — storage, stdlib only
Raw `sqlite3` (no ORM, so no version conflicts). Four tables:
- `meetings` (title, date, full transcript, summary, attendees JSON)
- `decisions`, `blockers` (each tied to a meeting, each with evidence + confidence)
- `actions` (full schema + `status` open/done/carried/dropped + `needs_review` flag +
  `carried_from` lineage for carry-forwards)
Functions: `connect()` (auto-creates schema), `insert_meeting()`, `insert_extraction()`,
`unresolved_actions()`, `overdue_actions()`, `carry_forward()` (copies open items from
meeting A into meeting B as `carried`, preserving lineage).

## `run.py` — one-line launcher
`python run.py` starts uvicorn on 127.0.0.1:8000 with reload. No CLI flags to remember.
