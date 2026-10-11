"""Data-analytics deep-dive (pandas): owner workload, overdue aging, confidence stats.
Exports CSVs + summary JSON for the resume/portfolio.
Falls back gracefully if pandas is not installed.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import database as db

def main():
    base = Path(__file__).resolve().parent.parent
    outdir = base / "data" / "analytics"
    outdir.mkdir(parents=True, exist_ok=True)
    conn = db.connect()
    try:
        import sqlite3
        actions = [dict(r) for r in conn.execute(
            "SELECT a.*, m.title meeting_title FROM actions a JOIN meetings m ON m.id=a.meeting_id").fetchall()]
    finally:
        conn.close()
    (outdir / "actions_export.json").write_text(json.dumps(actions, indent=2), encoding="utf-8")
    try:
        import pandas as pd
    except ImportError:
        print("pandas not installed — JSON export done. pip install pandas for full report.")
        return
    df = pd.DataFrame(actions)
    if df.empty:
        print("no actions yet — run scripts/seed.py first.")
        return
    by_owner = df.groupby(df["owner"].fillna("Unassigned")).agg(
        total=("id", "count"), open_n=("status", lambda s: s.isin(["open", "carried"]).sum()),
        avg_conf=("confidence", "mean")).sort_values("open_n", ascending=False)
    by_owner.to_csv(outdir / "owner_workload.csv")
    df.to_csv(outdir / "actions_full.csv", index=False)
    summary = {"total_actions": int(len(df)),
               "completion_rate": float((df.status == "done").mean()),
               "review_rate": float(df["needs_review"].mean()) if "needs_review" in df else 0.0,
               "avg_confidence": float(df["confidence"].mean()),
               "explicit_share": float((df.commitment_type == "explicit").mean()),
               "top_owner": str(by_owner.index[0]) if len(by_owner) else None}
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("analytics written to", outdir)
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
