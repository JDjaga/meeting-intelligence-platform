# Samples — upload these to try the platform

Go to **＋ New meeting** (`/upload`), pick a file, hit **Ingest + Extract**.

| file | what it tests | what to check after upload |
|---|---|---|
| `01_sales_weekly_sync.txt` | classic mix: 2 decisions, explicit + implicit actions, 1 blocker | mostly explicit; Karan's hedged item lands in **Review queue** |
| `02_product_standup.txt` | deadlines ("tomorrow", "EOD"), implicit suggestions | deadlines resolved to real dates; flag-audit goes to review |
| `03_client_onboarding_call.txt` | external attendee names, phased decision, DPA blocker | attendees parsed; Okta deadline = next Monday |
| `04_brainstorm_implicit_heavy.txt` | almost everything is vague/hedged | most items **implicit**, low confidence → review queue fills up; compare with `01` |

Also in `data/sample_transcripts/` (used by `scripts/seed.py` + evaluation):
sprint_planning, design_review, incident_retro.

## Audio samples (speech-to-text path)

| file | what it is |
|---|---|
| `05_sales_sync.wav` / `05_sales_sync.mp3` | same sales meeting, **spoken** (~70 s, single voice) — tests STT → extraction |
| `06_brainstorm.wav` | implicit-heavy brainstorm, **spoken** (~55 s) — tests STT on hedged speech |
| `05_sales_sync_narration.txt`, `06_brainstorm_narration.txt` | the scripts that were read aloud (reference) |

Upload a `.wav`/`.mp3` on **＋ New meeting** exactly like a transcript — it gets
transcribed with faster-whisper (`tiny` model, auto-downloaded once, ~75 MB) then
extracted normally. Expect 1–2 small mishears (e.g. "sales sink") — that is realistic
STT noise, and evidence grounding still holds because quotes come from the transcript.

**Things to try per upload:**
1. Open the meeting page — every action shows its exact transcript **evidence quote**.
2. Check `/review` — vague items are waiting for approve/correct.
3. Mark something Done on `/actions`, watch `/analytics` completion % move.
4. Upload `04`, then upload `01` with **carry_from = that meeting's #** — open items carry over.
