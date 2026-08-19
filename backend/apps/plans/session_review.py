"""One day, planned against what actually happened.

The week table shows the prescription — target pace, target HR, the distance the plan
asked for. It cannot show whether any of it was followed, and a plan you never check
yourself against is a wall chart rather than a training system. This module answers
the other half: what the session asked for, what the watch recorded, the gap between
them, and the one or two things worth changing next time.

Two rules shape everything here.

Every row cites a number the system holds. Where a session prescribes nothing for a
metric — a rest day has no target pace — the row says so rather than inventing a
target and then scoring against it.

A gap is not automatically a failure. Running further than prescribed is a warning,
not an achievement, because at this stage the plan is limited by what the athlete's
tendons can absorb rather than by what their lungs can do. Running *slower* than the
band is not flagged at all: for a beginner, too slow is a non-problem.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field
from typing import Optional

from . import readiness
from .template import session_in
from .weekly import RUN_SPORTS, week_bounds

# The kinds that actually ask for a run. A missed rest day is not a missed session.
PRESCRIBED_KINDS = {"intervals", "long", "jog", "race"}

# Faster than the easy band's fast edge by this much before it is called out. Below
# it, the difference is inside the noise of GPS pace and a beginner's stride.
PACE_TOLERANCE_S = 15
# A run block this many times longer than prescribed has left the plan's structure.
BLOCK_OVERRUN_FACTOR = 2.0
# Share of running time above the HR ceiling that turns a session from easy to hard.
HR_CEILING_WARN_PCT = 25.0
# Distance beyond the prescription before the ramp is worth naming.
DISTANCE_OVERRUN = 1.3
# Cadence targets, matching the thresholds `insights` reports against.
CADENCE_GOOD = 160
CADENCE_LOW = 150


@dataclass
class Row:
    """One planned-against-actual line."""

    key: str
    label: str
    planned: str
    actual: str
    delta: str = ""
    tone: str = "neutral"  # "good" | "warn" | "neutral"
    note: str = ""


@dataclass
class Suggestion:
    tone: str  # "good" | "warn" | "neutral"
    headline: str
    detail: str


@dataclass
class DayReview:
    date: dt.date
    is_past: bool
    is_today: bool
    state: str = "upcoming"  # done | missed | moved | rest | extra | upcoming | before_plan
    summary: str = ""
    planned: Optional[dict] = None
    activities: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)
    wellness: Optional[dict] = None
    log: Optional[dict] = None


# ---------------------------------------------------------------- formatting


def _pace(seconds: Optional[float]) -> str:
    if not seconds or seconds <= 0:
        return "—"
    return f"{int(seconds // 60)}:{int(round(seconds % 60)):02d}/km"


def _clock(seconds: Optional[float]) -> str:
    """m:ss, or h:mm:ss once it runs long enough to need it."""
    if seconds is None or seconds <= 0:
        return "—"
    total = int(round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _minutes(value: Optional[float]) -> str:
    """A prescription in minutes. 1.5 reads as 1:30, not "1.5 min"."""
    if not value:
        return "—"
    if value == int(value):
        return f"{int(value)} min"
    whole = int(value)
    return f"{whole}:{int(round((value - whole) * 60)):02d} min"


def _signed(value: float, unit: str, dp: int = 2) -> str:
    if abs(value) < 10 ** -dp:
        return "on target"
    return f"{value:+.{dp}f} {unit}"


def _signed_clock(seconds: float) -> str:
    if abs(seconds) < 30:
        return "on target"
    return f"{'+' if seconds > 0 else '-'}{_clock(abs(seconds))}"


@dataclass
class Band:
    """The range a metric is judged against, and where that range came from.

    A rest day prescribes no pace, but the athlete still has a standing easy band —
    and a run that happened on a rest day is exactly the one worth measuring. Falling
    back to the standing band keeps the day measurable; carrying `from_session` keeps
    the review honest about which of the two it is comparing against, so a standing
    band is never reported as a target this day set.
    """

    low: int
    high: int
    label: str
    from_session: bool


def _pace_band(athlete, session) -> Band:
    if session and session.target_pace_min_s:
        return Band(session.target_pace_min_s, session.target_pace_max_s,
                    session.target_pace, True)
    return Band(athlete.easy_pace_min, athlete.easy_pace_max,
                f"{_pace(athlete.easy_pace_min)}–{_pace(athlete.easy_pace_max)}"
                .replace("/km–", "–"), False)


def _hr_band(athlete, session) -> Band:
    if session and session.target_hr_min:
        return Band(session.target_hr_min, session.target_hr_max, session.target_hr, True)
    return Band(athlete.hr_easy_min, athlete.hr_easy_max,
                f"{athlete.hr_easy_min}–{athlete.hr_easy_max} bpm", False)


STANDING = "Your standing easy band — this day prescribed no target of its own."


# ---------------------------------------------------- the day's prescription


def planned_for(athlete, on: dt.date, sched, today: dt.date,
                metrics_by_day: dict, logs_by_day: dict):
    """The session for one date, carrying the readiness adjustment that applies to it.

    Shared with the calendar so a day's row and its review can never disagree. The
    adjustment is applied only from today forward, for the reason the calendar gives:
    projecting tonight's sleep onto a session three weeks out would mark the whole
    plan "shortened" off a single bad night.

    Takes the whole race calendar rather than one race: which mode a date is in
    depends on the races either side of it, not only on the one being counted down
    to. See `schedule.py`.
    """
    session = session_in(sched, on, athlete) if sched else None
    if session is None:
        return None
    if on < today:
        return session

    prior = on - dt.timedelta(days=1)
    # Wellness and logs are dated differently and must not be looked up the same way.
    # Garmin dates a night by the morning it ends, so day D's own row is the sleep
    # before a session on D. A written note is usually typed the evening before, so
    # D-1 is the one that applies.
    wellness_prior = metrics_by_day.get(on)
    if on == today + dt.timedelta(days=1):
        # Tomorrow is the one day allowed to fall back to "most recent", because for
        # tomorrow that genuinely means last night.
        log = logs_by_day.get(prior) or readiness.log_for(athlete, prior)
        wellness_prior = wellness_prior or readiness.metrics_for(athlete, on)
    else:
        log = logs_by_day.get(prior) or logs_by_day.get(on)

    if log or wellness_prior:
        readiness.apply(session, log, wellness_prior)
    return session


def session_payload(session) -> Optional[dict]:
    """The wire shape the calendar and the day review both send."""
    if session is None:
        return None
    return {
        "kind": session.kind, "title": session.title, "detail": session.detail,
        "focus": session.focus, "target_pace": session.target_pace,
        "target_hr": session.target_hr, "run_minutes": session.run_minutes,
        "walk_minutes": session.walk_minutes,
        "distance_km": session.distance_km, "total_minutes": session.total_minutes,
        "plan_week": session.plan_week, "phase": session.phase, "note": session.note,
        "adjusted": session.adjusted, "adjust_reason": session.adjust_reason,
        "adjust_severity": session.adjust_severity,
        "reps": session.reps, "rep_run_minutes": session.rep_run_minutes,
        "optional": session.optional,
        "before_plan": session.before_plan,
        # Which of the schedule's modes produced this day, and why. A recovery day
        # and a rest day look identical on the wire without it.
        "mode": session.mode, "mode_reason": session.mode_reason,
        "race_name": session.race_name,
    }


# ------------------------------------------------------------------ the rows


def _rows(athlete, session, activities, pace_band: Band, hr_band: Band) -> list[Row]:
    """Planned against actual, one metric per line.

    Rows are emitted only where at least one side has something to say. A blank row
    with two dashes in it teaches the reader to skim the table.
    """
    rows: list[Row] = []
    metrics = [a.metrics for a in activities if hasattr(a, "metrics")]

    total_km = sum(a.total_distance_m for a in activities) / 1000
    elapsed_s = sum(a.total_elapsed_s for a in activities)
    run_s = sum(m.run_time_s for m in metrics)
    walk_s = sum(m.walk_time_s for m in metrics)

    planned_km = session.distance_km if session else 0.0
    planned_run_min = session.run_minutes if session else 0.0
    planned_walk_min = session.walk_minutes if session else 0.0
    planned_total_min = session.total_minutes if session else 0.0

    # "Nothing prescribed" and "prescribed as zero" are different statements, and a
    # single dash for both is why a walk day looked like missing data. A walk targets
    # zero running on purpose; a rest day targets nothing at all.
    # A rest day now carries real targets for its optional walk, so it does prescribe
    # something — it simply does not *require* it. Missing it is handled separately in
    # `_missed_suggestions`, which still treats a rest day as nothing owed.
    prescribes = bool(session) and not session.before_plan

    def target(value: float, unit: str = "min") -> str:
        if not prescribes:
            return "—"
        if not value:
            return "none" if unit == "min" else "—"
        return _minutes(value) if unit == "min" else f"{value:g} {unit}"

    # --- distance
    if planned_km or total_km:
        tone = "neutral"
        delta = ""
        if planned_km and total_km:
            ratio = total_km / planned_km
            delta = _signed(total_km - planned_km, "km")
            tone = "warn" if ratio > DISTANCE_OVERRUN else "good" if ratio >= 0.9 else "neutral"
        rows.append(Row(
            "distance", "Distance",
            f"{planned_km:g} km" if planned_km else "—",
            f"{total_km:.2f} km" if activities else "—",
            delta, tone,
        ))

    # --- running time
    if planned_run_min or run_s:
        tone = "neutral"
        delta = ""
        if planned_run_min and run_s:
            ratio = (run_s / 60) / planned_run_min
            delta = _signed_clock(run_s - planned_run_min * 60)
            tone = "warn" if ratio > DISTANCE_OVERRUN else "good" if ratio >= 0.8 else "neutral"
        rows.append(Row(
            "run_time", "Time actually running",
            target(planned_run_min), _clock(run_s) if metrics else "—",
            delta, tone,
            note="Run blocks only — walk breaks are counted separately." if metrics else "",
        ))

    # --- walking time, which is prescribed work rather than a shortfall
    if walk_s or planned_walk_min:
        delta = ""
        if planned_walk_min and walk_s:
            delta = _signed_clock(walk_s - planned_walk_min * 60)
        rows.append(Row(
            "walk_time", "Time walking",
            target(planned_walk_min), _clock(walk_s) if metrics else "—",
            delta, "neutral",
            note="Part of the session, not a gap in it.",
        ))

    # --- total time on feet
    if planned_total_min or elapsed_s:
        rows.append(Row(
            "total_time", "Total time",
            target(planned_total_min), _clock(elapsed_s) if activities else "—",
            _signed_clock(elapsed_s - planned_total_min * 60)
            if (planned_total_min and elapsed_s) else "",
            "neutral",
        ))

    # --- pace of the running, against the prescribed band
    paces = [m.avg_run_pace_s_per_km for m in metrics if m.avg_run_pace_s_per_km]
    actual_pace = sum(paces) / len(paces) if paces else None
    if actual_pace:
        tone, delta = "neutral", ""
        if actual_pace < pace_band.low - PACE_TOLERANCE_S:
            delta = f"{_clock(pace_band.low - actual_pace)}/km faster than the band"
            tone = "warn"
        elif actual_pace > pace_band.high + PACE_TOLERANCE_S:
            # Too slow is a non-problem for a beginner, so it is reported and not judged.
            delta = f"{_clock(actual_pace - pace_band.high)}/km slower than the band"
        else:
            delta, tone = "inside the band", "good"
        rows.append(Row(
            "run_pace", "Pace while running", pace_band.label,
            _pace(actual_pace), delta, tone,
            note="" if pace_band.from_session else STANDING,
        ))

    # --- how much of the running sat inside that band
    disciplines = [m.pace_discipline_pct for m in metrics if m.pace_discipline_pct is not None]
    if disciplines:
        value = sum(disciplines) / len(disciplines)
        rows.append(Row(
            "pace_discipline", "Running inside the easy band", "60% or more",
            f"{value:.0f}% of running time", "",
            "good" if value >= 60 else "warn" if value < 25 else "neutral",
        ))

    # --- heart rate. Whole-session average, so it is context rather than a verdict:
    #     it includes the walk breaks, which the band was never written for.
    hrs = [a.avg_hr for a in activities if a.avg_hr]
    if hrs:
        note = "Whole session, including walk breaks."
        rows.append(Row(
            "avg_hr", "Average heart rate", hr_band.label,
            f"{sum(hrs) / len(hrs):.0f} bpm", "", "neutral",
            note=note if hr_band.from_session else f"{note} {STANDING}",
        ))

    ceilings = [m.hr_over_ceiling_pct for m in metrics if m.hr_over_ceiling_pct is not None]
    if ceilings:
        value = sum(ceilings) / len(ceilings)
        rows.append(Row(
            "hr_ceiling", "Running above your HR ceiling",
            f"under {athlete.hr_ceiling} bpm", f"{value:.0f}% of running time", "",
            "warn" if value > HR_CEILING_WARN_PCT else "good" if value <= 10 else "neutral",
        ))

    # --- the structure of the session, which is what the summed totals hide
    longest = max((m.longest_run_s for m in metrics), default=0.0)
    if longest:
        prescribed_block = session.rep_run_minutes * 60 if session else 0.0
        tone, delta = "neutral", ""
        if prescribed_block:
            if longest > prescribed_block * BLOCK_OVERRUN_FACTOR:
                delta = f"{longest / prescribed_block:.1f}× the prescribed block"
                tone = "warn"
            elif longest >= prescribed_block * 0.8:
                delta = "as prescribed"
                tone = "good"
            else:
                delta = _signed_clock(longest - prescribed_block)
        rows.append(Row(
            "longest_block", "Longest unbroken run",
            _minutes(session.rep_run_minutes) if prescribed_block
            else ("none" if prescribes and not planned_run_min else "—"),
            _clock(longest), delta, tone,
        ))

    blocks = sum(m.run_block_count for m in metrics)
    if blocks:
        rows.append(Row(
            "run_blocks", "Run blocks",
            f"{session.reps}" if session and session.reps
            else ("none" if prescribes and not planned_run_min else "—"),
            f"{blocks}", "", "neutral",
        ))

    cadences = [m.avg_run_cadence_spm for m in metrics if m.avg_run_cadence_spm]
    if cadences:
        value = sum(cadences) / len(cadences)
        rows.append(Row(
            "cadence", "Cadence while running", f"{CADENCE_GOOD}+ spm",
            f"{value:.0f} spm", "",
            "good" if value >= CADENCE_GOOD else "warn" if value < CADENCE_LOW else "neutral",
        ))

    return rows


# ----------------------------------------------------------- the suggestions


def _missed_suggestions(session, moved_to) -> list[Suggestion]:
    """Nothing was recorded. Whether that matters depends on the day."""
    if session is None or session.before_plan:
        return [Suggestion(
            "neutral", "Before the plan started",
            "This date is earlier than your training block, so nothing was prescribed "
            "for it and there is nothing to judge it against.",
        )]

    if session.kind not in PRESCRIBED_KINDS:
        if session.kind in ("walk", "cross"):
            return [Suggestion(
                "neutral", "An easy day, and it stayed easy",
                f"{session.title} was optional support work rather than a session the "
                "plan depends on. Nothing was recorded, which costs the week nothing.",
            )]
        return [Suggestion(
            "neutral", "A rest day",
            "No running was prescribed. Adaptation happens on the days you don't run, "
            "so an empty row here is the plan working rather than a gap in it.",
        )]

    if moved_to:
        dates = ", ".join(d.strftime("%a %-d %b") for d in moved_to)
        return [Suggestion(
            "neutral", "Moved, not missed",
            f"Nothing was recorded on this date, but you ran on {dates} in the same "
            "week. The week counts the work, not the calendar slot — three sessions on "
            "days that suit you is the week done.",
        )]

    return [Suggestion(
        "warn", f"{session.title} was not recorded",
        "Nothing landed on this date and nothing else in the week covers it. Don't "
        "stack it onto the next session — the plan absorbs a missed day far better "
        "than it absorbs a doubled one. Pick the next prescribed day back up as written.",
    )]


def _done_suggestions(athlete, session, activities, rows, wellness,
                      pace_band: Band) -> list[Suggestion]:
    """Something was recorded. Lead with whatever most changes the next session."""
    warns: list[Suggestion] = []
    goods: list[Suggestion] = []
    metrics = [a.metrics for a in activities if hasattr(a, "metrics")]
    by_key = {r.key: r for r in rows}

    paces = [m.avg_run_pace_s_per_km for m in metrics if m.avg_run_pace_s_per_km]
    actual_pace = sum(paces) / len(paces) if paces else None

    # The single most valuable thing this system can say to a beginner.
    if actual_pace and actual_pace < pace_band.low - PACE_TOLERANCE_S:
        against = ("against a target of" if pace_band.from_session
                   else "against an easy band of")
        warns.append(Suggestion(
            "warn", f"You ran {_pace(actual_pace)} {against} {pace_band.label}",
            f"That is {_clock(pace_band.low - actual_pace)} per kilometre faster than "
            "easy. Slowing down is the single change that lets the run blocks get "
            "longer — keep the same cadence and shorten your stride rather than "
            "slowing your legs down.",
        ))
    elif (row := by_key.get("pace_discipline")) and row.tone == "warn":
        warns.append(Suggestion(
            "warn", f"Only {row.actual} sat inside your easy band",
            f"Your band is {pace_band.label}. Easy running is what builds the aerobic "
            "base; running it hard turns every session into the same medium-hard "
            "effort, which is how beginners plateau.",
        ))

    if (row := by_key.get("longest_block")) and row.tone == "warn":
        warns.append(Suggestion(
            "warn", f"Your longest block was {row.actual}, against {row.planned} prescribed",
            "Running the blocks longer than written is not a bonus. The block length is "
            "the dose your tendons and connective tissue are being asked to absorb, and "
            "it is set to rise gradually on purpose. Hold the prescribed block even when "
            "it feels too easy — especially then.",
        ))

    if (row := by_key.get("hr_ceiling")) and row.tone == "warn":
        warns.append(Suggestion(
            "warn", f"{row.actual} was above your {athlete.hr_ceiling} bpm ceiling",
            "The ceiling is the line where a run stops being aerobic. Above it you are "
            "buying fatigue rather than base fitness. Walk when it crosses, rather than "
            "pushing to the end of the block.",
        ))

    overshoots = [m.avg_hr_overshoot_bpm for m in metrics if m.avg_hr_overshoot_bpm is not None]
    if overshoots and sum(overshoots) / len(overshoots) > 4:
        value = sum(overshoots) / len(overshoots)
        warns.append(Suggestion(
            "warn", f"Heart rate kept climbing {value:.0f} bpm after you stopped running",
            "That means the run block was above what your aerobic system could cover, so "
            "it was still catching up once you started walking. It is the clearest "
            "signal to slow the blocks down rather than shorten them.",
        ))

    if (row := by_key.get("distance")) and row.tone == "warn":
        warns.append(Suggestion(
            "warn", f"You covered {row.actual} against {row.planned} prescribed",
            "Distance is the one thing worth being strict about this early. The plan is "
            "limited by what your tendons can absorb, not by what your lungs can do — "
            "and they adapt several weeks slower than your fitness does.",
        ))

    ran = any(m.run_time_s for m in metrics)
    if session and session.kind in PRESCRIBED_KINDS and metrics and not ran:
        warns.append(Suggestion(
            "warn", f"{session.title} was prescribed, and nothing here was run",
            "Something was recorded, but no block in it crossed the cadence that counts "
            f"as running ({athlete.run_cadence_threshold} steps per minute). Walking is "
            "real aerobic work and it is not nothing — but it is not this session, and "
            "the week still needs it.",
        ))

    if session and session.kind == "rest" and activities:
        warns.append(Suggestion(
            "warn", "This was written as a rest day",
            f"You have {athlete.running_days_per_week} running days set. New runners are "
            "injured by frequency far more often than by distance, so an extra day is a "
            "bigger risk than an extra kilometre. If this day suits you better, change "
            "the training week rather than adding to it.",
        ))

    readiness_score = (wellness or {}).get("training_readiness")
    if readiness_score is not None and readiness_score < 35 and activities:
        warns.append(Suggestion(
            "warn", f"Training readiness was {readiness_score}/100 that day",
            "Your watch was saying this was not a day to train, and the session went "
            "ahead anyway. One session is never worth much — the cost of training on "
            "top of a body that has not recovered is the week or two it takes back.",
        ))

    # Good news is reported with the same specificity, or it reads as consolation.
    if (row := by_key.get("run_pace")) and row.tone == "good":
        goods.append(Suggestion(
            "good", f"Pace held at {row.actual}, inside {row.planned}",
            "This is the hard part of the plan and you did it. Holding the easy band is "
            "what makes the next step up in distance possible.",
        ))
    if (row := by_key.get("pace_discipline")) and row.tone == "good":
        goods.append(Suggestion(
            "good", f"{row.actual} inside the easy band",
            "Most of your running sat where it was meant to.",
        ))
    if (row := by_key.get("longest_block")) and row.tone == "good":
        goods.append(Suggestion(
            "good", f"Blocks held at {row.actual} as written",
            "Running the session as prescribed rather than as it feels on the day is "
            "the habit that gets a beginner to a start line uninjured.",
        ))
    if (row := by_key.get("cadence")) and row.tone == "good":
        goods.append(Suggestion(
            "good", f"Cadence {row.actual}",
            "Already where it should be, so there is nothing to fix in your form. It "
            "also means you can slow down by shortening your stride rather than by "
            "slowing your legs — same rhythm, smaller steps.",
        ))
    if (row := by_key.get("distance")) and row.tone == "good" and not warns:
        goods.append(Suggestion(
            "good", f"{row.actual} against {row.planned} prescribed",
            "The session was done as written, which is the whole ask.",
        ))

    out = warns + goods
    if not out:
        if metrics and not ran:
            out.append(Suggestion(
                "neutral", "Recorded as a walk — no run blocks in it",
                "Nothing in this file crossed the cadence threshold that counts as "
                f"running ({athlete.run_cadence_threshold} steps per minute), so there "
                "is no pace or heart-rate verdict to give. On a walk day that is the "
                "session done.",
            ))
        else:
            out.append(Suggestion(
                "neutral", "Session recorded",
                "The run/walk metrics are derived from the per-second data, so the "
                "comparison above fills in once this file has been processed.",
            ))
    # Four is roughly what someone reads. Warnings are already ordered by what most
    # changes the next session.
    return out[:4]


# ------------------------------------------------------------------- the API


def build(athlete, on: dt.date, sched) -> DayReview:
    """Everything the day-detail popup shows, for one date."""
    from apps.activities.models import Activity
    from apps.journal.models import logs_by_day as journal_logs_by_day
    from apps.journal.wellness import DailyMetrics

    today = athlete.local_today
    prior = on - dt.timedelta(days=1)

    metrics_by_day = {
        m.metric_date: m for m in
        DailyMetrics.objects.filter(athlete=athlete, metric_date__in=[prior, on])
    }
    logs_by_day = journal_logs_by_day(athlete, prior, on)

    session = planned_for(athlete, on, sched, today, metrics_by_day, logs_by_day)
    activities = list(
        Activity.objects.filter(athlete=athlete, local_date=on).select_related("metrics")
    )

    review = DayReview(date=on, is_past=on < today, is_today=on == today)
    review.planned = session_payload(session)

    wellness = metrics_by_day.get(on)
    review.wellness = {
        "sleep_window": wellness.sleep_window, "sleep_hours": wellness.sleep_hours,
        "sleep_score": wellness.sleep_score, "resting_hr": wellness.resting_hr,
        "training_readiness": wellness.training_readiness,
    } if wellness else None

    log = logs_by_day.get(on)
    review.log = {"text": log.text, "felt": log.felt} if log else None

    review.activities = [{
        "id": a.id, "sport": a.sport,
        "distance_km": round(a.total_distance_m / 1000, 2),
        "duration_s": a.total_elapsed_s,
        "started_at": a.started_at,
        "place_name": a.place_name,
        "temp_c": a.temp_c, "feels_like_c": a.feels_like_c,
        "run_blocks": a.metrics.run_block_count if hasattr(a, "metrics") else None,
        "longest_run_s": a.metrics.longest_run_s if hasattr(a, "metrics") else None,
        "avg_run_pace_s": a.metrics.avg_run_pace_s_per_km if hasattr(a, "metrics") else None,
    } for a in activities]

    # A future date has nothing to compare, and saying "0 of 2.5 km" about tomorrow
    # would be reporting a shortfall that has not had a chance to happen yet.
    if on > today:
        review.state = "upcoming"
        # The title is already the heading above this line and the headline below it;
        # repeating it a third time here is noise, not emphasis.
        #
        # A day off the template says *why* instead. "Nothing prescribed — a rest
        # day" is true of a recovery day and badly misleading about it: the athlete
        # is not resting because the week is light, they are resting because they
        # raced on Sunday, and that is the sentence that stops them training anyway.
        off_template = session is not None and session.mode not in ("build", "race")
        review.summary = (
            session.mode_reason if off_template and session.mode_reason
            else "Not run yet." if session and session.kind != "rest"
            else "Nothing prescribed — a rest day."
        )
        if session:
            review.suggestions = [
                Suggestion("neutral", "What the session asks for", session.detail)
            ]
            if session.adjusted:
                review.suggestions.insert(0, Suggestion(
                    "warn" if session.adjust_severity == "critical" else "neutral",
                    "This session has been eased", session.adjust_reason,
                ))
        return _finish(review)

    if not activities:
        # "Did the week's work happen elsewhere" is the honest question — the same one
        # the weekly verdict asks. Someone who runs three times on days that suit them
        # has done the week, whatever the calendar says.
        start, end = week_bounds(on)
        moved_to = sorted({
            a.local_date for a in Activity.objects.filter(
                athlete=athlete, sport__in=RUN_SPORTS,
                local_date__gte=start, local_date__lte=min(end, today),
            ).exclude(local_date=on)
        })
        review.suggestions = _missed_suggestions(session, moved_to)
        if session is None or session.before_plan:
            review.state = "before_plan"
            review.summary = "Before the plan started."
        elif session.kind not in PRESCRIBED_KINDS:
            review.state = "rest"
            review.summary = f"{session.title} — nothing recorded, and nothing needed."
        elif moved_to:
            review.state = "moved"
            review.summary = f"{session.title} — not on this date, but the week has runs in it."
        else:
            review.state = "missed"
            review.summary = f"{session.title} — nothing recorded."
        return _finish(review)

    # Before the plan's start the template still returns a session, clamped to week 1,
    # but nothing was actually prescribed for that date — which is exactly why
    # weekly.py refuses to give those weeks a verdict. Judging adherence against a
    # prescription that did not exist would invent a shortfall. What the athlete's
    # own standing bands say about how they ran still holds, so those rows stay.
    judged = None if (session and session.before_plan) else session

    pace_band = _pace_band(athlete, judged)
    review.rows = _rows(athlete, judged, activities, pace_band, _hr_band(athlete, judged))
    review.suggestions = _done_suggestions(
        athlete, judged, activities, review.rows, review.wellness, pace_band)
    if session and session.before_plan:
        review.suggestions.insert(0, Suggestion(
            "neutral", "This date is before your plan started",
            "Nothing was prescribed for it, so there is no adherence to judge — only "
            "what the run itself shows. Shown for context.",
        ))
    # Cadence is the arbiter, not the sport label: Garmin files a run/walk session as
    # "running", and a day whose every block was walked has not done a run session.
    ran = any(a.metrics.run_time_s for a in activities if hasattr(a, "metrics"))
    prescribed_run = bool(judged and judged.kind in PRESCRIBED_KINDS)

    total_km = sum(a.total_distance_m for a in activities) / 1000
    if judged is None:
        review.state = "before_plan"
    elif judged.kind == "rest":
        review.state = "extra"
    elif prescribed_run and not ran:
        review.state = "partial"
    else:
        review.state = "done"

    review.summary = (
        f"{total_km:.2f} km recorded"
        + (f" against {judged.distance_km:g} km prescribed." if judged and judged.distance_km
           else " on a day with no distance target.")
    )
    return _finish(review)


def _finish(review: DayReview) -> dict:
    # asdict recurses into the Row and Suggestion dataclasses inside the lists.
    return asdict(review)
