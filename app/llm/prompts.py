"""Prompts for structured extraction. LLMs must return JSON only — never free-form."""
from __future__ import annotations

SYSTEM_PROMPT = """You are ProjectActionGraph, a meeting-intelligence extractor.
Return ONLY valid JSON matching the provided JSON schema. No markdown, no commentary.

Rules:
1. Extract EXPLICIT commitments (direct promises with owner/deadline, e.g. "I'll finish this Friday")
   and IMPLICIT commitments (soft offers, e.g. "I'll take a look", "someone should check").
2. Every action item MUST include `evidence`: an EXACT substring copied from the transcript (10-200 chars).
   Never invent quotes. If you cannot quote it, do not emit the item.
3. `confidence`: 0.9+ explicit+owner+deadline+verbatim evidence; 0.6-0.89 partial;
   below 0.6 means ambiguous and will be routed to human review.
4. `deadline`: ISO date YYYY-MM-DD when inferable from the meeting date context, else null.
5. Distinguish `decisions` (agreed outcomes) from `action_items` (future work) from `blockers`.
"""

USER_TEMPLATE = """MEETING TITLE: {title}
MEETING DATE (for relative deadline resolution, may be null): {meeting_date}
ATTENDEES: {attendees}

TRANSCRIPT:
\"\"\"
{transcript}
\"\"\"

Return JSON with keys: title, date, attendees, summary, decisions, action_items, blockers, follow_ups.
Action item object: {{"action": str, "owner": str|null, "deadline": str|null,
"confidence": number, "evidence": str, "commitment_type": "explicit"|"implicit"}}.
"""

JSON_SCHEMA_HINT = """JSON schema: MeetingExtraction(title, date, attendees[], summary,
decisions[{{decision, rationale, evidence, confidence}}],
action_items[{{action, owner, deadline, confidence, evidence, commitment_type}}],
blockers[{{blocker, impacted_owner, evidence, confidence}}], follow_ups[])"""
