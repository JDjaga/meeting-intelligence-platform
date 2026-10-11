# 13. Interview Questions & Strong Answers

## Technical

**Q: Why structured outputs instead of parsing the LLM's free-form reply?**
A: Free-form text needs fragile regex parsing that breaks silently on rephrasing. I defined
Pydantic schemas as the contract — both providers return validated objects, so bad output
fails loudly at validation instead of corrupting analytics. The LLM is further constrained
with JSON-mode decoding (`responseMimeType`) at temperature 0.1.

**Q: How do you prevent hallucinations?**
A: Three layers: (1) the prompt demands exact copied quotes; (2) `ground_and_score`
rejects any evidence that is not a verbatim transcript substring, crushing confidence to
≤ 0.35 and forcing human review — measured hallucination rate is 0.0; (3) chat citations
go through the same verbatim check.

**Q: Why split explicit vs implicit commitments?**
A: They behave differently — soft promises ("someone should…") deserve lower confidence
(capped at 0.70) and separate measurement. The eval reports F1 per type (1.00 vs 0.73),
which tells me exactly where the system is weak.

**Q: How does the confidence/review system work?**
A: Rule-based scoring (owner + deadline + verbatim evidence ≈ 0.85; vague/owner-less ≈
0.52) with threshold 0.60 tuned so implicit items land in review and solid ones pass.
Review stores a machine-written reason, and Approve lets a human correct fields.

**Q: Why no fine-tuning?**
A: Only ~15 gold labels exist — fine-tuning would overfit. All tuning is in prompts,
patterns, thresholds and rules (overall F1 went 0.56 → 0.82 that way). The review queue
is designed as a label collector: at ~200+ corrections, fine-tuning becomes justified,
and the eval harness is already provider-agnostic to prove the gain.

**Q: Why faster-whisper tiny, and how did you survive the Windows AV clash?**
A: Local, private, free, real-time on CPU. When faster-whisper's PyAV decoding broke on
version drift, I bypassed it: stdlib `wave` for WAV, bundled static ffmpeg for the rest,
passing numpy arrays to whisper — its fragile file path is never touched.

**Q: Why not embeddings/vector DB for chat?**
A: Scale doesn't justify it: retrieval over a few dozen sentences with stemming +
prefix matching answers in milliseconds with zero dependencies. Structured intents
(deadlines, owners, blockers) answer from the database precisely — vectors would only
add noise at this scale.

**Q: How is evaluation fair to paraphrasing?**
A: Predictions match gold at token-overlap F1 ≥ 0.5 on action text, and commitment type
must agree for the split metrics — wording can differ, meaning cannot.

**Q: What happens when the LLM API fails mid-upload?**
A: Two fallbacks: Gemini retries on a backup model (wrong names/quota cause most failures),
then the orchestrator catches any exception and re-runs the offline rules engine, marking
`provider="rules-fallback"`. Uploads can never HTTP 500 — I verified this with a bad key.

**Q: How do two patterns matching one sentence not create duplicates?**
A: Shared `seen` set on evidence plus substring dedup on normalised action text
(`_is_dup`), with implicit patterns running first so hedged phrasing wins the type label.
A: Shared `seen` set on evidence plus substring dedup on normalised action text
(`_is_dup`), with implicit patterns running first so hedged phrasing wins the type label.

**Q: Why SQLite with raw SQL instead of Postgres/SQLAlchemy?**
A: Zero setup, zero version conflicts, single file — right-sized for this workload.
Analytics uses plain SQL so the dashboard can never break on a missing library; pandas
is quarantined to offline CSV reports.

## Practical / behavioural

**Q: Walk me through the demo in 2 minutes.**
A: Home → "Load sample: sales meeting" → meeting page (evidence quotes) → Review queue
(approve one) → Decisions page chat ("What is overdue?") → Analytics (completion moved).
Every stage is one click from the last.

**Q: What was the hardest bug?**
A: Duplicate + junk rows ("Sleep" as an explicit action). Root causes: case-insensitive
name matching ("team will sleep") and two patterns claiming one sentence. Fixed with
case-sensitive explicit matching, an idiom filter, and dedup — eval F1 jumped 0.56 → 0.82.

**Q: How did you decide the 0.60 threshold?**
A: Measured, not guessed: implicit items score 0.52–0.57, solid explicit 0.78–0.85, so
0.60 separates "needs a human" from "trusted" on real samples.

**Q: What would you do with 1,000 meetings?**
A: Postgres, background transcription queue, embeddings for cross-meeting search,
per-team analytics, and fine-tune on the accumulated review-queue labels.

**Q: What would you do differently?**
A: Collect gold labels from day one (bigger eval set sooner) and add user accounts so
"my tasks" views and Vrpermissions exist alongside owner tracking.
