"""Niggle tracking.

Pain is already extracted from every daily log and, until now, went nowhere. That is
the wrong place for it to stop: nobody re-reads six weeks of their own logs, so a knee
mentioned in weeks 2, 4 and 5 stays invisible until it stops being a niggle.

The threshold is deliberately low. Three mentions of one area inside a month is not
proof of anything, and the wording says so — but it is the point at which a runner
should notice, and noticing early is the entire value.
"""

from __future__ import annotations

import datetime as dt

# Mentions of one area within the window before it is worth flagging.
RECURRING_COUNT = 3
WINDOW_DAYS = 30
# Two mentions inside this many days reads as an ongoing problem rather than two
# unrelated bad days.
CLUSTER_DAYS = 10


def timeline(athlete, days: int = 120) -> dict:
    from apps.journal.models import DailyLog

    today = athlete.local_today
    since = today - dt.timedelta(days=days)

    logs = list(
        DailyLog.objects.filter(athlete=athlete, log_date__gte=since)
        .exclude(pain_area="")
        .order_by("log_date")
    )

    by_area: dict[str, list] = {}
    for log in logs:
        by_area.setdefault(log.pain_area, []).append(log)

    areas = []
    for area, entries in by_area.items():
        dates = [e.log_date for e in entries]
        window_start = today - dt.timedelta(days=WINDOW_DAYS)
        recent_count = sum(1 for d in dates if d >= window_start)

        gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
        clustered = any(g <= CLUSTER_DAYS for g in gaps)

        if recent_count >= RECURRING_COUNT:
            status, note = "recurring", (
                f"Mentioned {recent_count} times in the last {WINDOW_DAYS} days. That is "
                "not proof of an injury, but it is the point to stop running through it "
                "and get it looked at."
            )
        elif clustered and recent_count >= 2:
            status, note = "watch", (
                "Mentioned more than once within a short window, which reads as ongoing "
                "rather than two unrelated days. Worth watching."
            )
        else:
            status, note = "noted", "Mentioned once recently. Nothing to act on yet."

        areas.append({
            "area": area,
            "label": area.replace("_", " ").title(),
            "count": len(dates),
            "recent_count": recent_count,
            "first_seen": dates[0],
            "last_seen": dates[-1],
            "status": status,
            "note": note,
            "mentions": [
                {"date": e.log_date, "text": e.text[:180]} for e in entries[-6:]
            ],
        })

    order = {"recurring": 0, "watch": 1, "noted": 2}
    areas.sort(key=lambda a: (order[a["status"]], -a["recent_count"]))

    return {
        "areas": areas,
        "window_days": WINDOW_DAYS,
        "any_recurring": any(a["status"] == "recurring" for a in areas),
        "total_mentions": len(logs),
    }
