# ProjectActionGraph — End-to-End Meeting Intelligence Platform

Convert messy meeting transcripts into **reliable decisions, action items, owners, deadlines,
blockers and follow-ups** — with evidence citations, confidence scoring and human review.
LLM engineering **+** data-analytics in one project. No Streamlit — FastAPI + dashboard UI.

## Resume line
> Built an end-to-end LLM meeting-intelligence platform extracting structured decisions and
> action items (explicit F1 **1.00**, implicit F1 **0.73**, hallucination rate **0.0**),
> with evidence-based citations and confidence-driven human review.

## Architecture
```
transcript (.txt/.srt/.vtt) or audio (.mp3/.wav)
        │ ingest (app/stt/transcriber.py)
        ▼
LLM extraction — STRUCTURED OUTPUTS ONLY (Pydantic), never free-form parsing
  app/llm/prompts.py → providers (Gemini JSON | offline rules fallback)
        │ ground_and_score: evidence must be verbatim quote, else hallucination penalty
        ▼
SQLite store (meetings / decisions / actions / blockers) + carry-forward of open items
        ├── FastAPI dashboard (/): KPIs, review queue, meetings, actions, decisions
        │   + Chart.js analytics: workload, status, explicit-vs-implicit, confidence
        └── Analytics exports (data/analytics/): CSVs + summary.json (pandas)
        └── Evaluation (data/eval_results.json): P/R/F1 explicit vs implicit + hallucination
```

## Quickstart
```powershell
pip install -r requirements.txt
python run.py                     # dashboard at http://127.0.0.1:8000
python scripts/seed.py            # load 3 messy sample meetings (works offline)
python scripts/evaluate.py        # P/R/F1 explicit vs implicit + hallucination rate
python scripts/analytics_report.py# pandas deep-dive → data/analytics/
python -m pytest tests/ -q        # 3 smoke tests
```

## Keys (one `.env` file, git-ignored)
Paste `GEMINI_API_KEY` in `.env` (see `.env.example`) for real Gemini extraction + chat;
leave it empty for the offline engine. `.gitignore` hides `.env`, the database and
uploads, so `git push` never leaks secrets. Failures fall back automatically:
backup Gemini model → offline rules (`provider="rules-fallback"`), uploads never 500.


## LLM details
- **Structured schema** (`app/schemas.py`): `action | owner | deadline | confidence | evidence`
  (+ `commitment_type: explicit|implicit`), decisions, blockers — all Pydantic-validated.
- **Explicit vs implicit**: direct promises ("I'll finish this Friday") vs soft offers
  ("I'll take a look", "someone should…").
- **Evidence enforcement** (`app/llm/extractor.py::ground_and_score`): quote must be an exact
  transcript substring or confidence is crushed to ≤0.35 and the item is forced into review.
- **Confidence → review**: anything `< MIP_REVIEW_THRESHOLD (0.60)`, missing owner, or
  hallucinated evidence lands in the **human review queue** (approve/correct via dashboard).
- **Provider switch**: paste `GEMINI_API_KEY` in `.env` for real Gemini LLM extraction + chat;
  default `auto` falls back to the deterministic offline extractor — same schema, zero cost.
- **History**: open actions `carry_forward()` into the next meeting; overdue computed vs today.

## Data-analytics angle
- Dashboard KPIs: completion %, overdue, review rate, explicit/implicit split.
- Charts: owner workload, status donut, confidence histogram, overdue-by-owner, actions-per-meeting.
- `scripts/analytics_report.py` (pandas): `owner_workload.csv`, `actions_full.csv`, `summary.json`.
- Evaluation harness (`app/eval/evaluate.py`): token-overlap matching, macro P/R/F1 per type.

## Current baseline (offline rules provider, `data/eval_results.json`)
| slice | P | R | F1 |
|---|---|---|---|
| explicit | 1.000 | 1.000 | **1.000** |
| implicit | 0.617 | 0.889 | **0.726** |
| overall | 0.738 | 0.933 | 0.823 |
| hallucination rate | — | — | **0.000** |

Swap in an LLM key to beat the baseline — the harness measures it identically.

## API
| route | purpose |
|---|---|
| `GET /` | overview (KPIs + digest charts + latest meetings) |
| `GET /meetings`, `GET /meetings/{id}` | meeting list + per-meeting detail (transcript + evidence) |
| `GET /actions` | action items grouped by meeting (?status=&ctype=&owner=&meeting=&q= filters) |
| `GET /decisions` | decisions log grouped by meeting (?meeting= filter) + workspace chat |
| `GET /analytics` | full charts + overdue + per-meeting tables (global view) |
| `GET /review` | human review queue grouped by meeting (?meeting= filter) |
| `POST /api/chat` | workspace assistant on the Decisions page: deadlines, owners, decisions, blockers, summaries, small talk (evidence-cited) |
| `POST /api/meetings/{id}/chat` | same assistant scoped to one meeting file |
| `GET /upload` + `POST /upload` | ingest form → extract → store (+ optional `carry_from`) |
| `GET /api/stats`, `/api/review`, `/api/export/actions` | charts, queue, export |
| `POST /api/actions/{id}/approve`, `/api/actions/{id}/status` | human review + status |
