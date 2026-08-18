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

# Fallback week used only when no athlete is supplied (tests, previews). Live plans
# read the athlete's own `training_days`.
DEFAULT_WEEK = {0: "rest", 1: "intervals", 2: "rest", 3: "intervals",
                4: "rest", 5: "walk", 6: "long"}

Kind = Literal["intervals", "long", "rest", "race", "jog", "walk", "cross"]


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
    # Walking is prescribed work on this plan, not a gap in it, so it gets a target
    # like anything else. Without it the week table could only ever say what a
    # session was *not*, and a walk day showed a blank row.
    walk_minutes: float = 0.0
    distance_km: float = 0.0
    # Concrete targets so the schedule answers "what am I aiming at" per day.
    target_pace: str = ""
    target_hr: str = ""
    # The numbers behind those labels. Carried alongside rather than parsed back out
    # of the strings, because "optional walk, easy" has no numbers in it and a review
    # that guessed would be inventing a target the plan never set. Zero means
    # "nothing prescribed", which is a different statement from "prescribed as zero".
    target_pace_min_s: int = 0
    target_pace_max_s: int = 0
    target_hr_min: int = 0
    target_hr_max: int = 0
    # The shape of an interval session, not just its total. A day review needs to say
    # "the plan asked for 1 min blocks and you ran 4:51" — which the summed
    # run_minutes cannot express.
    reps: int = 0
    rep_run_minutes: float = 0.0
    total_minutes: float = 0.0
    focus: str = ""
    # Set when a daily log moves the session off the template.
    adjusted: bool = False
    adjust_reason: str = ""
    adjust_severity: str = ""
    # "If you do it, here is the target" — as opposed to work the week depends on.
    # A rest day's walk has real numbers behind it, but missing it is not a shortfall,
    # and the two must stay distinguishable downstream.
    optional: bool = False
    # True for dates earlier than the plan's own start. The table is clamped so those
    # dates still return something sensible, but they are not week 1 — the plan simply
    # had not begun, and judging them against it is meaningless.
    before_plan: bool = False


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


def _pace_label(athlete) -> str:
    def fmt(sec):
        return f"{int(sec // 60)}:{int(sec % 60):02d}"
    return f"{fmt(athlete.easy_pace_min)}–{fmt(athlete.easy_pace_max)}/km"


def session_for(race_date: dt.date, on: dt.date, athlete=None) -> PlannedSession:
    """The prescribed session for one date."""
    easy_pace_label = _pace_label(athlete) if athlete else "10:00–10:45/km"
    hr_label = f"{athlete.hr_easy_min}–{athlete.hr_easy_max} bpm" if athlete else "130–145 bpm"
    weeks_out = weeks_out_for(race_date, on)
    # Before the plan proper starts, hold at week 1 rather than inventing volume.
    key = min(max(weeks_out, 0), 16)
    reps, run_m, walk_m, long_km, note = WEEKS[key]
    plan_week = 17 - key
    phase = _phase_for(key)
    weekday = on.weekday()

    # Walking targets, shared by the prescribed walk day and the optional walk on a
    # rest day. 11.2 min/km is the pace the walk session's own 2.5 km / 28 min implies.
    walk_pace_label = "9:00–11:00/km"
    walk_pace_min, walk_pace_max = 540, 660
    walk_min_per_km = 11.2

    pace_min = athlete.easy_pace_min if athlete else 600
    pace_max = athlete.easy_pace_max if athlete else 645
    hr_min = athlete.hr_easy_min if athlete else 130
    hr_max = athlete.hr_easy_max if athlete else 145

    base = dict(
        date=on, plan_week=plan_week, weeks_out=weeks_out, phase=phase, note=note,
        target_pace=easy_pace_label, target_hr=hr_label,
        target_pace_min_s=pace_min, target_pace_max_s=pace_max,
        target_hr_min=hr_min, target_hr_max=hr_max,
        before_plan=weeks_out > 16,
    )

    # Names of the target fields, so the branches that prescribe something different
    # (or nothing) can drop the whole set rather than half of it.
    PACE_KEYS = ("target_pace", "target_pace_min_s", "target_pace_max_s")
    HR_KEYS = ("target_hr", "target_hr_min", "target_hr_max")

    # A long run and a jog are targeted by distance, but at this stage they are still
    # run/walk — so the running time inside them is real and was simply never
    # recorded. It follows the same run:walk ratio the week's intervals prescribe,
    # which is the only ratio the plan actually states.
    run_share = run_m / (run_m + walk_m) if (run_m + walk_m) else 1.0

    if on == race_date:
        return PlannedSession(
            kind="race", title="Race day — 10K",
            detail=(
                "Start at the back. Run the first kilometre at least 30 s slower than "
                "training pace. Hold your run/walk pattern from kilometre one rather "
                "than running until you have to stop. Walk every water station."
            ),
            distance_km=long_km, focus="Finish", total_minutes=long_km * 11,
            run_minutes=round(long_km * 11 * run_share, 1),
            walk_minutes=round(long_km * 11 * (1 - run_share), 1),
            **base,
        )

    day_type = athlete.day_type(weekday) if athlete else DEFAULT_WEEK[weekday]

    if day_type == "long":
        total = round(long_km * 11)
        return PlannedSession(
            kind="long", title=f"Long run — {long_km:g} km",
            detail=(
                f"Run/walk the whole way at {easy_pace_label}. This is the session that "
                "actually builds the distance; treat the midweek work as support for it."
            ),
            distance_km=long_km, focus="Build distance",
            run_minutes=round(total * run_share, 1),
            walk_minutes=round(total * (1 - run_share), 1),
            total_minutes=total, **base,
        )

    if day_type == "jog":
        # An easy continuous-ish run, deliberately shorter than the long run so the
        # week still has one clear distance session.
        jog_km = round(long_km * 0.6, 1)
        total = round(jog_km * 11)
        return PlannedSession(
            kind="jog", title=f"Easy jog — {jog_km:g} km",
            detail=(
                f"Run/walk at {easy_pace_label}, whatever mix feels sustainable. This is "
                "volume at low cost — it should feel easier than your interval days."
            ),
            distance_km=jog_km, focus="Easy volume",
            run_minutes=round(total * run_share, 1),
            walk_minutes=round(total * (1 - run_share), 1),
            total_minutes=round(jog_km * 11), **base,
        )

    if day_type == "walk":
        return PlannedSession(
            kind="walk", title="Easy walk — 25–30 min",
            detail=(
                "Brisk walking, no running. It builds aerobic base with none of the "
                "impact load, which is exactly what a body adapting to running needs. "
                "Quick enough that talking takes a little effort."
            ),
            focus="Active recovery", total_minutes=28, walk_minutes=28,
            # A walk has real targets; leaving them blank made the row read as
            # "nothing prescribed" when this is prescribed work.
            distance_km=2.5,
            **{k: v for k, v in base.items() if k not in PACE_KEYS + HR_KEYS},
            target_pace=walk_pace_label,
            target_pace_min_s=walk_pace_min, target_pace_max_s=walk_pace_max,
            target_hr=f"{max(athlete.hr_easy_min - 20, 90)}–{athlete.hr_easy_min} bpm"
                      if athlete else "110–130 bpm",
            target_hr_min=max(hr_min - 20, 90) if athlete else 110,
            target_hr_max=hr_min if athlete else 130,
        )

    if day_type == "cross":
        return PlannedSession(
            kind="cross", title="Cross-training — 30 min",
            detail=(
                "Cycle, swim or row at an easy effort. Aerobic work without the "
                "repetitive impact that causes most beginner running injuries."
            ),
            focus="Aerobic, no impact", total_minutes=30,
            **{k: v for k, v in base.items() if k not in PACE_KEYS},
            target_pace="",
        )

    if day_type == "intervals":
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
            run_minutes=reps * run_m, reps=reps, rep_run_minutes=run_m,
            # The recovery halves plus the 5 min walk each side. Every minute of an
            # interval session is now accounted for as either run or walk.
            walk_minutes=reps * walk_m + 10,
            focus="Time on feet",
            total_minutes=round(reps * (run_m + walk_m) + 10), **base,
        )

    # A rest day prescribes no running, but its own text has always said "if you do
    # walk, 20–30 minutes easy is plenty" — which is a target the row was discarding.
    # Showing "optional walk, easy" and four dashes told the athlete to walk without
    # saying how far, how fast, or for how long.
    rest_walk_minutes = 25.0
    return PlannedSession(
        kind="rest", title="Rest or easy walk",
        detail=(
            "No running today. A walk, cycle or swim is fine — adaptation happens on "
            "the days you don't run. If you do walk, 20–30 minutes easy is plenty."
        ),
        focus="Recover", optional=True,
        walk_minutes=rest_walk_minutes, total_minutes=rest_walk_minutes,
        distance_km=round(rest_walk_minutes / walk_min_per_km, 1),
        **{k: v for k, v in base.items() if k not in PACE_KEYS + HR_KEYS},
        target_pace=walk_pace_label,
        target_pace_min_s=walk_pace_min, target_pace_max_s=walk_pace_max,
        target_hr=f"{max(hr_min - 20, 90)}–{hr_min} bpm",
        target_hr_min=max(hr_min - 20, 90), target_hr_max=hr_min,
    )


def upcoming(race_date: dt.date, start: dt.date, days: int = 7, athlete=None) -> list[PlannedSession]:
    return [session_for(race_date, start + dt.timedelta(days=i), athlete) for i in range(days)]
