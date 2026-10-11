# 12. How to Run (end to end)

```powershell
pip install -r requirements.txt
```
Then open `.env` and paste your `GEMINI_API_KEY` (leave it empty to run fully offline).
```powershell
python run.py                      # dashboard at http://127.0.0.1:8000
```

## First 5 minutes (recommended order)
1. Open Home — read the 3 steps and the example item.
2. Click **Load sample: sales meeting** — a real meeting appears with actions, review items, decisions.
3. Open its meeting page (pipeline strip → evidence quotes), then **Review queue** → Approve one item.
4. Go to **Decisions**, scroll to **Ask about your meetings**, try "What is overdue?" and "What did we decide?".
5. Upload your own file on **New meeting** (txt, pdf, docx, mp3, wav…).

## Verification commands
```powershell
python scripts/evaluate.py        # P/R/F1 explicit vs implicit + hallucination
python scripts/analytics_report.py # pandas CSVs + summary.json
python -m pytest tests/ -q        # 3 smoke tests
```

## Troubleshooting
- **Charts blank**: Chart.js loads from CDN — tables/KPIs still work offline.
- **Audio upload slow first time**: the whisper `tiny` model (~75 MB) downloads once.
- **Scanned PDF rejected**: no text layer to extract; use a transcript or recording instead.
- **Messy rows from an experiment**: New meeting page → Reset workspace (or delete `data/meetings.db`).
- **Want the real LLM**: paste `GEMINI_API_KEY` in `.env` (and `MIP_PROVIDER=gemini`), restart, re-run eval to compare.
