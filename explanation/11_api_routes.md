# 11. API Routes (pages + endpoints)

## Pages (server-rendered, all share `base.html` nav)
| Route | Page | Content |
|---|---|---|
| `GET /` | Home | "Paste a meeting. Get the actions." hero, 3-step guide, example item, 1-click sample loaders, KPIs, digest charts, latest meetings |
| `GET /meetings` | Meetings | every meeting, link to detail |
| `GET /meetings/{id}` | Meeting detail | pipeline strip, summary, transcript, decisions, actions, blockers |
| `GET /actions` | Action items, grouped by meeting; filters: meeting, status, explicit/implicit, owner, keyword |
| `GET /decisions` | Decisions log, grouped by meeting (meeting filter) + workspace chat below |
| `GET /analytics` | Analytics | 4 charts + overdue-by-owner + per-meeting tables |
| `GET /review` | Review queue, grouped by meeting (meeting filter), Approve/Done |
| `GET /upload` | New meeting | ingest form (txt/srt/vtt/pdf/docx/audio), carry-forward option, workspace Reset |

## APIs (JSON)
| Route | Does |
|---|---|
| `POST /upload` | ingest file → extract → store → redirect to the new meeting page |
| `POST /demo/{sales,brainstorm}` | 1-click sample ingestion, zero setup |
| `POST /api/actions/{id}/status` | set open/done/carried/dropped |
| `POST /api/actions/{id}/approve` | human review: correct fields, clear flag, boost confidence |
| `POST /api/meetings/{id}/chat` | Q&A scoped to one meeting |
| `POST /api/chat` | workspace-wide assistant |
| `POST /api/reset` | wipe all data (fresh start, with UI confirm) |
| `GET /api/stats`, `/api/review`, `/api/export/actions` | chart data, queue, full export |
