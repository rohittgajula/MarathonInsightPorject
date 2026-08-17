"""The 17-week run/walk progression to a 10K.

Indexed by *weeks remaining until race day* rather than by an absolute week number,
so the same table works no matter when an athlete starts. weeks_out 16 is the first
week of the plan; weeks_out 0 is race week.

Sessions are prescriptions, not records. Nothing here reads the athlete's history —
adherence is judged by comparing this against what they actually did.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal, Optional

# weeks_out: (reps, run_minutes, walk_minutes, long_run_km, note)
WEEKS: dict[int, tuple[int, float, float, float, str]] = {
    16: (8, 1.0, 2.0, 2.5, ""),
    15: (8, 1.5, 2.0, 3.0, ""),
    14: (7, 2.0, 2.0, 3.2, ""),
    13: (6, 2.5, 2.0, 3.5, ""),
    12: (6, 3.0, 2.0, 4.0, ""),
    11: (5, 4.0, 2.0, 4.5, ""),
    10: (5, 4.0, 1.5, 4.0, "cutback"),
    9:  (4, 6.0, 2.0, 5.0, ""),
    8:  (3, 8.0, 2.0, 5.5, ""),
    7:  (3, 10.0, 2.0, 6.0, ""),
    6:  (3, 10.0, 1.5, 5.0, "cutback"),
    5:  (2, 15.0, 2.0, 7.0, ""),
    4:  (2, 18.0, 2.0, 8.0, ""),
    3:  (1, 25.0, 0.0, 6.0, "cutback"),
    2:  (2, 20.0, 2.0, 9.5, "peak"),
    1:  (2, 15.0, 2.0, 6.0, "taper"),
    0:  (1, 20.0, 0.0, 10.0, "race"),
}

PHASE = {
    range(13, 17): "Foundation",
    range(8, 13): "Build",
    range(2, 8): "Distance",
    range(0, 2): "Taper & race",
}

# Tue / Thu intervals, Sunday long run. Monday is always rest — new runners get
# injured by frequency, so a fourth running day is never prescribed.
INTERVAL_DAYS = {1, 3}   # Mon=0 … Sun=6
LONG_DAY = 6

Kind = Literal["intervals", "long", "rest", "race"]


@dataclass
class PlannedSession:
    date: dt.date
    kind: Kind
    title: str
    detail: str
    plan_week: int
    weeks_out: int
    phase: str
    note: str
    run_minutes: float = 0.0
    distance_km: float = 0.0


def _fmt(minutes: float) -> str:
    if minutes == int(minutes):
        return f"{int(minutes)} min"
    whole = int(minutes)
    return f"{whole}:{int(round((minutes - whole) * 60)):02d} min"


def _phase_for(weeks_out: int) -> str:
    for span, name in PHASE.items():
        if weeks_out in span:
            return name
    return "Foundation"


def weeks_out_for(race_date: dt.date, on: dt.date) -> int:
    return (race_date - on).days // 7


def session_for(race_date: dt.date, on: dt.date, easy_pace_label: str = "10:00–10:45/km") -> PlannedSession:
    """The prescribed session for one date."""
    weeks_out = weeks_out_for(race_date, on)
    # Before the plan proper starts, hold at week 1 rather than inventing volume.
    key = min(max(weeks_out, 0), 16)
    reps, run_m, walk_m, long_km, note = WEEKS[key]
    plan_week = 17 - key
    phase = _phase_for(key)
    weekday = on.weekday()

    base = dict(
        date=on, plan_week=plan_week, weeks_out=weeks_out, phase=phase, note=note
    )

    if on == race_date:
        return PlannedSession(
            kind="race", title="Race day — 10K",
            detail=(
                "Start at the back. Run the first kilometre at least 30 s slower than "
                "training pace. Hold your run/walk pattern from kilometre one rather "
                "than running until you have to stop. Walk every water station."
            ),
            distance_km=long_km, **base,
        )

    if weekday == LONG_DAY:
        return PlannedSession(
            kind="long", title=f"Long run — {long_km:g} km",
            detail=(
                f"Run/walk the whole way at {easy_pace_label}. This is the session that "
                "actually builds the distance; treat the midweek work as support for it."
            ),
            distance_km=long_km, **base,
        )

    if weekday in INTERVAL_DAYS:
        if reps == 1 and walk_m == 0:
            title = f"{_fmt(run_m)} continuous"
            detail = f"Continuous easy running at {easy_pace_label}. Walk if HR crosses your ceiling."
        else:
            title = f"{reps} × ({_fmt(run_m)} run / {_fmt(walk_m)} walk)"
            detail = (
                f"5 min walk warm-up, then {reps} rounds, then 5 min walk cool-down. "
                f"Run blocks at {easy_pace_label} — keep your cadence and shorten your stride."
            )
        return PlannedSession(
            kind="intervals", title=title, detail=detail,
            run_minutes=reps * run_m, **base,
        )

    return PlannedSession(
        kind="rest", title="Rest or easy walk",
        detail=(
            "No running today. A walk, cycle or swim is fine — adaptation happens on "
            "the days you don't run."
        ),
        **base,
    )


def upcoming(race_date: dt.date, start: dt.date, days: int = 7) -> list[PlannedSession]:
    return [session_for(race_date, start + dt.timedelta(days=i)) for i in range(days)]
