"""Calendar: what was planned and what actually happened, per day."""

import datetime as dt

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.activities.models import Activity
from apps.journal.models import DailyLog
from apps.journal.wellness import DailyMetrics

from . import readiness
from .models import Race
from .template import session_for
from .coaching import FORM_CUES, TROUBLESHOOTING
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
    logs_by_day = {
        l.log_date: l
        for l in DailyLog.objects.filter(
            athlete=athlete, log_date__gte=start, log_date__lte=end
        )
    }

    days = []
    cursor = start
    while cursor <= end:
        session = session_for(race.race_date, cursor, athlete) if race else None

        # The night before is what governs a session, so a note written on day D
        # shapes day D+1 — but only where that night actually has data.
        #
        # Tomorrow is the one day allowed to fall back to "most recent", because for
        # tomorrow that genuinely means last night. Every later day requires its own
        # preceding row: projecting tonight's sleep onto a session three weeks out
        # would mark the whole calendar "shortened" off a single bad night.
        if session and cursor >= today:
            prior = cursor - dt.timedelta(days=1)
            if cursor == today + dt.timedelta(days=1):
                log = logs_by_day.get(prior) or readiness.log_for(athlete, prior)
                wellness_prior = metrics_by_day.get(prior) or readiness.metrics_for(athlete, prior)
            else:
                log = logs_by_day.get(prior)
                wellness_prior = metrics_by_day.get(prior)
            if log or wellness_prior:
                readiness.apply(session, log, wellness_prior)

        done = activities.get(cursor, [])
        wellness = metrics_by_day.get(cursor)
        log = logs_by_day.get(cursor)

        days.append({
            "date": cursor,
            "is_today": cursor == today,
            "is_past": cursor < today,
            "is_race": bool(race and cursor == race.race_date),
            "planned": ({
                "kind": session.kind, "title": session.title, "detail": session.detail,
                "focus": session.focus, "target_pace": session.target_pace,
                "target_hr": session.target_hr, "run_minutes": session.run_minutes,
                "distance_km": session.distance_km, "total_minutes": session.total_minutes,
                "plan_week": session.plan_week, "phase": session.phase, "note": session.note,
                "adjusted": session.adjusted, "adjust_reason": session.adjust_reason,
            } if session else None),
            "activities": [{
                "id": a.id, "sport": a.sport,
                "distance_km": round(a.total_distance_m / 1000, 2),
                "duration_s": a.total_elapsed_s,
                "run_blocks": a.metrics.run_block_count if hasattr(a, "metrics") else None,
                "longest_run_s": a.metrics.longest_run_s if hasattr(a, "metrics") else None,
                "avg_run_pace_s": a.metrics.avg_run_pace_s_per_km if hasattr(a, "metrics") else None,
            } for a in done],
            "wellness": ({
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
def warmup(request):
    _athlete(request)
    return Response(routine())


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def technique(request):
    """Running form and troubleshooting — the things a plan assumes you already know."""
    _athlete(request)
    return Response({"cues": FORM_CUES, "troubleshooting": TROUBLESHOOTING})
