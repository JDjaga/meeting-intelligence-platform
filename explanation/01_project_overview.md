# 1. Project Overview

## What it is
ProjectActionGraph is an end-to-end **Meeting Intelligence Platform**. It converts messy
meeting transcripts or recordings into reliable, trackable work:
**decisions, action items, owners, deadlines, blockers and follow-ups**.

## The problem it solves
Meetings produce vague memory ("I think someone said they'd look into it"). Owners,
deadlines and decisions slip. This software replaces memory with evidence: every
extracted item carries the **exact transcript quote** it came from and a
**confidence score**. Low-confidence items wait in a **human review queue** instead of
silently entering reports.

## The pipeline (5 stages)
1. **Ingest** — upload `.txt/.srt/.vtt`, `.pdf/.docx`, or audio `.mp3/.wav/.m4a`. Audio is
   transcribed with faster-whisper; documents are text-extracted.
2. **Extract (structured outputs only)** — the meeting becomes Pydantic objects:
   `action | owner | deadline | confidence | evidence | commitment_type (explicit/implicit)`,
   plus decisions, blockers, follow-ups. No free-form text is ever parsed downstream.
3. **Ground + score** — each evidence quote must appear verbatim in the transcript or the
   item is penalised (confidence ≤ 0.35) and forced into review. Implicit commitments are
   capped at 0.70. Anything below 0.60 (or owner-less) goes to human review.
4. **Store + carry** — SQLite keeps every meeting; open actions carry forward into the
   next meeting; overdue is computed against today.
5. **Use** — 7 dashboard pages (Home, Meetings, Action items, Decisions, Analytics,
   Review queue, New meeting) plus a workspace chat assistant that answers questions
   with cited quotes, plus a precision/recall/F1 evaluation harness.

## Resume line
Built an end-to-end LLM meeting-intelligence platform extracting structured decisions
and action items (explicit F1 1.00, implicit F1 0.73, hallucination rate 0.0), with
evidence-based citations and confidence-driven human review.
