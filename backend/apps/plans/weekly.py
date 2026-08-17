"""Week-level review: planned against actual, and one verdict.

The app judges individual sessions well and trends individual metrics well, but the
decision that actually protects December is a weekly one — hold, repeat, or progress.
Without it the plan advances on the calendar whether or not the work happened, which
is the quiet way a 17-week block ends up two weeks of fitness short of its own
schedule.

The verdict is deliberately conservative. Repeating a week costs one week; arriving
at the start line underprepared costs the race.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Optional

from .template import session_for

RUN_SPORTS = {"running", "trail_running", "treadmill_running", "track_running", "virtual_run"}

# Fraction of the week's prescribed sessions that must be completed to progress.
PROGRESS_THRESHOLD = 0.75
REPEAT_THRESHOLD = 0.4


@dataclass
class WeekReview:
    start: dt.date
    end: dt.date
    plan_week: Optional[int]
    phase: str
    planned_sessions: int = 0
    completed_sessions: int = 0
    planned_run_minutes: float = 0.0
    actual_run_minutes: float = 0.0
    planned_distance_km: float = 0.0
    actual_distance_km: float = 0.0
    longest_run_s: float = 0.0
    previous_longest_run_s: float = 0.0
    pace_discipline_pct: Optional[float] = None
    avg_sleep_h: Optional[float] = None
    sleep_debt_h: Optional[float] = None
    niggles: list = field(default_factory=list)
    off_plan_days: list = field(default_factory=list)
    missed_days: list = field(default_factory=list)
    verdict: str = "progress"
    verdict_reason: str = ""
    days: list = field(default_factory=list)
    in_progress: bool = False
    before_plan: bool = False


def week_bounds(any_date: dt.date) -> tuple[dt.date, dt.date]:
    """Monday-to-Sunday containing the given date."""
    start = any_date - dt.timedelta(days=any_date.weekday())
    return start, start + dt.timedelta(days=6)


def review(athlete, any_date: dt.date, race=None) -> WeekReview:
    from apps.activities.models import Activity
    from apps.journal.models import DailyLog
    from apps.journal.wellness import DailyMetrics

    start, end = week_bounds(any_date)
    prev_start = start - dt.timedelta(days=7)

    activities = list(
        Activity.objects.filter(athlete=athlete, local_date__gte=start, local_date__lte=end)
        .select_related("metrics")
    )
    runs = [a for a in activities if a.sport in RUN_SPORTS]
    previous_runs = list(
        Activity.objects.filter(
            athlete=athlete, sport__in=RUN_SPORTS,
            local_date__gte=prev_start, local_date__lt=start,
        ).select_related("metrics")
    )

    sessions = []
    if race:
        cursor = start
        while cursor <= end:
            sessions.append(session_for(race.race_date, cursor, athlete))
            cursor += dt.timedelta(days=1)

    # A week entirely before the plan's start gets no prescription and no verdict.
    # The clamped template would otherwise report every earlier week as "week 1 of 17"
    # and then mark it failed for missing sessions that were never set.
    before_plan = bool(sessions) and all(s.before_plan for s in sessions)

    prescribed = [] if before_plan else [
        s for s in sessions if s.kind in ("intervals", "long", "jog", "race")
    ]
    plan_week = None if before_plan else (
        prescribed[0].plan_week if prescribed
        else (sessions[0].plan_week if sessions else None)
    )
    phase = "Before the plan" if before_plan else (
        prescribed[0].phase if prescribed else (sessions[0].phase if sessions else "")
    )

    result = WeekReview(start=start, end=end, plan_week=plan_week, phase=phase)
    result.before_plan = before_plan
    result.planned_sessions = len(prescribed)
    result.planned_run_minutes = sum(s.run_minutes for s in prescribed)
    result.planned_distance_km = sum(s.distance_km for s in prescribed)

    run_dates = {a.local_date for a in runs}
    prescribed_dates = {s.date for s in prescribed}

    # Count the work, not the calendar slot. Someone who runs three times on days that
    # suit them has done the week; matching prescribed dates exactly would have called
    # a Monday run "0 of 3" purely because Monday is written as rest.
    result.completed_sessions = min(len(run_dates), result.planned_sessions)
    result.off_plan_days = sorted(d for d in run_dates if d not in prescribed_dates)
    result.missed_days = sorted(d for d in prescribed_dates if d not in run_dates)
    result.actual_distance_km = round(sum(a.total_distance_m for a in runs) / 1000, 2)
    result.actual_run_minutes = round(
        sum(a.metrics.run_time_s for a in runs if hasattr(a, "metrics")) / 60, 1
    )

    longest = [a.metrics.longest_run_s for a in runs if hasattr(a, "metrics")]
    result.longest_run_s = max(longest) if longest else 0.0
    prev_longest = [a.metrics.longest_run_s for a in previous_runs if hasattr(a, "metrics")]
    result.previous_longest_run_s = max(prev_longest) if prev_longest else 0.0

    disciplines = [
        a.metrics.pace_discipline_pct for a in runs
        if hasattr(a, "metrics") and a.metrics.pace_discipline_pct is not None
    ]
    if disciplines:
        result.pace_discipline_pct = round(sum(disciplines) / len(disciplines), 1)

    metrics = list(DailyMetrics.objects.filter(
        athlete=athlete, metric_date__gte=start, metric_date__lte=end))
    sleeps = [m.sleep_hours for m in metrics if m.sleep_hours]
    if sleeps:
        result.avg_sleep_h = round(sum(sleeps) / len(sleeps), 1)
    deficits = [m.sleep_deficit_hours for m in metrics if m.sleep_deficit_hours is not None]
    if deficits:
        result.sleep_debt_h = round(sum(d for d in deficits if d > 0), 1)

    result.niggles = sorted({
        log.pain_area for log in DailyLog.objects.filter(
            athlete=athlete, log_date__gte=start, log_date__lte=end)
        if log.pain_area
    })

    result.days = [{
        "date": s.date,
        "planned": "—" if before_plan else s.title,
        "kind": s.kind,
        "done": s.date in run_dates,
        "prescribed": (not before_plan) and s.kind in ("intervals", "long", "jog", "race"),
    } for s in sessions]

    # A week still in progress cannot be judged on sessions not yet due.
    result.in_progress = end >= athlete.local_today

    _decide(result)
    return result


def _decide(week: WeekReview) -> None:
    """Hold, repeat or progress. Conservative on purpose."""
    if week.before_plan:
        week.verdict = "before_plan"
        week.verdict_reason = (
            "This week is before your plan started, so there was nothing prescribed. "
            "Shown for context only."
        )
        return

    if week.in_progress:
        remaining = week.planned_sessions - week.completed_sessions
        week.verdict = "in_progress"
        week.verdict_reason = (
            f"{week.completed_sessions} of {week.planned_sessions} sessions so far, "
            f"{max(remaining, 0)} still to come this week."
        )
        return

    if week.planned_sessions == 0:
        week.verdict = "none"
        week.verdict_reason = "No sessions were prescribed for this week."
        return

    ratio = week.completed_sessions / week.planned_sessions
    missed = week.planned_sessions - week.completed_sessions

    if week.niggles:
        week.verdict = "repeat"
        week.verdict_reason = (
            f"You reported {', '.join(n.replace('_', ' ') for n in week.niggles)} pain this "
            "week. Repeat rather than progress — adding load onto a niggle is how it "
            "becomes an injury."
        )
        return

    if ratio < REPEAT_THRESHOLD:
        week.verdict = "repeat"
        week.verdict_reason = (
            f"Only {week.completed_sessions} of {week.planned_sessions} sessions happened. "
            "Repeat this week rather than moving on — the next one assumes this one was done."
        )
        return

    if ratio < PROGRESS_THRESHOLD:
        week.verdict = "hold"
        week.verdict_reason = (
            f"{week.completed_sessions} of {week.planned_sessions} sessions done, {missed} "
            "missed. Hold at this level for another week rather than stepping up."
        )
        return

    if week.pace_discipline_pct is not None and week.pace_discipline_pct < 25:
        week.verdict = "hold"
        week.verdict_reason = (
            f"You completed the work, but only {week.pace_discipline_pct:.0f}% of your "
            "running was inside the easy band. Hold here and fix the pacing before "
            "adding distance — that is what lets the run blocks lengthen."
        )
        return

    week.verdict = "progress"
    grew = week.longest_run_s > week.previous_longest_run_s
    week.verdict_reason = (
        f"{week.completed_sessions} of {week.planned_sessions} sessions done"
        + (", and your longest unbroken run grew." if grew else ".")
        + " Move on to next week as written."
    )


def recent(athlete, race=None, weeks: int = 6) -> list[WeekReview]:
    today = athlete.local_today
    out = []
    for offset in range(weeks):
        out.append(review(athlete, today - dt.timedelta(days=7 * offset), race))
    return out
