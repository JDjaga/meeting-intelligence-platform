# 10. Where Tuning Happened (and the fine-tuning question)

## Direct answer: no model fine-tuning was done — and that is intentional
"Fine-tuning" usually means gradient-training a model on labelled data. This project has
~15 gold actions: far too few to fine-tune anything without overfitting. Instead, all
tuning happened in **prompts, patterns, thresholds and rules** — transparent, reversible,
and debuggable. Every past bug (duplicate rows, the "Sleep" action, "I'll sync up" marked
explicit) was fixed by tuning these, in minutes, with eval scores proving each fix
(overall F1 0.56 → 0.82 across the fixes).

## Everything that was tuned, and where
- **Review threshold 0.60** (`config.REVIEW_THRESHOLD`): implicit items score 0.52–0.57,
  solid explicit items 0.78–0.85 — 0.60 cleanly separates "needs a human" from "trusted".
- **Implicit-first ordering** (`providers.py`): hedged sentences are claimed by implicit
  patterns before greedy explicit ones.
- **Case-sensitive explicit matching**: names must be capitalised (killed "team will sleep").
- **`JUNK_RE` idiom list + lone-verb fallback**: pleasantries never become tasks.
- **Dedup (`_is_dup`)**: same sentence via two patterns → one item.
- **Confidence caps**: implicit ≤ 0.70, owner-less ≤ 0.59, hallucinated evidence ≤ 0.35.
- **Vague-word list** (`VAGUE_RE`): someone/maybe/probably/soon… force low confidence.
- **Chat**: stopword list, suffix stemmer, prefix-match length ≥ 4, retrieval depth k=4–6.
- **Eval match threshold 0.5**: tolerant to paraphrase, strict enough to reject neighbours.
- **List ordering** — newest meeting first, transcript order inside (`group_by_meeting`);
  confidence-sort scattered IDs across meetings and confused readers.
- **Failure tuning** — Gemini primary→fallback model chain, then rules-fallback in the
  orchestrator: tuned from a real HTTP 500 caused by a bad model name.

## How to tune further / do real fine-tuning later
1. Use the app: every Approve/correction in the review queue is a labelled example.
2. Export them (`/api/export/actions`) into `eval_gold.json` format — at ~200+ examples,
   rules hit their ceiling and a fine-tuned small model (or few-shot LLM) takes over.
3. Compare with `scripts/evaluate.py` before/after — the harness is already provider-agnostic.
