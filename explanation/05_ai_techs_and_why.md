# 5. AI Techniques Used — and Why Each One

| Technique | Where | Why this one (and what was rejected) |
|---|---|---|
| **Structured outputs** (Pydantic) | `schemas.py`, both providers | Free-form LLM text needs fragile regex parsing that breaks silently. Schema validation fails loudly instead. Rejected: parsing bullet lists / markdown. |
| **JSON-mode decoding** (`responseMimeType`) | `llm/backends.py` Gemini | Constrains the model to valid JSON at decode time — cheaper and more reliable than "please reply in JSON" prompting alone. |
| **Low temperature (0.1)** | Gemini calls | Extraction must be deterministic; creativity causes hallucinations. |
| **Evidence grounding** | `extractor.py` | A quote that is not a transcript substring is, by definition, invented. Exact-substring check is the simplest possible hallucination detector — no embedding model needed. |
| **Confidence scoring + threshold routing** | extractor, `config.REVIEW_THRESHOLD` | Accepts that AI is uncertain; routes ambiguity to humans (like spellcheck underlines) instead of pretending certainty. Threshold 0.60 was tuned on the 3 sample meetings (see file 10). |
| **Explicit vs implicit split** | schemas, providers, eval | Soft commitments ("someone should…") behave differently from promises — different confidence caps, different F1 measured separately. |
| **Deterministic offline fallback** | `RuleBasedProvider` | Guarantees the demo, tests, seed and eval run with no key, no cost, no network. Pattern engines are transparent and debuggable; every earlier bug (dupes, "Sleep") was fixable in minutes. |
| **Speech-to-text (faster-whisper tiny, int8)** | `transcriber.py` | Local, private, free; tiny+int8 runs on CPU in ~real-time. Rejected: cloud STT APIs (cost/keys/network). |
| **Extractive QA + intent engine** | `chat/qa.py` | Offline chat answers from structured rows first (precise), transcript search second (grounded), small-talk direct. Stemming + prefix matching handles "blocking/blocker/blocks". Rejected: vector DB + embeddings (heavy dependency for 3–30 meetings; keyword search wins at this scale). |
| **Multi-LLM backends** (Gemini → HF auto-fallback) | `llm/backends.py`, chat | Chat tries providers in order; first configured key wins, failures fall through silently. Gemini uses stdlib REST (no SDK), HF reuses the whisper-bundled `huggingface_hub`. No key = offline mode, never an error. |
| **Token-overlap eval matching (F1 ≥ 0.5)** | `eval/evaluate.py` | Fair to paraphrase: a prediction counts if it overlaps the gold action's meaning, not exact wording. |
| **Deadline normalisation** | providers | Relative words ("Friday", "EOD") are useless in analytics; ISO dates enable overdue computation. |
| **SQLite + stdlib, no ORM** | `database.py` | Zero version conflicts, zero setup, git-friendly. Rejected: Postgres (overkill), SQLAlchemy (dependency weight). |
| **FastAPI + Jinja + Chart.js** | `main.py`, templates | No-Streamlit requirement; server rendering + CDN charts = no JS build step, works offline except charts. |
| **pandas (offline reports only)** | `scripts/analytics_report.py` | Dashboard uses plain SQL (always works); pandas is reserved for CSV deep-dives, so a missing/slow pandas never breaks the app. |

What was deliberately NOT used: model fine-tuning (no labelled corpus large enough — see file 10),
embeddings/vector search (scale does not justify it), cloud APIs as hard dependencies
(everything degrades to working offline).
