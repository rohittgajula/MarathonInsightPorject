"""Daily-log readiness adjustment.

This is what makes the log matter: what you record tonight changes what tomorrow's
session asks of you.

Deliberately separate from the correlation analysis in `insights.py`, and it is worth
being clear why the sample-size gate does not apply here. Saying "alcohol costs you
4% of your pace" is a statistical claim about a population of your runs, and needs
many observations before it means anything. Saying "you slept five hours, so run
easier tomorrow" is a same-day readiness rule — standard training practice, and true
of the single night in question regardless of how many nights came before it.

Rules only ever make a session easier, never harder. An automated system should not
be able to talk someone into more training than the plan asked for.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional

SHORT_SLEEP_H = 6.0
VERY_SHORT_SLEEP_H = 5.0
ALCOHOL_UNITS = 2.0

TIRED_WORDS = {"tired", "sore", "unwell"}


# Below these the day is not "a bit compromised" — it is a day to not train.
CRITICAL_READINESS = 20
CRITICAL_SLEEP_H = 4.5


@dataclass
class Adjustment:
    applied: bool
    reason: str = ""
    downgrade_to_rest: bool = False
    # "caution" | "critical". Drives how loudly the UI says it.
    severity: str = "caution"


# Garmin's readiness score is 0-100. Below this the watch itself is saying rest.
LOW_READINESS = 35
POOR_SLEEP_SCORE = 50
# Acute:chronic load above this is the standard ramping-too-fast flag.
HIGH_LOAD_RATIO = 1.5


def evaluate(log, metrics=None) -> Adjustment:
    """Decide whether the next session should be eased.

    Measured data wins over self-reported text when both exist: Garmin knows the
    athlete slept 5h26m and scored it against their personal sleep need, whereas the
    log only knows what they thought to type. The text log still carries what the
    watch cannot see — alcohol, and how they actually feel.
    """
    reasons: list[str] = []
    to_rest = False

    measured_sleep = None
    if metrics is not None:
        measured_sleep = metrics.sleep_hours

        if metrics.training_readiness is not None and metrics.training_readiness < LOW_READINESS:
            reasons.append(f"Garmin puts your training readiness at {metrics.training_readiness}/100")
            to_rest = True

        deficit = metrics.sleep_deficit_hours
        if deficit is not None and deficit >= 1.5:
            reasons.append(f"you slept {deficit:g} h less than your body needed")

        if metrics.sleep_score is not None and metrics.sleep_score < POOR_SLEEP_SCORE:
            reasons.append(f"a sleep score of {metrics.sleep_score}")

        ratio = metrics.load_ratio
        if ratio is not None and ratio > HIGH_LOAD_RATIO:
            reasons.append(f"your training load ratio is {ratio} — ramping faster than you are absorbing")

        if measured_sleep is not None:
            if measured_sleep < VERY_SHORT_SLEEP_H:
                reasons.append(f"your watch recorded {measured_sleep:g} h of sleep")
                to_rest = True
            elif measured_sleep < SHORT_SLEEP_H:
                reasons.append(f"your watch recorded {measured_sleep:g} h of sleep")

    critical = _is_critical(metrics, None)

    if log is None:
        if not reasons:
            return Adjustment(False)
        joined = reasons[0] if len(reasons) == 1 else ", ".join(reasons[:-1]) + " and " + reasons[-1]
        return Adjustment(True, joined, to_rest, "critical" if critical else "caution")

    # Only fall back to the typed sleep figure when the watch did not measure one.
    if measured_sleep is None and log.sleep_hours is not None:
        if log.sleep_hours < VERY_SHORT_SLEEP_H:
            reasons.append(f"you logged {log.sleep_hours:g} h of sleep")
            to_rest = True
        elif log.sleep_hours < SHORT_SLEEP_H:
            reasons.append(f"you logged {log.sleep_hours:g} h of sleep")

    if log.alcohol_units:
        reasons.append(
            f"{log.alcohol_units:g} units of alcohol"
            if log.alcohol_units != 1
            else "a drink"
        )

    if log.felt in TIRED_WORDS:
        reasons.append(f"you felt {log.felt}")

    # Pain and illness are stop signals rather than scale-back signals. Running
    # through a niggle is how a two-day problem becomes a six-week one, and the plan
    # has enough buffer to lose a fortnight and still make the start line.
    quality = getattr(log, "sleep_quality", "")
    if measured_sleep is None and log.sleep_hours is None and quality in ("short", "poor"):
        reasons.append(
            "you described a short night" if quality == "short" else "you slept badly"
        )

    if getattr(log, "pain_area", ""):
        area = log.pain_area.replace("_", " ")
        reasons.append(f"you reported {area} pain")
        to_rest = True
    if getattr(log, "illness", False):
        reasons.append("you logged feeling unwell")
        to_rest = True

    if not reasons:
        return Adjustment(False)

    critical = _is_critical(metrics, log)
    joined = reasons[0] if len(reasons) == 1 else ", ".join(reasons[:-1]) + " and " + reasons[-1]
    return Adjustment(True, joined, to_rest, "critical" if critical else "caution")


def _is_critical(metrics, log) -> bool:
    """Severe enough that the honest advice is 'do not train today'."""
    if metrics is not None:
        if metrics.training_readiness is not None and metrics.training_readiness < CRITICAL_READINESS:
            return True
        if metrics.sleep_hours is not None and metrics.sleep_hours < CRITICAL_SLEEP_H:
            return True
    if log is not None:
        if getattr(log, "pain_area", "") or getattr(log, "illness", False):
            return True
        if log.sleep_hours is not None and log.sleep_hours < CRITICAL_SLEEP_H:
            return True
    return False


def apply(session, log, metrics=None) -> None:
    """Mutate a PlannedSession in place when the day's data calls for an easier one."""
    if session is None or session.kind in ("rest", "race"):
        return

    verdict = evaluate(log, metrics)
    if not verdict.applied:
        return

    session.adjusted = True
    session.adjust_severity = verdict.severity

    if verdict.downgrade_to_rest and session.kind in ("intervals", "jog"):
        # Pain and illness are stop signals, not scale-back signals, and they get
        # their own wording — telling someone with knee pain that they are short on
        # sleep points them at the wrong problem.
        painful = bool(getattr(log, "pain_area", "")) or bool(getattr(log, "illness", False))

        if painful:
            session.adjust_reason = (
                f"Dropped because {verdict.reason}. Running through this is how a "
                "two-day problem becomes a six-week one — and the plan can lose a "
                "fortnight and still reach the start line."
            )
            session.title = "Rest today"
            session.detail = (
                "No running, and no walking it off either. If it still hurts in two "
                "days that is a physiotherapy question rather than a training one."
            )
            session.total_minutes = 0
        else:
            session.adjust_reason = (
                f"Eased because {verdict.reason}. Running hard on this little sleep "
                "buys fatigue rather than fitness."
                + (" This is well past a normal short night — today is for sleeping, "
                   "not training. Missing one session costs nothing; training on top of "
                   "this is how people get ill or injured."
                   if verdict.severity == "critical" else "")
            )
            session.title = "Easy walk — 25–30 min (instead of intervals)"
            session.detail = (
                "Swap the run blocks for a 25–30 minute walk at a comfortable pace. "
                "You lose nothing from one session moved, and you keep the week intact."
            )
            session.total_minutes = 28
        session.kind = "walk" if not painful else "rest"
        session.focus = "Recover"
        session.run_minutes = 0.0
        session.distance_km = 0.0 if painful else 2.5
        # An eased day is still a walk with targets, not a blank row.
        session.target_pace = "" if painful else "9:00–11:00/km"
        session.target_hr = "" if painful else "110–130 bpm"
        return

    # Otherwise keep the session but cut the running volume roughly in half.
    session.adjust_reason = (
        f"Scaled back because {verdict.reason}. Do the session, but take the easy end "
        "of the pace range and stop if it feels harder than usual."
    )
    if session.kind == "intervals" and session.run_minutes:
        session.run_minutes = round(session.run_minutes * 0.6, 1)
        session.title = f"{session.title} — shortened"
        # Totals must follow the shortened work, not the original prescription.
        session.total_minutes = round(session.run_minutes * 3 + 10)
    elif session.kind == "long" and session.distance_km:
        session.distance_km = round(session.distance_km * 0.7, 1)
        session.title = f"Long run — {session.distance_km:g} km (shortened)"
        session.total_minutes = round(session.distance_km * 11)


def log_for(athlete, on: dt.date):
    """The log that should influence a session on `on` — the night before it."""
    from apps.journal.models import DailyLog

    return (
        DailyLog.objects.filter(athlete=athlete, log_date__lte=on)
        .order_by("-log_date", "-created_at")
        .first()
    )


def metrics_for(athlete, on: dt.date):
    """The most recent measured day at or before `on`."""
    from apps.journal.wellness import DailyMetrics

    return (
        DailyMetrics.objects.filter(athlete=athlete, metric_date__lte=on)
        .order_by("-metric_date")
        .first()
    )
