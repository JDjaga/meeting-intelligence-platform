"""SQLite storage (stdlib only — zero version conflicts)."""
from __future__ import annotations
import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from app import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    meeting_date TEXT,
    transcript TEXT NOT NULL,
    summary TEXT DEFAULT '',
    attendees TEXT DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL REFERENCES meetings(id),
    decision TEXT NOT NULL,
    rationale TEXT,
    evidence TEXT,
    confidence REAL DEFAULT 0.8
);
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL REFERENCES meetings(id),
    action TEXT NOT NULL,
    owner TEXT,
    deadline TEXT,
    confidence REAL NOT NULL,
    evidence TEXT NOT NULL,
    commitment_type TEXT NOT NULL CHECK (commitment_type IN ('explicit','implicit')),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','done','carried','dropped')),
    needs_review INTEGER NOT NULL DEFAULT 0,
    review_reason TEXT,
    carried_from INTEGER,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS blockers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL REFERENCES meetings(id),
    blocker TEXT NOT NULL,
    impacted_owner TEXT,
    evidence TEXT,
    confidence REAL DEFAULT 0.7
);
"""


def connect(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or config.DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def insert_meeting(conn: sqlite3.Connection, title: str, meeting_date: str | None,
                   transcript: str, summary: str, attendees: list[str]) -> int:
    cur = conn.execute(
        "INSERT INTO meetings (title, meeting_date, transcript, summary, attendees, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (title, meeting_date, transcript, summary, json.dumps(attendees),
         datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    return int(cur.lastrowid)


def insert_extraction(conn: sqlite3.Connection, meeting_id: int, ext) -> None:
    for d in ext.decisions:
        conn.execute(
            "INSERT INTO decisions (meeting_id, decision, rationale, evidence, confidence)"
            " VALUES (?,?,?,?,?)",
            (meeting_id, d.decision, d.rationale, d.evidence, d.confidence),
        )
    now = datetime.now().isoformat(timespec="seconds")
    for a in ext.action_items:
        conn.execute(
            """INSERT INTO actions (meeting_id, action, owner, deadline, confidence,
               evidence, commitment_type, status, needs_review, review_reason, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (meeting_id, a.action, a.owner, a.deadline, a.confidence, a.evidence,
             a.commitment_type, "open", 1 if a.needs_review else 0,
             a.review_reason, now),
        )
    for b in ext.blockers:
        conn.execute(
            "INSERT INTO blockers (meeting_id, blocker, impacted_owner, evidence, confidence)"
            " VALUES (?,?,?,?,?)",
            (meeting_id, b.blocker, b.impacted_owner, b.evidence, b.confidence),
        )
    conn.commit()


def unresolved_actions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM actions WHERE status IN ('open','carried') ORDER BY deadline IS NULL, deadline"
    ).fetchall()


def overdue_actions(conn: sqlite3.Connection, today: str | None = None) -> list[sqlite3.Row]:
    today = today or date.today().isoformat()
    return conn.execute(
        "SELECT * FROM actions WHERE status IN ('open','carried')"
        " AND deadline IS NOT NULL AND deadline != '' AND deadline < ? ORDER BY deadline",
        (today,),
    ).fetchall()


def carry_forward(conn: sqlite3.Connection, from_meeting_id: int, to_meeting_id: int) -> int:
    """Copy still-open actions from a past meeting into a new one as 'carried'. Returns count."""
    rows = conn.execute(
        "SELECT * FROM actions WHERE meeting_id=? AND status IN ('open','carried')",
        (from_meeting_id,),
    ).fetchall()
    now = datetime.now().isoformat(timespec="seconds")
    n = 0
    for r in rows:
        conn.execute(
            """INSERT INTO actions (meeting_id, action, owner, deadline, confidence, evidence,
               commitment_type, status, needs_review, review_reason, carried_from, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (to_meeting_id, r["action"], r["owner"], r["deadline"], r["confidence"],
             r["evidence"], r["commitment_type"], "carried",
             r["needs_review"], "carried over from meeting #%d" % from_meeting_id,
             r["id"], now),
        )
        n += 1
    conn.commit()
    return n
