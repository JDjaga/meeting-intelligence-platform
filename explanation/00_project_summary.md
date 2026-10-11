# Project Summary (read this first — 2 minutes)

## One sentence
ProjectActionGraph turns messy meeting transcripts or recordings into structured,
trackable work — decisions, action items, owners and deadlines — where every item cites
its exact transcript quote and carries a confidence score.

## Why it exists
Meetings leak commitments: "I'll take a look" is forgotten, nobody owns follow-ups,
decisions get re-argued. The software replaces memory with evidence — vague promises
are caught, scored, and either trusted or sent to a human, never silently dropped.

## How it works (5 stages, 30 seconds each)
1. **Ingest** — upload transcript (txt/srt/vtt), document (pdf/docx) or audio
   (mp3/wav/…) transcribed locally with faster-whisper.
2. **Extract** — the meeting becomes validated objects
   (`action | owner | deadline | confidence | evidence | explicit/implicit`), never free text.
3. **Trust-filter** — quotes must match the transcript verbatim; confidence below 0.60,
   missing owners, or weak evidence route to a human review queue.
4. **Track** — history persists; open actions carry into the next meeting; overdue is flagged.
5. **Analyse & ask** — dashboard (KPIs, charts, per-owner workload), pandas exports,
   a chat assistant that answers with cited quotes, and a P/R/F1 evaluation harness.

## Proof it works
Explicit F1 **1.00**, implicit F1 **0.73**, hallucination rate **0.0** on a labelled set;
3/3 smoke tests green; every claim re-measurable with `python scripts/evaluate.py`.

## Stack in one line
FastAPI + SQLite + Pydantic structured outputs (+ offline rules engine, Gemini JSON
ready) + faster-whisper STT + Chart.js dashboard + pandas reports + pytest.
