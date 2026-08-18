"""Calendar: what was planned and what actually happened, per day."""

import datetime as dt

from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.activities.models import Activity
from apps.journal.models import DailyLog, logs_by_day as journal_logs_by_day
from apps.journal.wellness import DailyMetrics

from .models import Race
from . import exercises as exercise_lib
from .fueling import plan as fueling_plan
from .session_review import build as build_day_review, planned_for, session_payload
from .template import session_for
from . import niggles as niggle_module
from . import weekly as weekly_module
from .coaching import FORM_CUES, TROUBLESHOOTING
from .race_plan import build as build_race_plan
from .warmup import routine


def _athlete(request):
    athlete = getattr(request.user, "athlete", None)
    if athlete is None:
        raise PermissionDenied("No athlete profile.")
    return athlete


def _parse(value, fallback):
    try:
        return dt.date.fromisoformat(value) if value else fallback
    except ValueError:
        return fallback


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def calendar(request):
    """A date range of days, each carrying plan and outcome.

    Past days show what happened; future days show what is prescribed. The readiness
    adjustment is applied only to the next training day — projecting today's poor
    sleep onto a session three weeks out would be nonsense.
    """
    athlete = _athlete(request)
    today = athlete.local_today
    start = _parse(request.query_params.get("from"), today.replace(day=1))
    end = _parse(request.query_params.get("to"), start + dt.timedelta(days=41))
    if end < start:
        start, end = end, start
    end = min(end, start + dt.timedelta(days=120))

    race = Race.objects.filter(athlete=athlete, is_target=True).first()

    activities = {}
    for a in Activity.objects.filter(
        athlete=athlete, local_date__gte=start, local_date__lte=end
    ).select_related("metrics"):
        activities.setdefault(a.local_date, []).append(a)

    metrics_by_day = {
        m.metric_date: m
        for m in DailyMetrics.objects.filter(
            athlete=athlete, metric_date__gte=start, metric_date__lte=end
        )
    }
    # Keyed by the day each entry is *about*, not the day it was typed — see
    # journal.models.effective_logs.
    logs_by_day = journal_logs_by_day(athlete, start, end)

    days = []
    cursor = start
    while cursor <= end:
        # The night before is what governs a session, so a note written on day D
        # shapes day D+1. That resolution lives in session_review.planned_for, which
        # the day-detail endpoint also calls — the popup explaining a row must be
        # judging the same session the row displays.
        session = planned_for(athlete, cursor, race, today, metrics_by_day, logs_by_day)

        done = activities.get(cursor, [])
        wellness = metrics_by_day.get(cursor)
        log = logs_by_day.get(cursor)

        days.append({
            "date": cursor,
            "is_today": cursor == today,
            "is_past": cursor < today,
            "is_race": bool(race and cursor == race.race_date),
            "planned": session_payload(session),
            "activities": [{
                "id": a.id, "sport": a.sport,
                "distance_km": round(a.total_distance_m / 1000, 2),
                "duration_s": a.total_elapsed_s,
                "run_blocks": a.metrics.run_block_count if hasattr(a, "metrics") else None,
                "longest_run_s": a.metrics.longest_run_s if hasattr(a, "metrics") else None,
                "avg_run_pace_s": a.metrics.avg_run_pace_s_per_km if hasattr(a, "metrics") else None,
            } for a in done],
            "wellness": ({
                "sleep_window": wellness.sleep_window,
                "sleep_hours": wellness.sleep_hours,
                "sleep_score": wellness.sleep_score,
                "training_readiness": wellness.training_readiness,
                "resting_hr": wellness.resting_hr,
            } if wellness else None),
            "log": ({"text": log.text, "felt": log.felt} if log else None),
        })
        cursor += dt.timedelta(days=1)

    return Response({
        "from": start, "to": end, "today": today,
        "race_date": race.race_date if race else None,
        "days": days,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def day_review(request):
    """One day in detail: what was prescribed, what was recorded, and what to change.

    The week table can only show the prescription. This is the other half of that
    row — opened from it, and judging the same session it displays.
    """
    athlete = _athlete(request)
    on = _parse(request.query_params.get("date"), athlete.local_today)
    race = Race.objects.filter(athlete=athlete, is_target=True).first()
    return Response(build_day_review(athlete, on, race))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def fueling(request):
    """Fluid, food and salt for a day's session, scaled to it and to the forecast.

    Defaults to the day the dashboard is showing rather than always to today: on a
    rest afternoon the useful answer is about tomorrow morning's run, and asking the
    athlete to change a date to get it would be the wrong way round.
    """
    from apps.ingest.weather import forecast as weather_forecast

    athlete = _athlete(request)
    today = athlete.local_today
    race = Race.objects.filter(athlete=athlete, is_target=True).first()
    if race is None:
        return Response({"detail": "No target race set."}, status=404)

    on = _parse(request.query_params.get("date"), None)
    if on is None:
        # A rest day has nothing to fuel, so look forward to the next day that has
        # something. The raw template is enough to find it — readiness is applied
        # below, once the date is settled.
        on = today
        if session_for(race.race_date, today, athlete).kind == "rest":
            for ahead in range(1, 8):
                candidate = today + dt.timedelta(days=ahead)
                if session_for(race.race_date, candidate, athlete).kind != "rest":
                    on = candidate
                    break

    # The eased session is the one the athlete is actually doing, and an eased
    # session is a shorter walk rather than a run — which changes every figure
    # below. Reading the raw template here would have the panel fuelling a session
    # the dashboard had already called off.
    prior = on - dt.timedelta(days=1)
    metrics_by_day = {
        m.metric_date: m for m in
        DailyMetrics.objects.filter(athlete=athlete, metric_date__in=[prior, on])
    }
    session = planned_for(
        athlete, on, race, today, metrics_by_day, journal_logs_by_day(athlete, prior, on)
    )
    if session is None:
        return Response({"detail": "No session for that date."}, status=404)

    conditions = weather_forecast(athlete, on) or {}
    payload = fueling_plan(athlete, session, conditions)
    payload["date"] = on
    payload["is_today"] = on == today
    payload["adjusted"] = session.adjusted
    payload["conditions"] = conditions
    return Response(payload)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def exercise_library(request):
    """The whole strength / mobility / rehab catalogue, plus any live prescription.

    `?area=` returns the routine for one niggle; without it, the library plus the
    prescriptions implied by whatever the athlete has most recently reported.
    """
    athlete = _athlete(request)
    payload = exercise_lib.catalogue()

    area = request.query_params.get("area")
    if area:
        severity = request.query_params.get("severity")
        payload["prescriptions"] = [exercise_lib.prescription(
            area,
            severity=int(severity) if (severity or "").isdigit() else 2,
            when=request.query_params.get("when") or "unclear",
        )]
        return Response(payload)

    # Standing prescriptions from the most recent log that reported anything.
    recent = (
        DailyLog.objects.filter(athlete=athlete)
        .exclude(pain_area="")
        .order_by("-log_date")
        .first()
    )
    payload["prescriptions"] = (
        [exercise_lib.prescription(
            recent.pain_area,
            severity=recent.pain_severity or 2,
            when=recent.pain_when or "unclear",
        )] if recent else []
    )
    payload["from_log"] = ({
        "date": recent.log_date, "text": recent.text,
    } if recent else None)
    return Response(payload)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def warmup(request):
    _athlete(request)
    return Response(routine())


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def technique(request):
    """Running form and troubleshooting — the things a plan assumes you already know."""
    _athlete(request)
    return Response({"cues": FORM_CUES, "troubleshooting": TROUBLESHOOTING})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def weekly(request):
    athlete = _athlete(request)
    race = Race.objects.filter(athlete=athlete, is_target=True).first()
    weeks = weekly_module.recent(athlete, race, weeks=6)
    return Response({"weeks": [
        {
            "start": w.start, "end": w.end, "plan_week": w.plan_week, "phase": w.phase,
            "planned_sessions": w.planned_sessions, "completed_sessions": w.completed_sessions,
            "planned_run_minutes": w.planned_run_minutes, "actual_run_minutes": w.actual_run_minutes,
            "planned_distance_km": w.planned_distance_km, "actual_distance_km": w.actual_distance_km,
            "longest_run_s": w.longest_run_s, "previous_longest_run_s": w.previous_longest_run_s,
            "pace_discipline_pct": w.pace_discipline_pct,
            "avg_sleep_h": w.avg_sleep_h, "sleep_debt_h": w.sleep_debt_h,
            "niggles": w.niggles, "verdict": w.verdict, "verdict_reason": w.verdict_reason,
            "off_plan_days": w.off_plan_days, "missed_days": w.missed_days,
            "in_progress": w.in_progress, "before_plan": w.before_plan,
            "days": w.days,
        } for w in weeks
    ]})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def niggles(request):
    return Response(niggle_module.timeline(_athlete(request)))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def race_plan(request):
    athlete = _athlete(request)
    race = Race.objects.filter(athlete=athlete, is_target=True).first()
    if race is None:
        return Response({"detail": "No target race set."}, status=404)
    return Response(build_race_plan(athlete, race))
