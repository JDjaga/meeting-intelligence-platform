"""Data-analytics engine (dashboard KPIs + chart payloads + CSV export).

This is what makes the project dual-natured: LLM engineering (extraction)
PLUS analytics engineering (KPIs, trends, workload, aging, review analytics).
Powered by plain SQL + stdlib so the dashboard never breaks; pandas is used
only in scripts/analytics_report.py for offline deep-dives.
"""
from __future__ import annotations
import sqlite3
from collections import Counter
from datetime import date


def _rows(conn, q, args=()):
    return [dict(r) for r in conn.execute(q, args).fetchall()]


def overview(conn: sqlite3.Connection, today: str | None = None) -> dict:
    today = today or date.today().isoformat()
    m = conn.execute("SELECT COUNT(*) c FROM meetings").fetchone()["c"]
    a = conn.execute("SELECT COUNT(*) c FROM actions").fetchone()["c"]
    open_n = conn.execute("SELECT COUNT(*) c FROM actions WHERE status IN ('open','carried')").fetchone()["c"]
    done_n = conn.execute("SELECT COUNT(*) c FROM actions WHERE status='done'").fetchone()["c"]
    overdue = conn.execute(
        "SELECT COUNT(*) c FROM actions WHERE status IN ('open','carried')"
        " AND deadline IS NOT NULL AND deadline != '' AND deadline < ?", (today,)).fetchone()["c"]
    review = conn.execute("SELECT COUNT(*) c FROM actions WHERE needs_review=1 AND status IN ('open','carried')").fetchone()["c"]
    decisions = conn.execute("SELECT COUNT(*) c FROM decisions").fetchone()["c"]
    explicit = conn.execute("SELECT COUNT(*) c FROM actions WHERE commitment_type='explicit'").fetchone()["c"]
    implicit = a - explicit
    completion = round(100 * done_n / a, 1) if a else 0.0
    return {"meetings": m, "actions": a, "open": open_n, "done": done_n,
            "overdue": overdue, "review_queue": review, "decisions": decisions,
            "explicit": explicit, "implicit": implicit, "completion_rate": completion}


def owner_workload(conn: sqlite3.Connection) -> list[dict]:
    return _rows(conn, """SELECT COALESCE(owner,'Unassigned') owner,
        COUNT(*) total,
        SUM(CASE WHEN status IN ('open','carried') THEN 1 ELSE 0 END) open_n,
        SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) done_n,
        AVG(confidence) avg_conf
        FROM actions GROUP BY owner ORDER BY open_n DESC""")


def status_breakdown(conn: sqlite3.Connection) -> list[dict]:
    return _rows(conn, "SELECT status, COUNT(*) n FROM actions GROUP BY status")


def commitment_split(conn: sqlite3.Connection) -> list[dict]:
    return _rows(conn, "SELECT commitment_type, COUNT(*) n FROM actions GROUP BY commitment_type")


def confidence_histogram(conn: sqlite3.Connection, bins: int = 5) -> list[dict]:
    rows = conn.execute("SELECT confidence FROM actions").fetchall()
    hist = Counter()
    for r in rows:
        b = min(int((r["confidence"] or 0) * bins), bins - 1)
        lo, hi = b / bins, (b + 1) / bins
        hist[f"{lo:.1f}-{hi:.1f}"] += 1
    return [{"bin": k, "n": hist[k]} for k in sorted(hist)]


def overdue_by_owner(conn: sqlite3.Connection, today: str | None = None) -> list[dict]:
    today = today or date.today().isoformat()
    return _rows(conn, """SELECT COALESCE(owner,'Unassigned') owner, COUNT(*) n
        FROM actions WHERE status IN ('open','carried')
        AND deadline IS NOT NULL AND deadline != '' AND deadline < ?
        GROUP BY owner ORDER BY n DESC""", (today,))


def actions_per_meeting(conn: sqlite3.Connection) -> list[dict]:
    return _rows(conn, """SELECT m.id meeting_id, m.title, COUNT(a.id) n_actions,
        SUM(CASE WHEN a.status='done' THEN 1 ELSE 0 END) n_done
        FROM meetings m LEFT JOIN actions a ON a.meeting_id=m.id
        GROUP BY m.id ORDER BY m.id""")


def review_queue(conn: sqlite3.Connection) -> list[dict]:
    return _rows(conn, """SELECT a.*, m.title meeting_title FROM actions a
        JOIN meetings m ON m.id=a.meeting_id
        WHERE a.needs_review=1 AND a.status IN ('open','carried')
        ORDER BY m.id DESC, a.confidence ASC, a.id ASC""")


def group_by_meeting(rows: list[dict]) -> list[dict]:
    """Group rows under their meeting (newest meeting first, transcript order
    inside) so lists read meeting-by-meeting instead of interleaved."""
    groups: list[dict] = []
    idx: dict = {}
    for r in rows:
        key = r.get("meeting_id")
        if key not in idx:
            idx[key] = {"meeting_id": key,
                        "meeting_title": r.get("meeting_title", f"Meeting #{key}"),
                        "items": []}
            groups.append(idx[key])
        idx[key]["items"].append(r)
    return groups
