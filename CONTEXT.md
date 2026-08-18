# Run Project — context for a new session

Personal training system for **Rohit**, targeting a **10K on Sunday 13 December 2026**
(Bajaj Pune Marathon, 10K category). Goal is to *finish*; there is no time target.
Repo: `github.com/rohittgajula/MarathonInsightPorject` (private).

## Start here

```bash
cd ~/Desktop/run-project && docker compose up -d
```

Frontend http://localhost:5173 · API http://localhost:8000/api · admin `/admin`.
Dev login `rohit` / `runproject-dev` (change before this leaves the machine).

Vite's watcher sometimes misses newly created files. If a new component doesn't
appear, `docker compose restart frontend` — this has bitten several times.

Tests: `docker compose exec backend python -m pytest tests/ -q` (46 passing).

## What this is, and what it deliberately is not

Garmin Connect already does sleep, HRV, Body Battery and trends well. This does **not**
rebuild those. It exists for the three layers Garmin cannot have:

1. **Plan adherence** — Garmin doesn't know about 13 December or that run blocks should
   be 10:00–10:45/km.
2. **Run/walk truth** — Garmin's lap data hides that a beginner's "2.65 km run" was five
   short run blocks with walking between.
3. **Narrative** — turning numbers into a decision.

## Principles that shaped the code (violating these caused most bugs so far)

- **Every claim cites a number the system holds.** Where there isn't enough data, the UI
  says so rather than implying a trend. Correlations are gated at 12 observations.
- **Anything describing today's session reads from the *session object*, never the
  athlete profile.** The profile holds defaults; the session is what those became after
  the template, the day type, and the readiness adjustment. Reading the profile skips all
  three — this caused a running heart rate to be prescribed for a walk.
- **Readiness rules only ever make a session easier.** An automated system must not talk
  someone into more training.
- **Raw data is kept permanently** — `.fit` bytes and verbatim Garmin JSON — so a better
  parser can be re-run over history instead of re-fetching.
- **Colour is validated, not chosen by eye.** Chart palettes were run through a CVD
  validator; several plausible-looking sets failed at ΔE 1–5 under protanopia.
- **Dates come from `Athlete.local_today`**, never `timezone.localdate()`. Django's
  TIME_ZONE is UTC and at 00:48 in Kolkata that is still yesterday.

## Architecture

Docker Compose: `backend` (Django 5 + DRF) · `worker` + `beat` (Celery) · `db` (Postgres)
· `redis` · `frontend` (Vite + React + TS, Recharts, TanStack Query).

Multi-tenant from the start: `Athlete` is the tenancy root, `AthleteScopedMixin` filters
every queryset.

### Backend apps

| App | Holds |
|---|---|
| `athletes` | `Athlete` (tenancy root, pace/HR bands, `training_days`, timezone) |
| `ingest` | `RawFitFile`, FIT parser, Garmin sync/connect/wellness, weather |
| `activities` | `Activity`, `ActivityRecord` (per-second), `Segment`, `ActivityMetrics`, chart notes, compare |
| `analysis` | `segmentation.py`, `metrics.py` — **pure, no Django imports** |
| `plans` | `Race`, plan template, readiness, coaching, calendar, weekly, niggles, race plan, warm-up, weather advice |
| `journal` | `DailyLog` (short, drives readiness), `JournalEntry` (long-form, drives nothing), `DailyMetrics` (Garmin wellness) |
| `achievements` | `EarnedAchievement` + catalog (definitions in code, only earnings stored) |

### The pieces that matter most

**`analysis/segmentation.py`** — the crown jewel. Splits per-second samples into
run/walk/stop by **cadence**, not GPS speed (a slow jog and a brisk walk overlap in speed
but not cadence; ≥140 spm is running). Produces two HR metrics from walk breaks:
`hr_recovery_60s` measured **from peak**, not the block boundary (cardiac lag keeps HR
climbing 15–25 s after stopping), and `hr_overshoot_bpm`. Bump `ALGORITHM_VERSION` on
change, then re-run `build_derived` across history.

**`plans/template.py`** — the 17-week table, indexed by *weeks remaining* so it works
from any start date. Clamped at 16 weeks out; `before_plan` marks earlier dates so they
are not reported as "week 1".

**`plans/readiness.py`** — turns log + wellness into a session adjustment, with a
`severity` of caution/critical. Pain and illness *drop* the session; poor sleep
*shortens* it.

## Current state of the data

12 activities (3 runs), 15 wellness days, 1 achievement earned. The one baseline run is
**17 Aug: 2.65 km, five run blocks, longest 4:51, 8:27/km** — roughly 90 s/km faster than
prescribed, which is why every insight leads on slowing down.

Live finding worth knowing: **sleep debt is the loudest signal in his data** — around 20 h
short across seven nights, readiness dipping to 11/100. Bigger lever right now than pace.

## Known gaps / next steps

- **No database tests.** All 46 cover pure logic (segmentation, metrics, extraction).
  Nothing covers plan/readiness/timezone, which is exactly where the worst bugs lived.
  `pytest-django` plus a handful of tests would have caught the UTC bug.
- **No React error boundary** — one component throwing blanks the whole app.
- **`components/GarminPanel.tsx` is dead** — superseded by `GarminButton`; safe to delete.
- **Log extraction is keyword-based** and will keep hitting edge cases ("a few drinks",
  "knee is fine now"). Raw text is stored verbatim precisely so an LLM parser can be
  swapped in and re-run over history.
- Not built: shoe mileage, data export, real push/email notification, PWA.

## Garmin, and why it is fragile

Garmin has **no personal API** — the Connect Developer Program requires a legal entity,
rejects personal use, and is currently on hold. This rides the unofficial
`garminconnect` library against a saved OAuth token.

Consequences already hit:
- `garmin-mcp`'s CLI logs in successfully and **writes no token** on non-MFA accounts
  (it sets `return_on_mfa=True`, which short-circuits the library's own `dump()`).
  `scripts/garmin_login.py` exists to work around this and verifies the token landed.
- Backend and login tool must run the **same** garminconnect version — 0.2.x reads
  `oauth1_token.json`, 0.3.x writes a combined `garmin_tokens.json`. Both are pinned to
  **0.3.10**.
- Garmin's `*TimestampLocal` fields are epoch-ms **already shifted to local** — applying a
  timezone on top double-counts it.
- Garmin dates a night of sleep by the **morning it ends**, so day D's row is the sleep
  before a session on D. Written notes, by contrast, come from the evening before.

Weather uses **Open-Meteo** (no key) and **Nominatim** for place names (cached a month,
rounded to ~1 km to respect its rate limit).
