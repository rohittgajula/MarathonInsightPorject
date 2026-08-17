# Run Project

A training system built on top of Garmin data, for run/walk beginners working
towards a target race.

It is deliberately **not** a Garmin Connect clone. Connect already does sleep, HRV,
Body Battery and trends well. This builds the layers Connect cannot have:

1. **Plan adherence** — Connect doesn't know you have a 10K on 13 December or that
   your run blocks should be 10:00–10:45/km.
2. **Run/walk truth** — Connect's lap data hides the structure of a beginner's
   session. A "2.65 km run" is often five short run blocks with walking between.
3. **Recovery signal** — heart-rate behaviour in the walk breaks, which is the
   clearest early evidence that base fitness is improving.

## Why the raw `.fit` file is stored permanently

Garmin's [Connect Developer Program](https://developer.garmin.com/gc-developer-program/)
requires a legal entity, rejects personal-use applications, and is currently on
hold. There is no consumer API. Any sync route is therefore unofficial and can
break without warning, so:

- every uploaded file is stored byte-for-byte and never discarded;
- manual `.fit` upload is a first-class path, not a fallback;
- all derived data is rebuildable offline via `build_derived()`.

## Quick start

```bash
cp .env.example .env
docker compose up -d
docker compose exec backend python manage.py create_athlete you --password 'change-me' --superuser
```

Frontend on http://localhost:5173, API on http://localhost:8000/api,
Django admin on http://localhost:8000/admin.

Import history from the command line:

```bash
docker compose exec backend python manage.py import_fit /path/to/*.fit --athlete 1
```

## Services

| Service | Purpose |
|---|---|
| `backend` | Django + DRF API |
| `worker` | Celery worker — parsing and metric rebuilds |
| `beat` | Celery beat — scheduled sweeps |
| `db` | Postgres 16 |
| `redis` | Broker + result backend |
| `frontend` | Vite + React + TypeScript |

`beat` depends on `django_celery_beat` tables existing. On a completely fresh
volume it can start before `backend` finishes migrating; `docker compose restart
beat` once is enough.

## The derived layer

Nothing derived is ever authored by hand. `apps/analysis/segmentation.py` splits
the per-second series into run / walk / stop blocks by **cadence**, not GPS speed —
walking sits near 100–125 spm and running rarely drops below 140, while GPS speed
for a slow jog and a brisk walk overlap heavily.

Two heart-rate metrics come out of the walk breaks:

- **`hr_recovery_60s`** — peak HR minus HR 60 s later. Measured from the peak, not
  the block boundary, because cardiac lag keeps HR climbing 15–25 s after running
  stops. Rises as fitness improves.
- **`hr_overshoot_bpm`** — how far HR kept climbing *after* stopping. A large
  overshoot means that block outran the athlete's aerobic system. Falls towards
  zero as fitness improves.

`ALGORITHM_VERSION` in `segmentation.py` is stored on every `ActivityMetrics` row.
Bump it when classification changes, then re-run to roll the change across history:

```bash
docker compose exec backend python -c "
from apps.athletes.models import Athlete
from apps.ingest.services import reprocess_athlete
print(reprocess_athlete(Athlete.objects.get(pk=1)))
"
```

## Tests

```bash
docker compose exec backend python -m pytest tests/ -q
```

The fixture is a real Instinct 2X recording whose known ground truth (5 run blocks,
longest 291 s / 581 m, 8:27/km) pins the segmentation algorithm.

## Multi-tenant

`Athlete` is the tenancy root and everything hangs off it. `AthleteScopedMixin`
filters every queryset, so there is no code path that returns another athlete's
rows.

## Charts

The palette is validated for colour-vision deficiency rather than eyeballed —
run/walk/stop clear the CVD separation and normal-vision floors in both light and
dark mode. Pace and heart rate are two stacked charts sharing an x-axis, never a
dual-axis chart.

## Status

Phase 1 complete: ingest, segmentation, derived metrics, race targets, activity
list/detail, session charts, route map.

Not built yet: Garmin auto-sync, calendar, nutrition/alcohol logging and
correlations, daily briefing. See the project notes for phasing.
