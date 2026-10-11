"""LLM providers with a common structured-output interface.

- GeminiProvider: real LLM extraction via your Gemini API key (used when GEMINI_API_KEY is set).
- RuleBasedProvider: deterministic offline fallback. Still returns validated
  MeetingExtraction objects with exact evidence quotes — so the pipeline,
  dashboard, analytics and evaluation all run with zero API cost / zero errors.
"""
from __future__ import annotations
import re
from datetime import datetime, timedelta

from app import config
from app.schemas import ActionItem, Blocker, Decision, MeetingExtraction
from app.llm import prompts

# ---------- shared helpers ----------

EXPLICIT_PATTERNS = [
    r"(?P<ev>[A-Z][a-z]+ will (?P<act>[^.!\n]{5,120}?)(?: by | before | on )(?P<dl>[^.!\n]{1,40}))",
    r"(?P<ev>I(?:'ll| will) (?P<act>[^.!\n]{5,120}))",
    r"(?P<ev>[A-Z][a-z]+ (?:agreed|committed|promised) to (?P<act>[^.!\n]{5,120}))",
    r"(?P<ev>Action(?: item)?\s*:\s*(?P<act>[^.!\n]{5,160}))",
    r"(?P<ev>[A-Z][a-z]+ to (?P<act>finish|complete|deliver|ship|send|prepare|fix|deploy|review|update)[^.!\n]{3,120})",
]
IMPLICIT_PATTERNS = [
    r"(?P<ev>I(?:'ll| can| might) (?:take a look|have a look|check|look into|follow up|sync up|get back)[^.!\n]{0,80})",
    r"(?P<ev>(?:someone|we) should (?P<act>[^.!\n]{5,120}))",
    r"(?P<ev>(?:maybe|perhaps) (?P<act>[^.!\n]{5,120}))",
    r"(?P<ev>let(?:'s| us) (?P<act>[^.!\n]{5,120}))",
    r"(?P<ev>I(?:'ll| will) (?:get to it|get back|share something|sync up)[^.!\n]{0,80})",
]
VAGUE_RE = re.compile(r"\b(someone|maybe|perhaps|probably|soon|when i can|not sure)\b", re.IGNORECASE)
# Idioms / pleasantries that are never real action items.
JUNK_RE = re.compile(
    r"\b(sleep on it|move on|thank(s| you)?|you'?re welcome|welcome|good (morning|afternoon|evening)"
    r"|get started|wrap( |-)?up|bear with me|one moment|hold on)\b", re.IGNORECASE)


def _akey(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def _is_dup(action: str, existing: list[ActionItem]) -> bool:
    ka = _akey(action)
    if len(ka) < 12:
        return False
    return any(ka in _akey(e.action) or _akey(e.action) in ka for e in existing)
OWNER_RE = re.compile(r"\b([A-Z][a-z]+)\s*(?::|said|says|will|'ll|to take|agreed)")
SPEAKER_RE = re.compile(r"^([A-Z][a-z]+)\s*:", re.MULTILINE)
DECISION_RE = re.compile(
    r"(?:decided|decision|agreed|we(?:'ll| will go with)|approved|final call)\s*[:\-]?\s*(?P<d>[^.!\n]{5,160})",
    re.IGNORECASE,
)
BLOCKER_RE = re.compile(
    r"(?:blocked|blocker|stuck|waiting on|can't proceed|risk)\s*[:\-]?\s*(?P<b>[^.!\n]{5,160})",
    re.IGNORECASE,
)
DATE_WORDS = {
    "friday": 4, "monday": 0, "tuesday": 1, "wednesday": 2,
    "thursday": 3, "saturday": 5, "sunday": 6,
}


def _resolve_deadline(text: str, base: datetime | None) -> str | None:
    t = text.lower()
    base = base or datetime.now()
    m = re.search(r"20\d{2}-\d{2}-\d{2}", t)
    if m:
        return m.group(0)
    if "tomorrow" in t:
        return (base + timedelta(days=1)).date().isoformat()
    if "next week" in t:
        return (base + timedelta(days=7)).date().isoformat()
    if "eod" in t or "end of day" in t:
        return base.date().isoformat()
    for word, wd in DATE_WORDS.items():
        if word in t:
            delta = (wd - base.weekday()) % 7 or 7
            return (base + timedelta(days=delta)).date().isoformat()
    m = re.search(r"by\s+([a-z]+\s+\d{1,2})", t)
    if m:
        try:
            return datetime.strptime(m.group(1) + f" {base.year}", "%B %d %Y").date().isoformat()
        except ValueError:
            return None
    return None


def _owner_near(transcript: str, pos: int, fallback: str | None = None) -> str | None:
    window = transcript[max(0, pos - 120):pos]
    # last "Name:" speaker tag in window wins
    speakers = SPEAKER_RE.findall(window)
    if speakers:
        return speakers[-1]
    m = OWNER_RE.search(window[-80:])
    if m:
        return m.group(1)
    return fallback


class RuleBasedProvider:
    """Deterministic, evidence-grounded extractor. Name kept as 'provider' so the
    rest of the system treats LLM and rules identically (structured outputs only)."""

    name = "rules"

    def extract(self, transcript: str, title: str = "Meeting",
                meeting_date: str | None = None,
                attendees: list[str] | None = None) -> MeetingExtraction:
        attendees = attendees or sorted(set(SPEAKER_RE.findall(transcript))) or ["Team"]
        try:
            base = datetime.fromisoformat(meeting_date) if meeting_date else datetime.now()
        except ValueError:
            base = datetime.now()

        actions: list[ActionItem] = []
        seen: set[str] = set()

        def _add(ev: str, act: str, owner: str | None, deadline: str | None,
                 conf: float, ctype: str) -> None:
            act = (act or ev).strip().capitalize()
            if len(act.split()) <= 1:
                act = ev.strip().capitalize()  # lone-verb capture ("Send") is useless; keep full quote
            if len(ev.strip()) < 8 or ev.lower() in seen:
                return
            if JUNK_RE.search(act):  # idiom / pleasantry, not a task
                return
            if _is_dup(act, actions):  # same commitment, different pattern
                return
            seen.add(ev.lower())
            actions.append(ActionItem(
                action=act, owner=owner, deadline=deadline,
                confidence=conf, evidence=ev.strip(), commitment_type=ctype))  # type: ignore[arg-type]

        # Implicit first: hedged phrasing ("I'll sync up...", "let's...") must win
        # over the greedy explicit "I will..." pattern on the same sentence.
        for pat in IMPLICIT_PATTERNS:
            for m in re.finditer(pat, transcript, re.IGNORECASE):
                ev = m.group("ev").strip()
                act = m.groupdict().get("act", ev) or ev
                owner = _owner_near(transcript, m.start())
                conf = 0.52 if owner is None else 0.57
                if VAGUE_RE.search(ev):
                    conf = min(conf, 0.52)
                _add(ev, act, owner, None, conf, "implicit")
        for pat in EXPLICIT_PATTERNS:
            for m in re.finditer(pat, transcript):  # case-sensitive: names must be capitalized
                ev = m.group("ev").strip()
                act = m.groupdict().get("act", ev) or ev
                owner = _owner_near(transcript, m.start())
                dl = _resolve_deadline(ev, base)
                conf = 0.85 if (owner and dl) else (0.78 if owner else 0.68)
                _add(ev, act, owner, dl, conf, "explicit")

        decisions = [
            Decision(decision=d.group("d").strip().capitalize(), rationale=None,
                     evidence=d.group(0).strip(), confidence=0.8)
            for d in DECISION_RE.finditer(transcript)
        ][:10]
        blockers = [
            Blocker(blocker=b.group("b").strip().capitalize(), impacted_owner=None,
                    evidence=b.group(0).strip(), confidence=0.7)
            for b in BLOCKER_RE.finditer(transcript)
        ][:10]
        follow_ups = [a.action for a in actions if a.commitment_type == "implicit"][:5]
        summary = " ".join(transcript.split()[:60]) + ("..." if len(transcript.split()) > 60 else "")
        return MeetingExtraction(
            title=title, date=meeting_date, attendees=attendees, summary=summary,
            decisions=decisions, action_items=actions, blockers=blockers, follow_ups=follow_ups)


class GeminiProvider:
    """Real LLM extraction via Gemini structured JSON. Evidence is verified downstream."""

    name = "gemini"

    def extract(self, transcript: str, title: str = "Meeting",
                meeting_date: str | None = None,
                attendees: list[str] | None = None) -> MeetingExtraction:
        from app.llm import backends as _be
        user = prompts.USER_TEMPLATE.format(
            title=title, meeting_date=meeting_date,
            attendees=", ".join(attendees or []), transcript=transcript[:12000])
        _name, data = _be.generate_json(prompts.SYSTEM_PROMPT, user, only="gemini")
        if not data:
            raise RuntimeError("Gemini extraction failed")
        data.setdefault("title", title)
        return MeetingExtraction.model_validate(data)


def get_provider(name: str | None = None):
    want = (name or config.LLM_PROVIDER).lower()
    if want == "rules":
        return RuleBasedProvider()
    if want == "gemini" or (want == "auto" and config.GEMINI_API_KEY):
        try:
            return GeminiProvider()
        except Exception:
            return RuleBasedProvider()
    return RuleBasedProvider()
