"""Workspace assistant: ask anything about your imported meetings — or just talk.

How it answers (offline-first, no API key needed):
1. Small talk ("hi", "thanks", "bye") and help ("what can you do") are answered directly.
2. Meeting questions are resolved against STRUCTURED data first (action items,
   decisions, blockers, owners, deadlines) — precise, never guessed.
3. Anything else falls back to transcript search across all meetings, with every
   claim citing a verbatim quote plus the meeting it came from.
4. With GEMINI_API_KEY (or HF_TOKEN) set, an LLM rephrases using the same retrieved material,
   and any quote that is not verbatim is dropped (hallucination guard).

Contract: ask_workspace(question, meetings) -> {answer, evidence, method}
  meetings: list of {id, title, transcript, attendees[list], summary,
                     actions[{action,owner,deadline,confidence,commitment_type,status,evidence,needs_review}],
                     decisions[{decision,evidence}], blockers[{blocker,evidence}]}
  evidence: list of {meeting, quote}
"""
from __future__ import annotations
import re
from datetime import date

_STOP = set(
    "the,a,an,and,or,of,to,in,on,for,with,by,that,this,these,those,it,its,is,are,was,were,"
    "be,been,will,shall,should,can,could,would,do,does,did,what,when,where,who,whom,which,"
    "how,why,there,their,they,them,then,than,from,about,into,over,after,before,not,no,yes,"
    "all,any,our,we,you,your,he,she,his,her,as,at,but,if,me,my,us,so,up,out,have,has,had,"
    "having,likely,maybe,just,very,also,please,sure,yeah,okay,tell,give,show,list,find,"
    "know,want,need,like,kind".split(","))


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def _words(s: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", s.lower())
            if w not in _STOP and len(w) > 2]


def _match(a: str, b: str) -> bool:
    if a == b:
        return True
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= 4 and long.startswith(short)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [p.strip() for p in parts if len(p.strip()) > 25]


def _open(actions: list[dict]) -> list[dict]:
    return [a for a in actions if a.get("status") in ("open", "carried")]


def _ev(meeting: str, quote: str) -> dict:
    return {"meeting": meeting, "quote": quote}


# ---------- small talk ----------
def _small_talk(ql: str) -> dict | None:
    q = ql.strip()
    if re.fullmatch(r"(hi|hii+|hello|hey|yo|good (morning|afternoon|evening)|namaste)\W*", q):
        return {"answer": "Hello. I am your meeting assistant — ask me about deadlines, owners, "
                          "decisions, blockers, or anything inside your imported meetings.",
                "evidence": [], "method": "assistant"}
    if re.fullmatch(r"(thanks|thank you|thankyou|thx|great|awesome|nice|cool|ok|okay)\W*", q):
        return {"answer": "You are welcome. Anything else you want to know about your meetings?",
                "evidence": [], "method": "assistant"}
    if re.fullmatch(r"(bye|goodbye|see you|good night)\W*", q):
        return {"answer": "Goodbye. Your action items and reviews are saved whenever you return.",
                "evidence": [], "method": "assistant"}
    if re.search(r"what can you do|help|how (do|does) (this|it|you) work|features|abilities", q):
        return {"answer": ("I can: list action items and owners; show deadlines and overdue work; "
                           "recall decisions and blockers; show what is waiting in review; "
                           "summarise any meeting; and search every transcript with cited quotes. "
                           "Try: 'What is overdue?', 'What did we decide?', 'What is pending for Ritu?'"),
                "evidence": [], "method": "assistant"}
    return None


# ---------- structured intents ----------
def _intent_overdue(meetings: list[dict], today: str) -> dict | None:
    rows = [(m, a) for m in meetings for a in _open(m["actions"])
            if (a.get("deadline") or "") < today and a.get("deadline")]
    if not rows:
        return None
    lines = [f"- {a['action']} — {a.get('owner') or 'unassigned'} (due {a['deadline']}, {m['title']})"
             for m, a in sorted(rows, key=lambda x: x[1]["deadline"])]
    return {"answer": f"Overdue as of {today}:\n" + "\n".join(lines),
            "evidence": [_ev(m["title"], a["evidence"]) for m, a in rows],
            "method": "structured"}


def _intent_deadlines(meetings: list[dict]) -> dict | None:
    rows = [(m, a) for m in meetings for a in _open(m["actions"]) if a.get("deadline")]
    if not rows:
        return None
    rows.sort(key=lambda x: x[1]["deadline"] or "")
    lines = [f"- {a['action']} — {a.get('owner') or 'unassigned'}, due {a['deadline']} ({m['title']})"
             for m, a in rows]
    return {"answer": "Upcoming deadlines:\n" + "\n".join(lines),
            "evidence": [_ev(m["title"], a["evidence"]) for m, a in rows],
            "method": "structured"}


def _intent_owner(meetings: list[dict], ql: str) -> dict | None:
    owners = sorted({a.get("owner") for m in meetings for a in m["actions"] if a.get("owner")})
    hit = next((o for o in owners if o and o.lower() in ql
                and re.search(r"\b" + re.escape(o.lower()) + r"(s|'s)?\b", ql)), None)
    if not hit:
        return None
    rows = [(m, a) for m in meetings for a in m["actions"] if a.get("owner") == hit]
    mine = [(m, a) for m, a in rows if a.get("status") in ("open", "carried")]
    done = len(rows) - len(mine)
    if not rows:
        return None
    lines = [f"- {a['action']} [{a.get('status')}]" + (f" (due {a['deadline']})" if a.get("deadline") else "")
             for _, a in mine] or ["- nothing open"]
    return {"answer": f"{hit}: {len(mine)} open, {done} done.\nOpen items:\n" + "\n".join(lines),
            "evidence": [_ev(m["title"], a["evidence"]) for m, a in mine],
            "method": "structured"}


def _intent_decisions(meetings: list[dict]) -> dict:
    rows = [(m, d) for m in meetings for d in m["decisions"]]
    if not rows:
        return {"answer": "No decisions have been recorded in your meetings yet.",
                "evidence": [], "method": "structured"}
    lines = [f"- {d['decision']} ({m['title']})" for m, d in rows]
    return {"answer": "Decisions taken:\n" + "\n".join(lines),
            "evidence": [_ev(m["title"], d["evidence"]) for m, d in rows],
            "method": "structured"}


def _intent_blockers(meetings: list[dict]) -> dict:
    rows = [(m, b) for m in meetings for b in m["blockers"]]
    if not rows:
        return {"answer": "No blockers recorded. Ask about 'waiting on' topics and I will search the transcripts.",
                "evidence": [], "method": "structured"}
    lines = [f"- {b['blocker']} ({m['title']})" for m, b in rows]
    return {"answer": "Current blockers:\n" + "\n".join(lines),
            "evidence": [_ev(m["title"], b["evidence"]) for m, b in rows],
            "method": "structured"}


def _intent_review(meetings: list[dict]) -> dict:
    rows = [(m, a) for m in meetings for a in m["actions"]
            if a.get("needs_review") and a.get("status") in ("open", "carried")]
    if not rows:
        return {"answer": "Review queue is empty — every item is high-confidence and grounded.",
                "evidence": [], "method": "structured"}
    lines = [f"- {a['action']} — {a.get('owner') or 'unassigned'} (confidence {a.get('confidence')}, {m['title']})"
             for m, a in rows]
    return {"answer": f"{len(rows)} item(s) waiting for human review:\n" + "\n".join(lines),
            "evidence": [_ev(m["title"], a["evidence"]) for m, a in rows],
            "method": "structured"}


def _intent_summary(meetings: list[dict]) -> dict:
    if len(meetings) == 1:
        m = meetings[0]
        n_open = len(_open(m["actions"]))
        return {"answer": (f"{m['title']}: {len(m['actions'])} action items ({n_open} open), "
                           f"{len(m['decisions'])} decisions, {len(m['blockers'])} blockers.\n"
                           f"Summary: {m.get('summary') or '—'}"),
                "evidence": [], "method": "structured"}
    lines = [f"- {m['title']}: {len(m['actions'])} actions, {len(m['decisions'])} decisions" for m in meetings]
    total = sum(len(m["actions"]) for m in meetings)
    return {"answer": (f"Workspace: {len(meetings)} meetings, {total} action items.\n" + "\n".join(lines)
                       + "\nAsk 'summarise <meeting name>' or anything specific."),
            "evidence": [], "method": "structured"}


def _scoped(meetings: list[dict], ql: str) -> list[dict]:
    """Narrow to a meeting if its title words appear in the question."""
    scored = []
    for m in meetings:
        tw = [w for w in re.findall(r"[a-z0-9]+", m["title"].lower()) if len(w) > 3
              and w not in ("meeting", "demo", "sync")]
        hits = sum(1 for w in tw if w in ql)
        if hits:
            scored.append((hits, m))
    if not scored:
        return meetings
    scored.sort(key=lambda x: -x[0])
    return [m for _, m in scored[:1]]


# ---------- transcript search fallback ----------
def _search(meetings: list[dict], question: str, k: int = 5) -> list[dict]:
    qw = set(_words(question))
    scored: list[tuple[float, dict, str]] = []
    for m in _scoped(meetings, question.lower()):
        for s in _sentences(m["transcript"]):
            sw = set(_words(s))
            if not sw:
                continue
            inter = sum(1 for q in qw if any(_match(q, w) for w in sw)) if qw else 0
            if inter or not qw:
                scored.append((inter / max(1, len(qw)) + 0.1 * inter / len(sw), m, s))
    scored.sort(key=lambda x: -x[0])
    out, seen = [], set()
    for _, m, s in scored:
        if s.lower() not in seen:
            seen.add(s.lower())
            out.append(_ev(m["title"], s))
        if len(out) == k:
            break
    return out


def _answer_from_structured(question: str, meetings: list[dict]) -> dict | None:
    ql = question.lower()
    if re.search(r"overdue|past due|\blate\b", ql):
        return _intent_overdue(meetings, date.today().isoformat()) or {
            "answer": "Nothing is overdue. All dated items are on track.",
            "evidence": [], "method": "structured"}
    if re.search(r"deadline|due |due\?|timeline|\bwhen\b", ql):
        got = _intent_deadlines(meetings)
        if got:
            return got
    owner_hit = _intent_owner(meetings, ql)
    if owner_hit and re.search(r"commit|promis|task|action|todo|doing|pending|assign|responsib|work|job|pending|his|her|their", ql):
        return owner_hit
    if re.search(r"decid|decis|agre|conclu", ql):
        return _intent_decisions(meetings)
    if re.search(r"block|stuck|waiting on|risk|imped", ql):
        return _intent_blockers(meetings)
    if re.search(r"review|unsure|uncertain|low confiden|approve", ql):
        return _intent_review(meetings)
    if re.search(r"commit|promis|task|action items?|todo|doing|pending|assign", ql):
        rows = [(m, a) for m in _scoped(meetings, ql) for a in _open(m["actions"])][:8]
        if rows:
            lines = [f"- {a['action']} — {a.get('owner') or 'unassigned'} ({m['title']})" for m, a in rows]
            return {"answer": "Open commitments:\n" + "\n".join(lines),
                    "evidence": [_ev(m["title"], a["evidence"]) for m, a in rows],
                    "method": "structured"}
    if re.search(r"summar|overview|how many|status|recap", ql):
        return _intent_summary(_scoped(meetings, ql))
    if owner_hit:
        return owner_hit
    return None


def ask_workspace(question: str, meetings: list[dict]) -> dict:
    q = (question or "").strip()
    if len(q) < 2:
        return {"answer": "Ask me something — for example 'What is overdue?' or 'What did we decide?'",
                "evidence": [], "method": "assistant"}
    small = _small_talk(q.lower())
    if small:
        return small
    if not meetings:
        return {"answer": ("No meetings imported yet, so I have nothing to search. "
                           "Upload a transcript, document or recording on the New meeting page — "
                           "or load a sample — and then ask me anything about it."),
                "evidence": [], "method": "assistant"}
    structured = _answer_from_structured(q, meetings)
    if structured:
        return _maybe_llm(q, meetings, structured)
    hits = _search(meetings, q)
    if hits:
        lines = "\n".join(f"{i + 1}. [{h['meeting']}] {h['quote']}" for i, h in enumerate(hits))
        base = {"answer": f"Here is what your meetings say:\n{lines}",
                "evidence": hits, "method": "extractive"}
        return _maybe_llm(q, meetings, base)
    return {"answer": ("I searched all your meetings and found nothing on that. I can answer about "
                       "deadlines, owners, decisions, blockers, the review queue, or summaries — "
                       "try one of those, or upload the meeting that covers it."),
            "evidence": [], "method": "assistant"}


# ---------- LLM upgrade (optional) ----------
def _context(meetings: list[dict], question: str) -> tuple[str, str]:
    chunks = []
    for m in _scoped(meetings, question.lower()):
        for s in _sentences(m["transcript"])[:40]:
            chunks.append(f"[{m['title']}] {s}")
    struct = []
    for m in meetings:
        for a in _open(m["actions"])[:15]:
            struct.append(f"[{m['title']}] ACTION: {a['action']} owner={a.get('owner')} "
                          f"deadline={a.get('deadline')} conf={a.get('confidence')}")
        for d in m["decisions"][:10]:
            struct.append(f"[{m['title']}] DECISION: {d['decision']}")
    return "\n".join(struct[:40]), "\n".join(chunks[:40])


def _maybe_llm(question: str, meetings: list[dict], base: dict) -> dict:
    from app.llm import backends as _be
    struct, chunks = _context(meetings, question)
    name, data = _be.generate_json(
        "Answer using ONLY the material below. Return JSON "
        '{"answer": str, "evidence": [{"meeting": str, "quote": exact quote}]}. '
        "If the answer is unknown, say so.",
        f"STRUCTURED:\n{struct}\n\nTRANSCRIPT:\n{chunks}\n\nQ: {question}")
    if not name:
        return base  # no key / all backends failed → offline answer stands
    valid = []
    for m in meetings:
        t = " ".join((m["transcript"] or "").lower().split())
        m["_t"] = t
    for e in data.get("evidence", []):
        q = " ".join(str(e.get("quote", "")).lower().split())
        for m in meetings:
            if q and q in m["_t"]:
                valid.append({"meeting": m["title"], "quote": e["quote"]})
                break
    return {"answer": str(data.get("answer", base["answer"])),
            "evidence": valid[:6] or base["evidence"], "method": name}


# ---------- single-meeting entry (kept for the per-meeting API) ----------
def ask(transcript: str, question: str, title: str = "Meeting",
        attendees: list[str] | None = None, summary: str = "",
        actions: list[dict] | None = None, decisions: list[dict] | None = None,
        blockers: list[dict] | None = None) -> dict:
    return ask_workspace(question, [{
        "id": 0, "title": title, "transcript": transcript,
        "attendees": attendees or [], "summary": summary,
        "actions": actions or [], "decisions": decisions or [],
        "blockers": blockers or []}])
