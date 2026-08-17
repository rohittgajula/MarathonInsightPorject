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


@dataclass
class Adjustment:
    applied: bool
    reason: str = ""
    downgrade_to_rest: bool = False


def evaluate(log) -> Adjustment:
    """Read one daily log and decide whether tomorrow should be eased."""
    if log is None:
        return Adjustment(False)

    reasons: list[str] = []
    to_rest = False

    if log.sleep_hours is not None:
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

    if not reasons:
        return Adjustment(False)

    joined = reasons[0] if len(reasons) == 1 else ", ".join(reasons[:-1]) + " and " + reasons[-1]
    return Adjustment(True, joined, to_rest)


def apply(session, log) -> None:
    """Mutate a PlannedSession in place when the log calls for an easier day."""
    if session is None or session.kind in ("rest", "race"):
        return

    verdict = evaluate(log)
    if not verdict.applied:
        return

    session.adjusted = True

    if verdict.downgrade_to_rest and session.kind == "intervals":
        session.adjust_reason = (
            f"Eased because {verdict.reason}. Running hard on this little sleep buys "
            "fatigue rather than fitness."
        )
        session.title = "Easy walk instead of intervals"
        session.detail = (
            "Swap the run blocks for a 25–30 minute walk. You lose nothing from one "
            "session moved, and you keep the week intact."
        )
        session.kind = "rest"
        session.focus = "Recover"
        session.run_minutes = 0.0
        # A walk day has no pace or heart-rate target to hit.
        session.target_pace = ""
        session.target_hr = ""
        return

    # Otherwise keep the session but cut the running volume roughly in half.
    session.adjust_reason = (
        f"Scaled back because {verdict.reason}. Do the session, but take the easy end "
        "of the pace range and stop if it feels harder than usual."
    )
    if session.kind == "intervals" and session.run_minutes:
        session.run_minutes = round(session.run_minutes * 0.6, 1)
        session.title = f"{session.title} — shortened"
    elif session.kind == "long" and session.distance_km:
        session.distance_km = round(session.distance_km * 0.7, 1)
        session.title = f"Long run — {session.distance_km:g} km (shortened)"


def log_for(athlete, on: dt.date):
    """The log that should influence a session on `on` — the night before it."""
    from apps.journal.models import DailyLog

    return (
        DailyLog.objects.filter(athlete=athlete, log_date__lte=on)
        .order_by("-log_date", "-created_at")
        .first()
    )
