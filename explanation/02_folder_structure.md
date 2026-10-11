# 2. Folder Structure

```
meeting_intelligence-platform/
├── app/                     # the application (all runtime code)
│   ├── main.py              # FastAPI app: 7 pages + APIs (upload, chat, review, reset…)
│   ├── config.py            # reads the single `.env` file: keys, models, thresholds
│   ├── schemas.py           # THE contract: ActionItem, Decision, Blocker, MeetingExtraction
│   ├── database.py          # SQLite storage (stdlib only): meetings/decisions/actions/blockers
│   ├── llm/                 # extraction brain
│   │   ├── prompts.py       # system + user prompts forcing JSON-only structured output
│   │   ├── providers.py     # Gemini JSON provider + offline rules fallback provider
│   │   ├── backends.py      # Gemini (stdlib REST) + Hugging Face caller with fallback chain
│   │   └── extractor.py     # orchestrator: extract → ground → score → review-route (never 500s: any LLM failure falls back to rules)
│   ├── stt/
│   │   └── transcriber.py   # ingest(): txt/srt/vtt + pdf/docx + audio→whisper
│   ├── chat/
│   │   └── qa.py            # workspace assistant: intents + transcript search + citations
│   ├── analytics/
│   │   └── metrics.py       # KPIs, chart payloads, review queue, group_by_meeting()
│   ├── eval/
│   │   └── evaluate.py      # precision/recall/F1 per explicit/implicit + hallucination rate
│   ├── templates/           # 9 Jinja pages (base, overview, meetings, meeting, actions,
│   │                        # decisions + chat, analytics, review, upload)
│   └── static/app.css       # professional light theme, one shared stylesheet
├── .env                     # YOUR private keys (git-ignored — never pushed to GitHub)
├── .env.example             # safe template showing the format with empty values
├── .gitignore               # hides .env, the database and uploads from git
├── data/
│   ├── meetings.db          # created on first run (starts empty; git-ignored)
│   ├── sample_transcripts/  # 3 messy meetings used by seed + eval
│   ├── eval_gold.json       # hand-labelled gold actions per meeting (evaluation truth)
│   ├── eval_results.json    # last evaluation run output
│   └── analytics/           # pandas exports: actions_full.csv, owner_workload.csv, summary.json
├── samples/                 # files YOU upload to try it (4 transcripts, 2 spoken audios + scripts, guide)
├── docs/
│   └── PROJECT_EXPLAINED.md # single-file full guide (mirrors this folder, condensed)
├── scripts/
│   ├── seed.py              # loads the 3 sample meetings into a fresh DB
│   ├── evaluate.py          # runs the eval harness, prints P/R/F1 table
│   └── analytics_report.py  # pandas deep-dive → data/analytics/
├── tests/test_extraction.py # 3 smoke tests (structure, grounding, review, eval)
├── explanation/             # this documentation (00 summary → 13 interview Q&A)
├── requirements.txt         # pinned dependencies (no OpenAI — Gemini only)
├── run.py                   # `python run.py` → dashboard at 127.0.0.1:8000
└── README.md                # setup + architecture + baseline scores + API table
```

Design rule followed throughout: **AI code (`llm/`, `chat/`, `eval/`) never touches the
database or HTML directly** — it consumes text and returns validated objects. `main.py`
and `database.py` do all storage and rendering. That separation is what keeps the
project from becoming tangled.
