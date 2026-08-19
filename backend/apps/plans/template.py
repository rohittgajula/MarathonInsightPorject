"""The 17-week run/walk progression to a 10K, and the modes that surround it.

The table is indexed by *weeks remaining until race day* rather than by an absolute
week number, so the same rows work no matter when an athlete starts. weeks_out 16 is
the first week of the plan; weeks_out 0 is race week.

The table is only half the plan. It describes a run-up and nothing else, so the days
after a race, the days before a second one, and the stretch between two races that
are too close to build across all get their own modes — see `schedule.py`, which
decides which mode a date is in. Every mode ends up in `_from_row`, so a maintenance
week and a build week are laid out across the athlete's own training days by exactly
the same code.

Sessions are prescriptions, not records. Nothing here reads the athlete's history —
adherence is judged by comparing this against what they actually did.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal, Optional

from .schedule import DayContext, Schedule

# weeks_out: (reps, run_minutes, walk_minutes, long_run_km, note)
Row = tuple[int, float, float, float, str]

WEEKS: dict[int, Row] = {
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

# The level the plan holds at when there is nothing to build towards — between two
# races that are too close together, and after the last race on the calendar. Below
# peak, above taper: enough to keep what a block bought, little enough to sit on for
# months without digging a hole.
MAINTENANCE: Row = (2, 15.0, 2.0, 7.0, "")

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

# Minutes per kilometre used to turn a prescribed distance into a prescribed
# duration. It is the run/walk pace a beginner actually covers ground at, and it is
# the same number the race-day estimate uses.
MIN_PER_KM = 11


@dataclass
class PlannedSession:
    date: dt.date
    kind: Kind
    title: str
    detail: str
    # None outside the ramp. A recovery day is not "week 15 of 17", and printing a
    # week number over it would be the plan claiming a position it has left.
    plan_week: Optional[int]
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
    # Which of the schedule's modes produced this day, and why in words. A day that
    # says "no running" without saying which race it is paying for reads as the plan
    # having lost its place rather than as a decision.
    mode: str = "build"
    mode_reason: str = ""
    # Set on race days only, so a calendar with three races on it can say which.
    race_name: str = ""


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


@dataclass(frozen=True)
class _Targets:
    """The athlete's standing bands, resolved once per session.

    Every mode needs the same six numbers and the two labels built from them, and
    the previous version rebuilt them inline in each branch — which is how a walk
    day ended up with a running heart rate on it.
    """

    pace_label: str
    pace_min: int
    pace_max: int
    hr_label: str
    hr_min: int
    hr_max: int
    walk_pace_label: str = "9:00–11:00/km"
    walk_pace_min: int = 540
    walk_pace_max: int = 660
    # The pace the walk session's own 2.5 km / 28 min implies.
    walk_min_per_km: float = 11.2

    @property
    def walk_hr_label(self) -> str:
        return f"{self.walk_hr_min}–{self.walk_hr_max} bpm"

    @property
    def walk_hr_min(self) -> int:
        return max(self.hr_min - 20, 90)

    @property
    def walk_hr_max(self) -> int:
        return self.hr_min


def _targets(athlete) -> _Targets:
    if athlete is None:
        return _Targets("10:00–10:45/km", 600, 645, "130–145 bpm", 130, 145)
    return _Targets(
        _pace_label(athlete), athlete.easy_pace_min, athlete.easy_pace_max,
        f"{athlete.hr_easy_min}–{athlete.hr_easy_max} bpm",
        athlete.hr_easy_min, athlete.hr_easy_max,
    )


def _day_type(athlete, on: dt.date) -> str:
    return athlete.day_type(on.weekday()) if athlete else DEFAULT_WEEK[on.weekday()]


# ------------------------------------------------------------------ entry points


def session_in(sched: Schedule, on: dt.date, athlete=None) -> Optional[PlannedSession]:
    """The prescribed session for one date, given the athlete's whole race calendar.

    Returns None only when there are no races at all — with nothing on the calendar
    there is no plan to be off, and inventing one would be the system asserting a
    goal the athlete never set.
    """
    if not sched:
        return None
    return session_for_context(sched.context(on), athlete)


def session_for(race_date: dt.date, on: dt.date, athlete=None) -> PlannedSession:
    """The prescribed session for one date against a single race.

    The pre-multi-race entry point, kept for previews and for tests that have no
    athlete and no database. Note that it now recovers from its one race and then
    holds, rather than prescribing race week forever the way a clamped negative
    `weeks_out` used to.
    """
    return session_for_context(Schedule.single(race_date).context(on), athlete)


def session_for_context(ctx: DayContext, athlete=None) -> PlannedSession:
    """One resolved day, turned into a prescription. One branch per mode."""
    targets = _targets(athlete)
    if ctx.mode == "race":
        return _race_session(ctx, athlete, targets)
    if ctx.mode == "recovery":
        return _recovery_session(ctx, athlete, targets)
    if ctx.mode == "mini_taper":
        return _taper_session(ctx, athlete, targets)
    if ctx.mode in ("maintenance", "off_season"):
        return _from_row(
            MAINTENANCE, ctx, athlete, targets,
            plan_week=None,
            phase="Maintenance" if ctx.mode == "maintenance" else "Off-season",
        )
    return _build_session(ctx, athlete, targets)


def upcoming_in(sched: Schedule, start: dt.date, days: int = 7,
                athlete=None) -> list[PlannedSession]:
    out = [session_in(sched, start + dt.timedelta(days=i), athlete) for i in range(days)]
    return [s for s in out if s is not None]


def upcoming(race_date: dt.date, start: dt.date, days: int = 7,
             athlete=None) -> list[PlannedSession]:
    return upcoming_in(Schedule.single(race_date), start, days, athlete)


# ------------------------------------------------------------------ build mode


def _build_session(ctx: DayContext, athlete, targets: _Targets) -> PlannedSession:
    """The ordinary ramp: the week table, indexed by weeks remaining."""
    weeks_out = ctx.weeks_out
    # Before the plan proper starts, hold at week 1 rather than inventing volume.
    key = min(max(weeks_out, 0), 16)
    return _from_row(
        WEEKS[key], ctx, athlete, targets,
        plan_week=17 - key, phase=_phase_for(key),
        before_plan=(ctx.anchor.date - ctx.date).days // 7 > 16,
    )


def _from_row(row: Row, ctx: DayContext, athlete, targets: _Targets, *,
              plan_week: Optional[int], phase: str,
              before_plan: bool = False) -> PlannedSession:
    """One week's numbers, laid out across the athlete's own training days.

    Shared by every mode that prescribes a normal week — the ramp and the
    maintenance hold — so the two can never drift apart in how they read a
    `training_days` map or how they split a session into run and walk minutes.
    """
    reps, run_m, walk_m, long_km, note = row
    on = ctx.date

    base = dict(
        date=on, plan_week=plan_week, weeks_out=ctx.weeks_out, phase=phase, note=note,
        target_pace=targets.pace_label, target_hr=targets.hr_label,
        target_pace_min_s=targets.pace_min, target_pace_max_s=targets.pace_max,
        target_hr_min=targets.hr_min, target_hr_max=targets.hr_max,
        before_plan=before_plan, mode=ctx.mode, mode_reason=ctx.reason,
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
    day_type = _day_type(athlete, on)

    if day_type == "long":
        total = round(long_km * MIN_PER_KM)
        return PlannedSession(
            kind="long", title=f"Long run — {long_km:g} km",
            detail=(
                f"Run/walk the whole way at {targets.pace_label}. This is the session "
                "that actually builds the distance; treat the midweek work as support "
                "for it."
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
        total = round(jog_km * MIN_PER_KM)
        return PlannedSession(
            kind="jog", title=f"Easy jog — {jog_km:g} km",
            detail=(
                f"Run/walk at {targets.pace_label}, whatever mix feels sustainable. "
                "This is volume at low cost — it should feel easier than your interval "
                "days."
            ),
            distance_km=jog_km, focus="Easy volume",
            run_minutes=round(total * run_share, 1),
            walk_minutes=round(total * (1 - run_share), 1),
            total_minutes=total, **base,
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
            target_pace=targets.walk_pace_label,
            target_pace_min_s=targets.walk_pace_min,
            target_pace_max_s=targets.walk_pace_max,
            target_hr=targets.walk_hr_label,
            target_hr_min=targets.walk_hr_min, target_hr_max=targets.walk_hr_max,
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
            detail = (
                f"Continuous easy running at {targets.pace_label}. Walk if HR crosses "
                "your ceiling."
            )
        else:
            title = f"{reps} × ({_fmt(run_m)} run / {_fmt(walk_m)} walk)"
            detail = (
                f"5 min walk warm-up, then {reps} rounds, then 5 min walk cool-down. "
                f"Run blocks at {targets.pace_label} — keep your cadence and shorten "
                "your stride."
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
    return _rest(base, targets, PACE_KEYS + HR_KEYS)


def _rest(base: dict, targets: _Targets, drop: tuple, *,
          minutes: float = 25.0, title: str = "Rest or easy walk",
          detail: str = (
              "No running today. A walk, cycle or swim is fine — adaptation happens "
              "on the days you don't run. If you do walk, 20–30 minutes easy is plenty."
          ),
          focus: str = "Recover") -> PlannedSession:
    """A rest day with the numbers behind its optional walk."""
    return PlannedSession(
        kind="rest", title=title, detail=detail, focus=focus, optional=bool(minutes),
        walk_minutes=minutes, total_minutes=minutes,
        distance_km=round(minutes / targets.walk_min_per_km, 1) if minutes else 0.0,
        **{k: v for k, v in base.items() if k not in drop},
        target_pace=targets.walk_pace_label if minutes else "",
        target_pace_min_s=targets.walk_pace_min if minutes else 0,
        target_pace_max_s=targets.walk_pace_max if minutes else 0,
        target_hr=targets.walk_hr_label if minutes else "",
        target_hr_min=targets.walk_hr_min if minutes else 0,
        target_hr_max=targets.walk_hr_max if minutes else 0,
    )


# ------------------------------------------------------------------ race day


def _race_session(ctx: DayContext, athlete, targets: _Targets) -> PlannedSession:
    """Race day, for whichever race this is.

    The distance comes from the race rather than from the week table's long-run
    column: with more than one race on the calendar those are no longer the same
    number, and a 5K in October would otherwise have been prescribed as 10 km.
    """
    race = ctx.race
    km = race.distance_km
    total = round(km * MIN_PER_KM)
    detail = (
        "Start at the back. Run the first kilometre at least 30 s slower than "
        "training pace. Hold your run/walk pattern from kilometre one rather than "
        "running until you have to stop. Walk every water station."
    )
    if not race.is_target:
        # A B-race run as if it were the A-race costs the block it sits inside. The
        # honest framing is a hard training day with a number on the end of it.
        detail += (
            " This is not your target race. Run it as the hard day it is — the "
            "weeks after it still have to happen, and racing it flat out buys a "
            "result today at the cost of the block it sits inside."
        )
    return PlannedSession(
        kind="race", title=f"Race day — {race.label or f'{km:g} km'}",
        detail=detail,
        distance_km=km, focus="Finish", total_minutes=total,
        # Race day is still run/walk at this stage, so its minutes split like any
        # other session rather than being recorded as pure running.
        run_minutes=round(total * 0.75, 1), walk_minutes=round(total * 0.25, 1),
        date=ctx.date, plan_week=None, weeks_out=ctx.weeks_out, phase="Taper & race",
        note="race", mode=ctx.mode, mode_reason=ctx.reason, race_name=race.name,
        target_pace=targets.pace_label, target_hr=targets.hr_label,
        target_pace_min_s=targets.pace_min, target_pace_max_s=targets.pace_max,
        target_hr_min=targets.hr_min, target_hr_max=targets.hr_max,
    )


# ------------------------------------------------------------------ recovery


def _recovery_session(ctx: DayContext, athlete, targets: _Targets) -> PlannedSession:
    """The days a race is repaid in.

    Three stages, scaled to the distance raced: complete rest, then walking, then
    short easy jogs. The athlete's own rest days stay rest throughout — recovery
    never adds a session to a week, it only ever replaces one with something
    smaller.
    """
    race = ctx.last_race
    owed = race.recovery_days
    since = ctx.days_since_race
    label = race.name or race.label or f"{race.distance_km:g} km"

    # Quarter of the window off entirely, then walking to a little over half, then
    # jogging. `round` keeps the short windows sane: a 5K's three days come out as
    # one off, one walking, one jogging.
    rest_until = max(1, round(owed * 0.25))
    walk_until = max(rest_until + 1, round(owed * 0.6))

    base = dict(
        date=ctx.date, plan_week=None, weeks_out=ctx.weeks_out, phase="Recovery",
        note="", mode=ctx.mode, mode_reason=ctx.reason,
        target_pace=targets.pace_label, target_hr=targets.hr_label,
        target_pace_min_s=targets.pace_min, target_pace_max_s=targets.pace_max,
        target_hr_min=targets.hr_min, target_hr_max=targets.hr_max,
    )
    PACE_KEYS = ("target_pace", "target_pace_min_s", "target_pace_max_s")
    HR_KEYS = ("target_hr", "target_hr_min", "target_hr_max")
    walk_targets = {
        "target_pace": targets.walk_pace_label,
        "target_pace_min_s": targets.walk_pace_min,
        "target_pace_max_s": targets.walk_pace_max,
        "target_hr": targets.walk_hr_label,
        "target_hr_min": targets.walk_hr_min,
        "target_hr_max": targets.walk_hr_max,
    }
    stripped = {k: v for k, v in base.items() if k not in PACE_KEYS + HR_KEYS}

    if since <= rest_until:
        # Day one is genuinely nothing. A "gentle shakeout" the day after a first
        # race is a thing experienced runners do and a thing beginners get hurt on.
        minutes = 0.0 if since == 1 else 20.0
        return _rest(
            base, targets, PACE_KEYS + HR_KEYS, minutes=minutes,
            title="Complete rest" if minutes == 0 else "Rest — gentle walk if you want one",
            detail=(
                f"You raced {label} {since} day{'s' if since != 1 else ''} ago. "
                + ("Nothing today: no running, no walking it off, no gym. The soreness "
                   "you can feel is the part that heals fastest; the tendon and muscle "
                   "damage you cannot feel is why this day exists."
                   if minutes == 0 else
                   f"Still no running. Twenty easy minutes on your feet helps the "
                   f"legs clear, and stopping short of that costs nothing.")
            ),
            focus="Repay the race",
        )

    day_type = _day_type(athlete, ctx.date)
    if day_type == "rest":
        # A rest day stays a rest day. Recovery never adds a session to a week; it
        # only ever replaces one with something smaller.
        return _rest(base, targets, PACE_KEYS + HR_KEYS, focus="Repay the race")

    if since <= walk_until or day_type == "walk":
        return PlannedSession(
            kind="walk", title="Easy walk — 25–30 min",
            detail=(
                f"Day {since} of {owed} after {label}. Walking, not running: it keeps "
                "the blood moving through legs that are still repairing without "
                "asking them to absorb impact again."
            ),
            focus="Repay the race", total_minutes=28, walk_minutes=28, distance_km=2.5,
            **stripped, **walk_targets,
        )

    # The last stretch: short and easy, and short on purpose. Coming back at the
    # volume you left at is the classic way a good race becomes a six-week injury.
    jog_km = round(min(4.0, max(2.0, race.distance_km * 0.35)), 1)
    total = round(jog_km * MIN_PER_KM)
    return PlannedSession(
        kind="jog", title=f"Easy jog — {jog_km:g} km",
        detail=(
            f"Day {since} of {owed} after {label}. Run/walk at {targets.pace_label} "
            f"and stop at {jog_km:g} km even if it feels easy — it should feel easy, "
            "that is what tells you the recovery worked. Full training resumes on day "
            f"{owed + 1}."
        ),
        distance_km=jog_km, focus="Ease back in",
        run_minutes=round(total * 0.6, 1), walk_minutes=round(total * 0.4, 1),
        total_minutes=total, **base,
    )


# ------------------------------------------------------------------ mini-taper


def _taper_session(ctx: DayContext, athlete, targets: _Targets) -> PlannedSession:
    """The last few days before a race the 17-week table is not tapering for.

    Every B-race gets this, and so does the target when the plan is holding rather
    than counting the table down to it. The table's own taper is two weeks long,
    which is right for the race a block was built for and far too expensive for a
    race that sits inside one.
    """
    race = ctx.next_race
    to_go = ctx.days_to_race
    label = race.name or race.label or f"{race.distance_km:g} km"

    base = dict(
        date=ctx.date, plan_week=None, weeks_out=ctx.weeks_out, phase="Taper & race",
        note="", mode=ctx.mode, mode_reason=ctx.reason,
        target_pace=targets.pace_label, target_hr=targets.hr_label,
        target_pace_min_s=targets.pace_min, target_pace_max_s=targets.pace_max,
        target_hr_min=targets.hr_min, target_hr_max=targets.hr_max,
    )
    PACE_KEYS = ("target_pace", "target_pace_min_s", "target_pace_max_s")
    HR_KEYS = ("target_hr", "target_hr_min", "target_hr_max")

    if to_go == 1:
        return _rest(
            base, targets, PACE_KEYS + HR_KEYS, minutes=0.0,
            title="Rest — race tomorrow",
            detail=(
                f"{label} is tomorrow. Nothing you do today makes you fitter for it, "
                "and plenty could make you slower. Stay off your feet, eat what you "
                "always eat, and lay your kit out tonight."
            ),
            focus="Arrive fresh",
        )

    if _day_type(athlete, ctx.date) in ("rest", "walk", "cross"):
        return _rest(
            base, targets, PACE_KEYS + HR_KEYS,
            title="Rest or easy walk",
            detail=(
                f"{to_go} days to {label}. A walk is fine; anything that leaves you "
                "tired is not. This is a week for banking sleep rather than sessions."
            ),
            focus="Arrive fresh",
        )

    # One short, easy run keeps the legs used to running without costing anything.
    # Roughly a third of race distance is the standard shape of a taper run.
    jog_km = round(max(2.0, race.distance_km * 0.3), 1)
    total = round(jog_km * MIN_PER_KM)
    return PlannedSession(
        kind="jog", title=f"Easy jog — {jog_km:g} km",
        detail=(
            f"{to_go} days to {label}. Short and easy at {targets.pace_label}, with "
            "your race-day run/walk pattern rather than a continuous run — rehearse "
            f"what you are going to do on the day. Stop at {jog_km:g} km."
        ),
        distance_km=jog_km, focus="Stay sharp, stay fresh",
        run_minutes=round(total * 0.6, 1), walk_minutes=round(total * 0.4, 1),
        total_minutes=total, **base,
    )
