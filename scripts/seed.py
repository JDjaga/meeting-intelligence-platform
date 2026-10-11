"""Seed DB from sample transcripts (offline, deterministic)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import database as db
from app.llm.extractor import extract_meeting

SAMPLES = [
    ("Sprint Planning — Billing Service", "2026-10-03", "data/sample_transcripts/sprint_planning.txt"),
    ("Design Review — Checkout", "2026-10-06", "data/sample_transcripts/design_review.txt"),
    ("Incident Retro — Orders Outage", "2026-10-09", "data/sample_transcripts/incident_retro.txt"),
]

def main():
    base = Path(__file__).resolve().parent.parent
    conn = db.connect()
    # fresh seed: wipe existing demo rows
    conn.execute("DELETE FROM blockers"); conn.execute("DELETE FROM actions")
    conn.execute("DELETE FROM decisions"); conn.execute("DELETE FROM meetings")
    conn.execute("DELETE FROM sqlite_sequence")
    conn.commit()
    for title, mdate, rel in SAMPLES:
        text = (base / rel).read_text(encoding="utf-8")
        ext, provider = extract_meeting(text, title=title, meeting_date=mdate, provider="rules")
        mid = db.insert_meeting(conn, title, mdate, text, ext.summary, ext.attendees)
        db.insert_extraction(conn, mid, ext)
        n_rev = sum(1 for a in ext.action_items if a.needs_review)
        print(f"meeting #{mid} [{provider}] {title}: {len(ext.action_items)} actions "
              f"({sum(1 for a in ext.action_items if a.commitment_type=='explicit')} explicit, "
              f"{sum(1 for a in ext.action_items if a.commitment_type=='implicit')} implicit), "
              f"{len(ext.decisions)} decisions, {n_rev} in review")
    print("seed complete.")

if __name__ == "__main__":
    main()
