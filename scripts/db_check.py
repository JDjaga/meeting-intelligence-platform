"""SQLite health check: live report + self-contained CRUD self-test (rolled back).

Usage:  python scripts/db_check.py
Reads your real data (report) and proves store/add/delete work by inserting,
updating and deleting TEST rows inside one transaction that is ROLLED BACK —
your data is never touched.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import database as db


def report(c) -> None:
    print("== LIVE DATA REPORT ==")
    for t in ("meetings", "decisions", "actions", "blockers"):
        print(f"{t:10s}: {c.execute(f'SELECT COUNT(*) n FROM {t}').fetchone()['n']} rows")
    print("\nmeetings:")
    for r in c.execute("SELECT id, title, meeting_date FROM meetings ORDER BY id"):
        n = c.execute("SELECT COUNT(*) n FROM actions WHERE meeting_id=?", (r["id"],)).fetchone()["n"]
        print(f"  #{r['id']} {r['title']!r} ({r['meeting_date']}) — {n} actions")


def crud_selftest(c) -> None:
    print("\n== CRUD SELF-TEST (will roll back) ==")
    before = c.execute("SELECT COUNT(*) n FROM actions").fetchone()["n"]
    mid = c.execute(
        "INSERT INTO meetings (title, meeting_date, transcript, summary, attendees, created_at)"
        " VALUES (?,?,?,?,?,?)",
        ("SELFTEST", "2026-01-01", "Test transcript.", "", "[]", "2026-01-01T00:00:00")).lastrowid
    print(f"CREATE meeting -> id {mid}")
    aid = c.execute(
        "INSERT INTO actions (meeting_id, action, owner, deadline, confidence, evidence,"
        " commitment_type, status, needs_review, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (mid, "Selftest action", "Tester", "2026-02-01", 0.9, "Test transcript.",
         "explicit", "open", 0, "2026-01-01T00:00:00")).lastrowid
    print(f"CREATE action  -> id {aid}")
    got = c.execute("SELECT action, status FROM actions WHERE id=?", (aid,)).fetchone()
    assert (got["action"], got["status"]) == ("Selftest action", "open")
    print(f"READ action    -> {got['action']!r} [{got['status']}]  OK")
    c.execute("UPDATE actions SET status='done' WHERE id=?", (aid,))
    assert c.execute("SELECT status s FROM actions WHERE id=?", (aid,)).fetchone()["s"] == "done"
    print("UPDATE status  -> open -> done  OK")
    c.execute("DELETE FROM actions WHERE id=?", (aid,))
    c.execute("DELETE FROM meetings WHERE id=?", (mid,))
    assert c.execute("SELECT COUNT(*) n FROM actions WHERE id=?", (aid,)).fetchone()["n"] == 0
    print("DELETE rows    -> gone  OK")
    c.execute("ROLLBACK")
    after = c.execute("SELECT COUNT(*) n FROM actions").fetchone()["n"]
    assert after == before, (before, after)
    print(f"ROLLBACK       -> actions count {before} -> {after} (untouched)  OK")
    print("\nCRUD self-test PASSED: store, add, update, delete all work.")


def main() -> None:
    c = db.connect()
    try:
        report(c)
        crud_selftest(c)
    finally:
        c.close()


if __name__ == "__main__":
    main()
