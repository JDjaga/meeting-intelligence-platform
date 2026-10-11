# Explanation Index — read in order

This folder documents the entire ProjectActionGraph build: what each part does,
which AI techniques are used and why, and where all tuning happened.

| # | File | Covers |
|---|---|---|
| 0 | `00_project_summary.md` | 2-minute overall summary (start here) |
| 1 | `01_project_overview.md` | What the software is, the pipeline, resume line |
| 2 | `02_folder_structure.md` | Every folder and what lives in it |
| 3 | `03_app_core_files.md` | `main.py`, `config.py`, `database.py`, `schemas.py`, `run.py` |
| 4 | `04_llm_engineering.md` | Structured outputs, prompts, providers, grounding, confidence, review |
| 5 | `05_ai_techs_and_why.md` | Each AI technique, why this one, what was rejected |
| 6 | `06_ingestion_stt.md` | Transcript / PDF / DOCX / audio pipeline, whisper, ffmpeg |
| 7 | `07_chat_assistant.md` | Question understanding, intents, retrieval, citations |
| 8 | `08_analytics.md` | KPIs, charts, pandas exports |
| 9 | `09_evaluation.md` | Precision/recall/F1, hallucination rate, current scores |
| 10 | `10_tuning.md` | Where tuning happened (no model fine-tuning — read why), how to tune further |
| 11 | `11_api_routes.md` | Every page and API endpoint |
| 12 | `12_how_to_run.md` | Setup, demo flows, troubleshooting |
| 13 | `13_interview_questions.md` | Technical + practical interview Q&A with strong answers |

One-line mental model: **meeting file in → structured commitments out → human confirms the unsure ones → track and analyse.**
