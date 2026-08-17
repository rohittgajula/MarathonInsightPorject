"""Homepage payload: upcoming sessions, insights, and trend series."""

import datetime as dt

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.activities.models import Activity
from apps.journal.models import DailyLog

from . import insights, readiness
from .models import Race
from .template import session_for, upcoming


def _session_dict(s):
    return {
        "date": s.date, "kind": s.kind, "title": s.title, "detail": s.detail,
        "plan_week": s.plan_week, "weeks_out": s.weeks_out, "phase": s.phase,
        "note": s.note, "run_minutes": s.run_minutes, "distance_km": s.distance_km,
        "target_pace": s.target_pace, "target_hr": s.target_hr,
        "total_minutes": s.total_minutes, "focus": s.focus,
        "adjusted": s.adjusted, "adjust_reason": s.adjust_reason,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard(request):
    athlete = getattr(request.user, "athlete", None)
    if athlete is None:
        raise PermissionDenied("No athlete profile.")

    today = timezone.localdate()
    tomorrow = today + dt.timedelta(days=1)
    race = Race.objects.filter(athlete=athlete, is_target=True).first()

    activities = list(
        Activity.objects.filter(athlete=athlete)
        .select_related("metrics")
        .order_by("-started_at")[:40]
    )
    # insights reads metrics.activity.local_date; pre-attach to avoid N+1.
    for a in activities:
        if hasattr(a, "metrics"):
            a.metrics.activity = a
    recent_metrics = [a.metrics for a in activities if hasattr(a, "metrics")]
    log_count = DailyLog.objects.filter(athlete=athlete).count()

    today_session = session_for(race.race_date, today, athlete) if race else None
    tomorrow_session = session_for(race.race_date, tomorrow, athlete) if race else None
    week = upcoming(race.race_date, today, 7, athlete) if race else []

    # What the athlete logged most recently eases tomorrow's session if it needs to.
    latest_log = readiness.log_for(athlete, today)
    readiness.apply(tomorrow_session, latest_log)
    for session in week:
        if session.date == tomorrow:
            readiness.apply(session, latest_log)

    cards = insights.build(athlete, activities[0] if activities else None,
                           recent_metrics, log_count, tomorrow_session)

    # Trend series, oldest first so charts read left to right.
    trend = [
        {
            "date": a.local_date,
            "distance_km": round(a.total_distance_m / 1000, 2),
            "longest_run_min": round(a.metrics.longest_run_s / 60, 1) if hasattr(a, "metrics") else None,
            "run_pace_s": a.metrics.avg_run_pace_s_per_km if hasattr(a, "metrics") else None,
            "discipline_pct": a.metrics.pace_discipline_pct if hasattr(a, "metrics") else None,
            "hr_recovery": a.metrics.avg_hr_recovery_60s if hasattr(a, "metrics") else None,
        }
        for a in reversed(activities)
    ]

    return Response({
        "today": _session_dict(today_session) if today_session else None,
        "tomorrow": _session_dict(tomorrow_session) if tomorrow_session else None,
        "week": [_session_dict(s) for s in week],
        "insights": [{"tone": c.tone, "headline": c.headline, "detail": c.detail} for c in cards],
        "trend": trend,
        "activity_count": Activity.objects.filter(athlete=athlete).count(),
        "log_count": log_count,
        "latest_log": (
            {
                "log_date": latest_log.log_date, "text": latest_log.text,
                "sleep_hours": latest_log.sleep_hours,
                "alcohol_units": latest_log.alcohol_units, "felt": latest_log.felt,
            }
            if latest_log else None
        ),
        "garmin_connected": athlete.garmin_connected,
    })
