"""Homepage payload: upcoming sessions, insights, and trend series."""

import datetime as dt
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.activities.models import Activity
from apps.journal.models import DailyLog

from . import coaching, insights, readiness
from .models import Race

RUN_SPORTS = ["running", "trail_running", "treadmill_running", "track_running", "virtual_run"]
from .template import session_for, upcoming


def _session_dict(s):
    return {
        "date": s.date, "kind": s.kind, "title": s.title, "detail": s.detail,
        "plan_week": s.plan_week, "weeks_out": s.weeks_out, "phase": s.phase,
        "note": s.note, "run_minutes": s.run_minutes, "distance_km": s.distance_km,
        "target_pace": s.target_pace, "target_hr": s.target_hr,
        "total_minutes": s.total_minutes, "focus": s.focus,
        "adjusted": s.adjusted, "adjust_reason": s.adjust_reason,
        "adjust_severity": s.adjust_severity,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard(request):
    athlete = getattr(request.user, "athlete", None)
    if athlete is None:
        raise PermissionDenied("No athlete profile.")

    today = athlete.local_today
    tomorrow = today + dt.timedelta(days=1)
    race = Race.objects.filter(athlete=athlete, is_target=True).first()

    # Walks, rides and gym sessions are real training but they are not runs, and
    # putting them in a running-pace trend makes the trend meaningless.
    activities = list(
        Activity.objects.filter(athlete=athlete, sport__in=RUN_SPORTS)
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

    # Which session the athlete actually needs to see.
    #
    # A card headed "Tomorrow" is wrong for most of the day: at 00:48 the session that
    # matters is the one in a few hours' time, not the one 30 hours away. So show
    # today's until it is done, then move on. "Done" means an activity was recorded
    # today — the honest signal, rather than a clock guess about when people run.
    done_today = any(a.local_date == today for a in activities)
    show_today = bool(today_session) and today_session.kind != "rest" and not done_today
    focus_date = today if show_today else tomorrow
    focus_session = today_session if show_today else tomorrow_session

    # Readiness applies to the session being shown, not always to tomorrow's.
    latest_log = readiness.log_for(athlete, today)
    latest_metrics = readiness.metrics_for(athlete, today)
    readiness.apply(focus_session, latest_log, latest_metrics)
    for session in week:
        if session.date == focus_date:
            readiness.apply(session, latest_log, latest_metrics)

    from apps.journal.wellness import DailyMetrics

    wellness = [
        {
            "date": m.metric_date,
            "sleep_hours": m.sleep_hours,
            "sleep_need_hours": m.sleep_need_hours,
            "sleep_deficit_hours": m.sleep_deficit_hours,
            "sleep_score": m.sleep_score,
            "training_readiness": m.training_readiness,
            "resting_hr": m.resting_hr,
            "body_battery_high": m.body_battery_high,
            "load_ratio": m.load_ratio,
            "training_status": m.training_status,
        }
        for m in reversed(
            list(DailyMetrics.objects.filter(athlete=athlete).order_by("-metric_date")[:28])
        )
    ]

    last_run = next((a for a in activities if a.sport in RUN_SPORTS), None)
    coach_metrics = {"last_avg_hr": last_run.avg_hr if last_run else None}

    cards = insights.build(athlete, activities[0] if activities else None,
                           recent_metrics, log_count, focus_session,
                           wellness=wellness, today=today)

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

    from apps.ingest.weather import forecast as weather_forecast

    session_weather = {}
    # Any planned day gets a forecast, including a walk or an eased session. Guarding
    # on kind != "rest" meant the weather vanished at exactly the moment readiness
    # downgraded the session — the day you most need to know it will feel like 30 C.
    if focus_session:
        try:
            session_weather = weather_forecast(athlete, focus_date, hour=6)
        except Exception:  # noqa: BLE001 — weather is context, never load-bearing
            logger.warning("session forecast unavailable", exc_info=True)

    return Response({
        "wellness": wellness,
        "session_weather": session_weather,
        "session_steps": coaching.steps_for(focus_session, athlete),
        "session_targets": coaching.targets_for(focus_session, athlete, coach_metrics),
        "today": _session_dict(today_session) if today_session else None,
        # `tomorrow` is kept as the literal next calendar day; `up_next` is the one
        # the page leads with.
        "tomorrow": _session_dict(tomorrow_session) if tomorrow_session else None,
        "up_next": _session_dict(focus_session) if focus_session else None,
        "up_next_label": "Today" if show_today else "Tomorrow",
        "up_next_date": focus_date,
        "done_today": done_today,
        "local_date": today,
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
