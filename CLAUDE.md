# CLAUDE.md — Timetable GA

## What this project is

A Flask web app that uses a **Genetic Algorithm** to generate conflict-free university timetables. An admin configures courses, teachers, rooms, and timeslots (including per-teacher availability). Clicking "Generate Timetable" runs the GA and renders the best schedule found.

## How to run

```powershell
cd C:\EC\timetable-ga
python app.py
# → http://127.0.0.1:5000
```

Kill and restart if already running:
```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -Confirm:$false
$env:PYTHONIOENCODING="utf-8"; python app.py
```

No build step. No npm. No migrations — `init_db()` runs on startup and creates/seeds the SQLite DB automatically.

## Stack

| Layer | Tech |
|---|---|
| Server | Flask (Python 3), no ORM |
| Database | SQLite via `sqlite3`, file at `database.db` (excluded from git) |
| Templates | Jinja2 server-side rendering, no JS framework |
| Styles | Custom CSS in `static/style.css` — OKLCH token system, no Bootstrap |
| Charts | Chart.js (CDN) — result page only |
| Deployment | Vercel (`vercel.json` + `@vercel/python`), DB at `/tmp/database.db` on Vercel |

## File map

```
app.py              — Flask routes
models.py           — All DB logic (init_db, get_all, insert_record, delete_record, availability helpers)
ga_engine.py        — GeneticAlgorithm class
static/style.css    — Complete design system (OKLCH tokens, all components)
templates/
  index.html        — Home: preflight chip grid + generate CTA
  result.html       — Schedule table + collapsible algo details
  admin.html        — CRUD for courses/teachers/rooms/timeslots + availability editor
PRODUCT.md          — Design principles and brand context (used by impeccable skills)
vercel.json         — Vercel build config
```

## Database schema

```sql
courses      (id, name, credit_hours)
teachers     (id, name)
rooms        (id, name, capacity)
timeslots    (id, day, start_time, end_time)
assignments  (id, run_id, course_id, teacher_id, room_id, timeslot_id, fitness, created_at)
teacher_availability (teacher_id, timeslot_id)  -- join table, PK on both cols
```

- `assignments` always holds **one run** — the entire table is replaced on each GA run.
- `teacher_availability` is the source of truth for which teachers can teach which slots. New teachers default to all slots. Deleting a teacher cascades to this table.
- `models.delete_record()` handles cascade cleanup manually (SQLite FK enforcement is off by default).

## GA parameters (`ga_engine.py`)

| Param | Value | Note |
|---|---|---|
| `POPULATION_SIZE` | 30 | Chromosomes per generation |
| `GENERATIONS` | 100 | Fixed run length |
| `TOURNAMENT_SIZE` | 3 | Selection pressure |
| `MUTATION_RATE` | 0.10 | Per-gene mutation probability |
| `ELITISM` | 2 | Top N carried forward unchanged |
| `HARD` penalty | 10 | Teacher clash, room clash, same-course overlap, unavailability |
| `SOFT` penalty | 2 | Back-to-back classes (same teacher) |

Fitness = `1 / (1 + total_penalty)`. A score of 1.0 = zero violations.

## Key routes

| Method | Path | Handler |
|---|---|---|
| GET | `/` | `index()` — home page |
| POST | `/generate` | `generate()` — runs GA, saves result, renders result.html |
| GET | `/admin` | `admin()` — CRUD dashboard |
| POST | `/admin/add` | `admin_add()` — insert course/teacher/room/timeslot |
| POST | `/admin/delete` | `admin_delete()` — delete with cascade |
| POST | `/admin/availability` | `admin_availability()` — set teacher timeslot availability |
| GET | `/export` | `export()` — download last schedule as CSV |

## Design system (`static/style.css`)

All colors are OKLCH tokens. Never add raw hex or `rgb()` values — use tokens:

```css
--brand / --brand-dark / --brand-light / --brand-subtle
--bg / --surface / --border / --border-strong
--ink / --ink-2 / --ink-3
--success / --success-bg / --success-border
--warning / --warning-bg / --warning-border
--danger  / --danger-bg  / --danger-border
```

Spacing tokens: `--s1` through `--s16` (4pt grid).
Type tokens: `--text-xs` through `--text-3xl`.

Key component classes: `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-danger`, `.btn-success`, `.btn-generate`, `.card`, `.card-header`, `.admin-section`, `.admin-form-card`, `.admin-table-card`, `.avail-section`, `.avail-grid`, `.avail-check`, `.status-section.success/.warning`, `.preflight-grid`, `.preflight-card`, `.algo-details`, `.metrics-row`, `.badge`, `.alert`.

## Conventions

- **No Bootstrap**. All styling via `static/style.css` only.
- **No ORM**. All DB access via `sqlite3` in `models.py`.
- **Flash messages** use `category='success'|'error'|'warning'` — templates map these to `.alert.success/.error/.warning`.
- **Delete confirmations** use `data-confirm="..."` attributes + a JS event listener in `admin.html`. Never use inline `onsubmit="return confirm('...{{ var }}...')"` — it's an XSS risk when names contain quotes.
- **Jinja2 autoescaping** is on for `.html` files. Don't use `| safe` on user-supplied data.
- All `SELECT` queries go through `get_all(table)` which validates against `_ALLOWED_TABLES`. Raw table names must never come from user input directly to `f'SELECT * FROM {table}'`.

## impeccable skills

Design critique/redesign tooling lives in `.claude/skills/impeccable/`. The PRODUCT.md at root defines brand, users, and design principles for the `/impeccable` commands.
