"""Achievement definitions.

Two rules shape everything here.

**Every achievement marks something real.** No "you opened the app" awards. Each one
is a threshold in the athlete's own data that genuinely was not true before and is
now, and the number that earned it is stored alongside so the claim can be checked.

**Locked achievements show honest progress.** "4:51 of 10:00" tells you where you
actually are; a padlock tells you nothing. Progress is capped at 99% until earned, so
a bar never sits full on something you have not done.

Thresholds are pitched at a beginner working toward a first 10K. Running 20 minutes
unbroken is genuinely hard from a standing start, and pretending otherwise would make
the whole set meaningless.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Callable, Optional

RUN_SPORTS = {"running", "trail_running", "treadmill_running", "track_running", "virtual_run"}


@dataclass
class Context:
    """Everything the definitions need, gathered once."""
    runs: list          # Activity, oldest first, running sports only, metrics attached
    all_activities: list
    wellness: list
    log_count: int


@dataclass
class Definition:
    key: str
    name: str
    description: str
    group: str
    unit: str
    target: float
    # Returns (best value so far, date it first crossed target or None).
    evaluate: Callable[[Context], tuple[float, Optional[dt.date], object]]
    format: str = "number"   # number | duration | distance | percent


def _first_crossing(runs, value_of, target) -> tuple[float, Optional[dt.date], object]:
    """Best value across all runs, and the first run that met the target."""
    best = 0.0
    earned_on = None
    earned_by = None
    for activity in runs:
        value = value_of(activity) or 0.0
        if value > best:
            best = value
        if earned_on is None and value >= target:
            earned_on = activity.local_date
            earned_by = activity
    return best, earned_on, earned_by


def _longest_run_s(activity):
    metrics = getattr(activity, "metrics", None)
    return metrics.longest_run_s if metrics else 0


def _run_distance(activity):
    metrics = getattr(activity, "metrics", None)
    return metrics.run_distance_m if metrics else 0


def _cumulative(runs, target) -> tuple[float, Optional[dt.date], object]:
    """Running total of distance, and the day it passed the target."""
    total = 0.0
    earned_on = None
    earned_by = None
    for activity in runs:
        total += activity.total_distance_m or 0
        if earned_on is None and total >= target:
            earned_on = activity.local_date
            earned_by = activity
    return total, earned_on, earned_by


def _runs_in_window(runs, days: int, count: int) -> tuple[float, Optional[dt.date], object]:
    """Most runs inside any rolling window, and when that count was first reached."""
    dates = [a.local_date for a in runs]
    best = 0
    earned_on = None
    earned_by = None
    for i, activity in enumerate(runs):
        window_start = dates[i] - dt.timedelta(days=days - 1)
        in_window = sum(1 for d in dates[: i + 1] if d >= window_start)
        if in_window > best:
            best = in_window
        if earned_on is None and in_window >= count:
            earned_on = activity.local_date
            earned_by = activity
    return float(best), earned_on, earned_by


def _consecutive_weeks(runs, target_weeks: int) -> tuple[float, Optional[dt.date], object]:
    """Longest streak of consecutive ISO weeks containing at least one run."""
    if not runs:
        return 0.0, None, None
    weeks = sorted({(a.local_date.isocalendar()[0], a.local_date.isocalendar()[1]) for a in runs})
    by_week = {}
    for a in runs:
        by_week.setdefault((a.local_date.isocalendar()[0], a.local_date.isocalendar()[1]), a)

    best = streak = 1
    earned_on = None
    earned_by = None
    if target_weeks <= 1:
        earned_on, earned_by = runs[0].local_date, runs[0]

    for i in range(1, len(weeks)):
        prev_year, prev_week = weeks[i - 1]
        year, week = weeks[i]
        # Compare by actual date so a year boundary does not break the streak.
        prev_monday = dt.date.fromisocalendar(prev_year, prev_week, 1)
        monday = dt.date.fromisocalendar(year, week, 1)
        streak = streak + 1 if (monday - prev_monday).days == 7 else 1
        best = max(best, streak)
        if earned_on is None and streak >= target_weeks:
            marker = by_week[weeks[i]]
            earned_on, earned_by = marker.local_date, marker
    return float(best), earned_on, earned_by


def _best_metric(runs, attr, target, higher_is_better=True):
    def value_of(activity):
        metrics = getattr(activity, "metrics", None)
        value = getattr(metrics, attr, None) if metrics else None
        return value if value is not None else (0 if higher_is_better else 10_000)
    if higher_is_better:
        return _first_crossing(runs, value_of, target)
    best = None
    earned_on = None
    earned_by = None
    for activity in runs:
        value = value_of(activity)
        if best is None or value < best:
            best = value
        if earned_on is None and value <= target:
            earned_on, earned_by = activity.local_date, activity
    return (best or 0.0), earned_on, earned_by


CATALOG: list[Definition] = [
    # ---- the progression that actually matters for a first 10K ----
    Definition("run_5min", "Five unbroken minutes", "Run for 5 minutes without walking.",
               "Unbroken running", "min", 300,
               lambda c: _first_crossing(c.runs, _longest_run_s, 300), "duration"),
    Definition("run_10min", "Ten unbroken minutes", "Run for 10 minutes without walking.",
               "Unbroken running", "min", 600,
               lambda c: _first_crossing(c.runs, _longest_run_s, 600), "duration"),
    Definition("run_20min", "Twenty unbroken minutes",
               "Run for 20 minutes without walking. The hardest step on this plan.",
               "Unbroken running", "min", 1200,
               lambda c: _first_crossing(c.runs, _longest_run_s, 1200), "duration"),
    Definition("run_30min", "Half an hour, no walking", "Run for 30 minutes without stopping.",
               "Unbroken running", "min", 1800,
               lambda c: _first_crossing(c.runs, _longest_run_s, 1800), "duration"),

    # ---- session distance ----
    Definition("session_3k", "Three kilometres", "Cover 3 km of running in one session.",
               "Distance", "km", 3000,
               lambda c: _first_crossing(c.runs, _run_distance, 3000), "distance"),
    Definition("session_5k", "Five kilometres", "Cover 5 km of running in one session.",
               "Distance", "km", 5000,
               lambda c: _first_crossing(c.runs, _run_distance, 5000), "distance"),
    Definition("session_8k", "Eight kilometres", "Cover 8 km of running in one session.",
               "Distance", "km", 8000,
               lambda c: _first_crossing(c.runs, _run_distance, 8000), "distance"),
    Definition("session_10k", "Ten kilometres", "The distance. Cover 10 km of running in one session.",
               "Distance", "km", 10000,
               lambda c: _first_crossing(c.runs, _run_distance, 10000), "distance"),

    # ---- cumulative ----
    Definition("total_25k", "25 km logged", "Run 25 km in total.",
               "Mileage", "km", 25000, lambda c: _cumulative(c.runs, 25000), "distance"),
    Definition("total_50k", "50 km logged", "Run 50 km in total.",
               "Mileage", "km", 50000, lambda c: _cumulative(c.runs, 50000), "distance"),
    Definition("total_100k", "100 km logged", "Run 100 km in total.",
               "Mileage", "km", 100000, lambda c: _cumulative(c.runs, 100000), "distance"),

    # ---- consistency: the strongest predictor of finishing ----
    Definition("week_3_runs", "Three runs in a week",
               "Run three times inside seven days — what the plan asks for every week.",
               "Consistency", "runs", 3, lambda c: _runs_in_window(c.runs, 7, 3)),
    Definition("streak_4_weeks", "Four weeks running",
               "Run at least once a week for four consecutive weeks.",
               "Consistency", "weeks", 4, lambda c: _consecutive_weeks(c.runs, 4)),
    Definition("streak_8_weeks", "Eight weeks running",
               "Run at least once a week for eight consecutive weeks.",
               "Consistency", "weeks", 8, lambda c: _consecutive_weeks(c.runs, 8)),

    # ---- craft: doing it the right way, not just doing it ----
    Definition("discipline_60", "Ran it easy",
               "Spend 60% of a session's running time inside your easy pace band.",
               "Craft", "%", 60,
               lambda c: _best_metric(c.runs, "pace_discipline_pct", 60), "percent"),
    Definition("no_overshoot", "Under control",
               "Finish a session with heart rate not climbing after you stop — the sign the "
               "effort stayed inside your aerobic capacity.",
               "Craft", "bpm", 0,
               lambda c: _best_metric(c.runs, "avg_hr_overshoot_bpm", 0, higher_is_better=False)),
    Definition("recovery_25", "Strong recovery",
               "Drop 25 bpm in the first minute of a walk break.",
               "Craft", "bpm", 25,
               lambda c: _best_metric(c.runs, "avg_hr_recovery_60s", 25)),
]


def build_context(athlete) -> Context:
    from apps.activities.models import Activity
    from apps.journal.models import DailyLog
    from apps.journal.wellness import DailyMetrics

    activities = list(
        Activity.objects.filter(athlete=athlete)
        .select_related("metrics")
        .order_by("started_at")
    )
    return Context(
        runs=[a for a in activities if a.sport in RUN_SPORTS],
        all_activities=activities,
        wellness=list(DailyMetrics.objects.filter(athlete=athlete).order_by("metric_date")),
        log_count=DailyLog.objects.filter(athlete=athlete).count(),
    )
