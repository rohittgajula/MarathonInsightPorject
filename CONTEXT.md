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

Backend code is bind-mounted and reloads, but **Python dependencies live in the image**:
after touching `requirements.txt`, `docker compose build backend` then
`docker compose up -d --force-recreate backend worker beat`. A plain `up -d` will not
pick them up, and the failure looks like a `ModuleNotFoundError` in code you just
verified. The build pulls large wheels and can exceed a two-minute timeout — give it room.

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
- **The model reads language; Python makes the decisions.** The LLM turns a log entry
  into structured facts (`ai_extract.py`) and stops there. This is also what makes
  the provider swappable — `analyse()` returns a dict and nothing downstream knows
  or cares which model produced it. Whether the session is
  eased, which exercises are prescribed, how much water to drink — all deterministic
  code in `readiness.py`, `exercises.py`, `fueling.py`. The failure mode of a bad
  extraction is a wrong *fact* the athlete can see and correct, not a wrong
  prescription. It also keeps the "only ever easier" guarantee somewhere a
  hallucination cannot reach.
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
| `athletes` | `Athlete` (tenancy root, pace/HR bands, `training_days`, timezone, `weight_kg`) |
| `ingest` | `RawFitFile`, FIT parser, Garmin sync/connect/wellness, weather |
| `activities` | `Activity`, `ActivityRecord` (per-second), `Segment`, `ActivityMetrics`, chart notes, compare |
| `analysis` | `segmentation.py`, `metrics.py` — **pure, no Django imports** |
| `plans` | `Race`, plan template, readiness, coaching, calendar, weekly, niggles, race plan, warm-up, weather advice, `session_review.py` (planned vs actual for one day), `exercises.py` (34-exercise strength/rehab library), `fueling.py` (hydration + fuel, heat-scaled) |
| `journal` | `DailyLog` (short, drives readiness), `JournalEntry` (long-form, drives nothing), `DailyMetrics` (Garmin wellness), `ai_extract.py` + `advice.py` + `tasks.py` (LLM reading and what follows from it) |
| `achievements` | `EarnedAchievement` + catalog (definitions in code, only earnings stored); `services.next_up` feeds the dashboard's one-line nudge |

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
*shortens* it. Pain is now graded 1–5 with *when* it hurt, so a twinge at rest and
pain that stopped a run are no longer the same signal — but anything unquantified is
still treated as serious.

**`plans/session_review.py`** — one day, planned against what actually happened.
Opened from any row of the week table (`DayReview.tsx`). The table can only ever show
the *prescription*; this is the other half. It shares `planned_for()` with the
calendar so a row and its popup can never disagree, and falls back to the athlete's
standing pace/HR bands on a day that prescribed none — a run on a rest day is exactly
the one worth measuring. Before-plan dates get no verdict, matching `weekly.py`.

**The week table's columns are fixed in pixels, measured, not guessed.** Percentages
looked tidier and clipped `DISTANCE`, `optional walk, easy`, and `130–145 bpm` at real
window sizes. `keepPreviousData` holds the old week on screen while the next loads —
without it the table empties, collapses to its min-width and springs back.

**A rest day prescribes an optional walk, and says so with numbers.** Its own text
always said "20–30 minutes easy is plenty"; the row used to show "optional walk,
easy" and four dashes. It now carries the walk pace and HR bands, 25 min and 2.2 km,
flagged `optional=True` — real targets that are not owed. `weekly.py` still excludes
rest from `planned_sessions`, so a skipped one is never a shortfall, and a session
dropped for pain or illness clears the flag: that is the one case where rest means
rest rather than "walk if you fancy it".

**Every session accounts for all of its minutes** as either `run_minutes` or
`walk_minutes`. Long runs and jogs are distance-targeted but still run/walk, so their
running time is derived from the same run:walk ratio that week's intervals prescribe
— it was `0.0` for years, which is why the week table showed a blank RUN TIME on
every long run. `readiness.apply` rescales both when it eases a session. In the day
review, `none` means prescribed as zero (a walk targets no running on purpose) and
`—` means nothing was prescribed at all; conflating them made a walk day look like
missing data.

**The hero's slide band (`HeroSlides.tsx`) is a slider, not a carousel.** It holds
the session detail and the closest achievement so the hero stops growing every time
something else is worth saying. Auto-advance stops permanently on any interaction
and pauses on hover or focus; hidden slides are `inert`. The readiness note is
pinned *outside* it on purpose — on a critical day it says "do not train hard
today", and that must not sit behind a slide nobody advances to. Clip the track at
an inner viewport: `overflow: hidden` on the padded outer element lets the next
slide show through the right-hand padding.

**Exercise animations are keyed by name.** `ExerciseAnimation.tsx` maps a key from
`plans/exercises.py` (or `warmup.py`) to an SVG + CSS-keyframe figure; adding a
demonstration is a matter of matching the key, nothing else is wired up. 28 of 34
catalogued exercises have one, and every exercise that `FIRST_LINE` or `MAINTENANCE`
can actually prescribe is covered — the component returns null for the rest, so a
gap degrades to no picture rather than a broken one. Figures share the `Torso` /
`Arm` / `Leg` parts so proportions stay consistent, and several exercises share a
keyframe rather than getting a near-duplicate.

**The dashboard log renders prescriptions `compact`** — names and doses only, with
the why/how and the animations on Strength & rehab. Rendering them in full made the
log card the tallest thing on the page.

**A day's log appends, it never overwrites.** Posting to `/logs/` for a date that
already has an entry adds a line rather than replacing the text — a day gets written
in pieces (sleep in the morning, a niggle after the run), and replacing silently
destroyed the earlier note. The box clears after a save and today's text is rendered
beneath it, so an empty box cannot be mistaken for a lost entry. There is no in-app
edit: correcting a line means deleting the day's log.

**A log's date is not always the day it was typed.** `DailyLog.applies_to_date` holds
the day an entry bears on. Everything reading a log must go through
`journal.models.effective_logs` / `logs_by_day`; filtering on `log_date` silently
drops the case the field exists for.

The schema asks **which day's *session* an entry affects**, not which calendar day its
words describe — those differ, and getting it wrong is subtle. "Last night I slept
badly" written in the morning is about *today's* session: the bad night is what you
carry into it. Asked the other way, the model answered "yesterday" and was right about
the words and wrong for the plan. If that field is ever reworded, re-check that case
first.

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
- **`npm run build` is blocked** by two unused-variable errors (`tsc` runs first):
  `MetricOverlay.tsx:51` and `Home.tsx:13`. Dev runs fine; production build does not.
- **`components/GarminPanel.tsx` is dead** — superseded by `GarminButton`; safe to delete.
- Not built: shoe mileage, data export, real push/email notification, PWA.
- **No Settings UI for `weight_kg`.** The field exists and every fuelling figure
  scales from it; unset, `fueling.py` assumes 70 kg and says so on each response.

## The log reader, and how it fails

`journal/ai_extract.py` reads the free-text daily log. **Two backends, one schema:**
Gemini (`gemini-3.7-flash`, free tier, the default) and Claude (`claude-opus-5`, paid,
the better reader of casual code-switched text). Whichever of `GEMINI_API_KEY` /
`ANTHROPIC_API_KEY` is set wins, Gemini first; `LOG_AI_PROVIDER` forces one, and an
explicit choice whose key is missing does *not* fall through to the other. With
neither, the keyword extractor still runs and the UI says which parser produced the
chips.

Both honour the same schema dialect — `anyOf`, `enum`, `required`,
`additionalProperties: false` — so nothing but the transport is provider-specific.

Consequences already hit:

- **Never construct the client inline.** `genai.Client().interactions.create(...)` as
  one expression lets the client be garbage-collected mid-request; it closes its httpx
  pool on the way out and the call dies with "client has been closed". Clients are
  cached in `_CLIENTS`.
- **A rate limit is not a failure.** Gemini's free tier capped us at
  `generate_content_free_tier_requests, limit: 20`, and waiting the ~50 s the error
  named did not clear it. `RateLimited` is a distinct status from `failed` so the row
  is retried rather than written off; `journal.tasks.sweep_unread` runs every 10 min
  on beat and heals a spent quota with nobody watching. A history re-parse
  (`reparse_logs`) paces itself at 3.5 s per entry to stay under the limit.
- **Free-tier content is used to improve Google's products**; the paid tier is not.
  These logs are sleep, alcohol, injuries and mood. That trade was made knowingly —
  revisit it before adding anything more sensitive.
- Bump `AI_EXTRACTION_VERSION` when the schema or prompt changes materially;
  `reparse_logs` finds every row that predates it.

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
