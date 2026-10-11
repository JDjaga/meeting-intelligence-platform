# 8. Analytics (`app/analytics/metrics.py` + dashboard + pandas)

This is the "data analytics project" half: LLM work produces the rows; analytics turns
rows into oversight.

## `metrics.py` (live dashboard data, stdlib + SQL only)
- `overview()` — meetings, actions, open, overdue, review queue, decisions,
  explicit/implicit counts, completion %.
- `owner_workload()` — per-owner total/open/done/avg-confidence (who is overloaded?).
- `status_breakdown()`, `commitment_split()`, `confidence_histogram()` — chart payloads.
- `overdue_by_owner()`, `actions_per_meeting()`, `review_queue()` — tables and the queue
  (queue ordered newest-meeting-first so items never interleave).
- `group_by_meeting()` — groups any row list under `#id title — n items` sections, newest
  meeting first, transcript order inside. Used by the Actions, Decisions and Review pages
  so each meeting reads as one block instead of scattered IDs.
Because it is plain SQL, the Analytics page can never break from a missing library.

## Dashboard charts (Chart.js)
Owner workload bar, status doughnut, explicit-vs-implicit pie, confidence histogram —
plus overdue-by-owner and actions-per-meeting tables. Analytics is intentionally the
**global cross-meeting view**; per-meeting detail lives on meeting pages and the
meeting filters on Actions/Decisions/Review.

## `scripts/analytics_report.py` (pandas deep-dives)
Exports `data/analytics/actions_full.csv`, `owner_workload.csv`, `summary.json`
(total, completion rate, review rate, avg confidence, explicit share, top owner) —
portfolio artefacts and spreadsheet-friendly data. pandas is quarantined here so the
app never depends on it at runtime.
