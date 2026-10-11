# 7. Chat Assistant (`app/chat/qa.py`)

Lives on the Decisions page as "Ask about your meetings" (`POST /api/chat`), with a
single-meeting variant (`POST /api/meetings/{id}/chat`). Both return
`{answer, evidence[{meeting, quote}], method}`.

## How a question is understood (in order)
1. **Small talk** — pure greetings/thanks/goodbyes and "what can you do" answered directly.
2. **Structured intents** (answered from the database, precise):
   - overdue (deadline < today, open), deadlines (dated open items, sorted),
   - owner ("What is pending for Ritu?" — name matched against real owners),
   - decisions, blockers, review queue, summaries ("summarise everything" / per-meeting).
   Meeting scoping: if title words appear in the question, intents narrow to that meeting.
3. **Transcript search fallback** — stemmed keyword overlap (`blocking/blocker/blocks`
   match via suffix-stripping + prefix matching) across all meetings; quotes labelled
   with their meeting.
4. **Helpful dead-end** — never the old "could not find anything": it states what was
   searched and what *can* be asked.
5. **LLM upgrade (optional)** — with any key set (`GEMINI_API_KEY`
   or `HF_TOKEN`), the retrieved material is sent for rephrasing via `llm/backends.py`,
   which tries Gemini → Hugging Face (`MIP_CHAT_BACKEND` forces one).
   Returned quotes are re-validated as verbatim substrings.

`method` in the response tells you which path answered: `assistant`, `structured`,
`extractive`, or `llm`.
