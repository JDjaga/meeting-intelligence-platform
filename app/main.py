"""FastAPI app: multi-page meeting intelligence (overview / meetings / actions / decisions / analytics / review / upload)."""
from __future__ import annotations
import sqlite3
from datetime import date
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import config
from app import database as db
from app.analytics import metrics as M
from app.llm.extractor import extract_meeting
from app.stt.transcriber import ingest

app = FastAPI(title="ProjectActionGraph — Meeting Intelligence")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def conn() -> sqlite3.Connection:
    return db.connect()


def _meeting_record(c: sqlite3.Connection, mid: int) -> dict | None:
    import json as _json
    m = c.execute("SELECT * FROM meetings WHERE id=?", (mid,)).fetchone()
    if not m:
        return None
    try:
        attendees = _json.loads(m["attendees"] or "[]")
    except ValueError:
        attendees = []
    return {
        "id": m["id"], "title": m["title"], "transcript": m["transcript"],
        "attendees": attendees, "summary": m["summary"] or "",
        "actions": [dict(r) for r in c.execute("SELECT * FROM actions WHERE meeting_id=?", (mid,)).fetchall()],
        "decisions": [dict(r) for r in c.execute("SELECT * FROM decisions WHERE meeting_id=?", (mid,)).fetchall()],
        "blockers": [dict(r) for r in c.execute("SELECT * FROM blockers WHERE meeting_id=?", (mid,)).fetchall()],
    }


def base_ctx(request: Request, active: str, extra: dict | None = None) -> dict:
    c = conn()
    try:
        review_count = c.execute(
            "SELECT COUNT(*) n FROM actions WHERE needs_review=1 AND status IN ('open','carried')"
        ).fetchone()["n"]
    finally:
        c.close()
    ctx = {"request": request, "active": active, "review_count": review_count,
           "today": date.today().isoformat()}
    if extra:
        ctx.update(extra)
    return ctx


# ---------- pages ----------
@app.get("/", response_class=HTMLResponse)
def overview(request: Request):
    c = conn()
    try:
        ov = M.overview(c)
        recent = [dict(r) for r in c.execute("SELECT * FROM meetings ORDER BY id DESC LIMIT 5").fetchall()]
        status, commit = M.status_breakdown(c), M.commitment_split(c)
    finally:
        c.close()
    return templates.TemplateResponse("overview.html", base_ctx(request, "overview", {
        "ov": ov, "recent": recent, "status": status, "commit": commit}))


@app.get("/meetings", response_class=HTMLResponse)
def meetings_page(request: Request):
    c = conn()
    try:
        meetings = [dict(r) for r in c.execute("SELECT * FROM meetings ORDER BY id DESC").fetchall()]
    finally:
        c.close()
    return templates.TemplateResponse("meetings.html", base_ctx(request, "meetings", {"meetings": meetings}))


@app.get("/meetings/{mid}", response_class=HTMLResponse)
def meeting_detail(mid: int, request: Request):
    c = conn()
    try:
        m = c.execute("SELECT * FROM meetings WHERE id=?", (mid,)).fetchone()
        if not m:
            raise HTTPException(404, "meeting not found")
        actions = [dict(r) for r in c.execute("SELECT * FROM actions WHERE meeting_id=?", (mid,)).fetchall()]
        decisions = [dict(r) for r in c.execute("SELECT * FROM decisions WHERE meeting_id=?", (mid,)).fetchall()]
        blockers = [dict(r) for r in c.execute("SELECT * FROM blockers WHERE meeting_id=?", (mid,)).fetchall()]
    finally:
        c.close()
    return templates.TemplateResponse("meeting.html", base_ctx(request, "meetings", {
        "m": dict(m), "actions": actions, "decisions": decisions, "blockers": blockers}))


@app.get("/actions", response_class=HTMLResponse)
def actions_page(request: Request, status: str = Query(""), ctype: str = Query(""),
                 owner: str = Query(""), q: str = Query(""), meeting: str = Query("")):
    c = conn()
    try:
        meetings = [dict(r) for r in c.execute("SELECT id, title FROM meetings ORDER BY id DESC").fetchall()]
        rows = [dict(r) for r in c.execute(
            "SELECT a.*, m.title meeting_title FROM actions a JOIN meetings m ON m.id=a.meeting_id"
            " ORDER BY m.id DESC, a.id ASC LIMIT 500").fetchall()]
        owners = sorted({r["owner"] for r in rows if r["owner"]})
        if meeting.strip().isdigit():
            rows = [r for r in rows if r["meeting_id"] == int(meeting.strip())]
        if status:
            rows = [r for r in rows if r["status"] == status]
        if ctype:
            rows = [r for r in rows if r["commitment_type"] == ctype]
        if owner:
            rows = [r for r in rows if r["owner"] == owner]
        if q:
            rows = [r for r in rows if q.lower() in (r["action"] or "").lower()]
    finally:
        c.close()
    return templates.TemplateResponse("actions.html", base_ctx(request, "actions", {
        "groups": M.group_by_meeting(rows), "owners": owners, "meetings": meetings,
        "f": {"status": status, "ctype": ctype, "owner": owner, "q": q, "meeting": meeting}}))


@app.get("/decisions", response_class=HTMLResponse)
def decisions_page(request: Request, meeting: str = Query("")):
    c = conn()
    try:
        meetings = [dict(r) for r in c.execute("SELECT id, title FROM meetings ORDER BY id DESC").fetchall()]
        decisions = [dict(r) for r in c.execute(
            "SELECT d.*, m.title meeting_title FROM decisions d JOIN meetings m ON m.id=d.meeting_id"
            " ORDER BY m.id DESC, d.id ASC LIMIT 200").fetchall()]
        if meeting.strip().isdigit():
            decisions = [d for d in decisions if d["meeting_id"] == int(meeting.strip())]
    finally:
        c.close()
    return templates.TemplateResponse("decisions.html", base_ctx(request, "decisions", {
        "groups": M.group_by_meeting(decisions), "meetings": meetings, "f_meeting": meeting}))


@app.get("/analytics", response_class=HTMLResponse)
def analytics_page(request: Request):
    c = conn()
    try:
        ov = M.overview(c)
        ctx = {"ov": ov, "owners": M.owner_workload(c), "status": M.status_breakdown(c),
               "commit": M.commitment_split(c), "conf": M.confidence_histogram(c),
               "overdue": M.overdue_by_owner(c), "per_meet": M.actions_per_meeting(c)}
        n = ov["actions"]
        ctx["review_rate"] = round(100 * ov["review_queue"] / n, 1) if n else 0.0
        avg = c.execute("SELECT AVG(confidence) v FROM actions").fetchone()["v"]
        ctx["avg_conf"] = round(avg or 0, 2)
    finally:
        c.close()
    return templates.TemplateResponse("analytics.html", base_ctx(request, "analytics", ctx))


@app.get("/review", response_class=HTMLResponse)
def review_page(request: Request, meeting: str = Query("")):
    c = conn()
    try:
        meetings = [dict(r) for r in c.execute("SELECT id, title FROM meetings ORDER BY id DESC").fetchall()]
        review = M.review_queue(c)
        if meeting.strip().isdigit():
            review = [r for r in review if r["meeting_id"] == int(meeting.strip())]
    finally:
        c.close()
    return templates.TemplateResponse("review.html", base_ctx(request, "review", {
        "groups": M.group_by_meeting(review), "total": len(review),
        "meetings": meetings, "f_meeting": meeting}))


@app.get("/upload", response_class=HTMLResponse)
def upload_form(request: Request):
    return templates.TemplateResponse("upload.html", base_ctx(request, "upload"))


DEMO_SAMPLES = {
    "sales": ("Demo — Sales Weekly Sync", "2026-10-10", "samples/01_sales_weekly_sync.txt"),
    "brainstorm": ("Demo — Brainstorm (implicit-heavy)", "2026-10-11", "samples/04_brainstorm_implicit_heavy.txt"),
}


@app.post("/demo/{key}")
def load_demo(key: str):
    """One-click demo: ingest a bundled sample so new users see the whole
    pipeline (upload → extract → review → track) with zero setup."""
    if key not in DEMO_SAMPLES:
        raise HTTPException(404, "unknown demo")
    title, mdate, rel = DEMO_SAMPLES[key]
    text = (Path(__file__).resolve().parent.parent / rel).read_text(encoding="utf-8")
    ext, _ = extract_meeting(text, title=title, meeting_date=mdate)
    c = conn()
    try:
        mid = db.insert_meeting(c, title, mdate, text, ext.summary, ext.attendees)
        db.insert_extraction(c, mid, ext)
    finally:
        c.close()
    return RedirectResponse(f"/meetings/{mid}", status_code=303)


# ---------- API ----------
@app.get("/api/stats")
def api_stats():
    c = conn()
    try:
        return {"overview": M.overview(c), "owners": M.owner_workload(c),
                "status": M.status_breakdown(c), "commitment": M.commitment_split(c),
                "confidence": M.confidence_histogram(c),
                "overdue_by_owner": M.overdue_by_owner(c),
                "per_meeting": M.actions_per_meeting(c)}
    finally:
        c.close()


@app.get("/api/review")
def api_review():
    c = conn()
    try:
        return {"queue": M.review_queue(c)}
    finally:
        c.close()


@app.post("/upload")
async def upload(title: str = Form("Untitled meeting"),
                 meeting_date: str = Form(""),
                 carry_from: str = Form(""),
                 file: UploadFile = File(...)):
    dest = config.UPLOAD_DIR / f"{date.today().isoformat()}_{file.filename}"
    raw = await file.read()
    dest.write_bytes(raw)
    try:
        transcript = ingest(dest)
    except Exception as e:
        raise HTTPException(400, str(e))
    if len(transcript.split()) < 5:
        raise HTTPException(400, "Transcript too short — upload a real meeting transcript or audio.")
    ext, provider = extract_meeting(transcript, title=title,
                                    meeting_date=meeting_date or None)
    c = conn()
    try:
        mid = db.insert_meeting(c, title, meeting_date or None, transcript,
                                ext.summary, ext.attendees)
        db.insert_extraction(c, mid, ext)
        carried = 0
        if carry_from.strip().isdigit():
            carried = db.carry_forward(c, int(carry_from.strip()), mid)
    finally:
        c.close()
    return RedirectResponse(f"/meetings/{mid}?provider={provider}&carried={carried}", status_code=303)


@app.post("/api/actions/{aid}/status")
def set_status(aid: int, payload: dict):
    status = payload.get("status")
    if status not in ("open", "done", "carried", "dropped"):
        raise HTTPException(400, "bad status")
    c = conn()
    try:
        c.execute("UPDATE actions SET status=? WHERE id=?", (status, aid))
        c.commit()
    finally:
        c.close()
    return {"ok": True}


@app.post("/api/actions/{aid}/approve")
def approve(aid: int, payload: dict):
    """Human review: correct owner/action/deadline, clear the review flag."""
    c = conn()
    try:
        row = c.execute("SELECT * FROM actions WHERE id=?", (aid,)).fetchone()
        if not row:
            raise HTTPException(404, "action not found")
        action = payload.get("action", row["action"])
        owner = payload.get("owner", row["owner"])
        deadline = payload.get("deadline", row["deadline"])
        c.execute("UPDATE actions SET action=?, owner=?, deadline=?, needs_review=0,"
                  " review_reason=NULL, confidence=MAX(confidence, 0.85) WHERE id=?",
                  (action, owner, deadline, aid))
        c.commit()
    finally:
        c.close()
    return {"ok": True}


@app.get("/api/export/actions")
def export_actions():
    c = conn()
    try:
        rows = [dict(r) for r in c.execute(
            "SELECT a.*, m.title meeting_title FROM actions a JOIN meetings m ON m.id=a.meeting_id").fetchall()]
    finally:
        c.close()
    return JSONResponse(rows)


@app.post("/api/meetings/{mid}/chat")
def chat_meeting(mid: int, payload: dict):
    """Ask a question about one imported meeting file. Answers are grounded:
    every citation is a verbatim transcript quote."""
    q = (payload.get("question") or "").strip()
    if len(q) < 2:
        raise HTTPException(400, "Ask a longer question.")
    from app.chat import qa as _qa
    rec = _meeting_record(conn(), mid)
    if not rec:
        raise HTTPException(404, "meeting not found")
    return _qa.ask_workspace(q, [rec])


@app.post("/api/chat")
def chat_workspace(payload: dict):
    """Workspace assistant: any question across all imported meetings —
    deadlines, owners, decisions, blockers, summaries, or general help."""
    q = (payload.get("question") or "").strip()
    if len(q) < 2:
        raise HTTPException(400, "Ask a longer question.")
    from app.chat import qa as _qa
    c = conn()
    try:
        recs = [_meeting_record(c, r["id"]) for r in
                c.execute("SELECT id FROM meetings ORDER BY id").fetchall()]
    finally:
        c.close()
    return _qa.ask_workspace(q, [r for r in recs if r])


@app.post("/api/reset")
def reset_workspace():
    """Clear all meetings, actions, decisions and blockers (fresh start)."""
    c = conn()
    try:
        c.execute("DELETE FROM blockers")
        c.execute("DELETE FROM actions")
        c.execute("DELETE FROM decisions")
        c.execute("DELETE FROM meetings")
        c.commit()
    finally:
        c.close()
    return {"ok": True}
