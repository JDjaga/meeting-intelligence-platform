"""Orchestrator: extract -> ground evidence -> score confidence -> route to review."""
from __future__ import annotations
from app import config
from app.schemas import MeetingExtraction
from app.llm.providers import get_provider


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def ground_and_score(ext: MeetingExtraction, transcript: str) -> MeetingExtraction:
    """Enforce: evidence must be an exact transcript substring.
    Hallucinated evidence -> confidence penalty + forced human review."""
    t_norm = _norm(transcript)
    for a in ext.action_items:
        reasons: list[str] = []
        if _norm(a.evidence) not in t_norm:
            a.confidence = min(a.confidence, 0.35)
            reasons.append("evidence not found verbatim in transcript (possible hallucination)")
        if not a.owner:
            a.confidence = min(a.confidence, 0.59)
            reasons.append("owner missing")
        if a.commitment_type == "implicit" and a.confidence > 0.75:
            a.confidence = 0.70  # cap: implicit is never high-confidence
            reasons.append("implicit commitment capped")
        if a.confidence < config.REVIEW_THRESHOLD:
            a.needs_review = True
            if not reasons:
                reasons.append(f"confidence {a.confidence:.2f} < {config.REVIEW_THRESHOLD}")
            a.review_reason = "; ".join(reasons)
    for d in ext.decisions:
        if _norm(d.evidence) not in t_norm:
            d.confidence = min(d.confidence, 0.35)
    return ext


def extract_meeting(transcript: str, title: str = "Meeting",
                    meeting_date: str | None = None,
                    attendees: list[str] | None = None,
                    provider: str | None = None) -> tuple[MeetingExtraction, str]:
    """Extract with the chosen provider; ANY failure falls back to the offline
    rules engine so an upload can never 500 (bad key, quota, no internet…)."""
    from app.llm.providers import RuleBasedProvider
    prov = get_provider(provider)
    try:
        ext = prov.extract(transcript, title, meeting_date, attendees)
        name = prov.name
    except Exception as e:
        print(f"[extract] {prov.name} failed ({e}); falling back to offline rules.")
        prov = RuleBasedProvider()
        ext = prov.extract(transcript, title, meeting_date, attendees)
        name = "rules-fallback"
    ext = ground_and_score(ext, transcript)
    return ext, name
