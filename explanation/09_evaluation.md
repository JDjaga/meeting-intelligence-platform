# 9. Evaluation (`app/eval/evaluate.py`, `scripts/evaluate.py`)

## What is measured
For each gold-labelled meeting (`data/eval_gold.json`: transcript + gold actions with
`commitment_type`), predictions are matched to gold by **token-overlap F1 ≥ 0.5 on the
action text** (paraphrase-tolerant). Then:
- **Precision / Recall / F1 separately for explicit and implicit**, plus micro overall;
- **Hallucination rate** = fraction of predicted items whose evidence is NOT a verbatim
  transcript substring;
- Reported **per meeting and macro-averaged**, saved to `data/eval_results.json`.

## Current baseline (offline rules provider)
| slice | P | R | F1 |
|---|---|---|---|
| explicit | 1.000 | 1.000 | 1.000 |
| implicit | 0.617 | 0.889 | 0.726 |
| overall | 0.738 | 0.933 | 0.823 |
| hallucination rate | — | — | 0.000 |

Run it: `python scripts/evaluate.py`. `run_fn` inside can be pointed at any provider, so
plugging in `GEMINI_API_KEY` measures the real LLM on the identical harness — that
before/after number is the strongest resume artefact in the project.

## Known limits (honest)
Gold set is small (3 meetings, ~15 actions); scores will move on bigger data. Overlap
matching can forgive genuinely different tasks sharing words. Implicit recall (< 1.0)
is where an LLM provider should beat rules.
