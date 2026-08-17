"""Evaluate the catalog against an athlete's data.

Idempotent by construction: earning is keyed uniquely per athlete, and `earned_on`
comes from the activity that crossed the threshold rather than from today. Running
this against a freshly imported history produces exactly the dates it would have
produced had it been running all along.
"""

from __future__ import annotations

import logging

from .catalog import CATALOG, build_context
from .models import EarnedAchievement

logger = logging.getLogger(__name__)


def evaluate(athlete) -> dict:
    context = build_context(athlete)
    already = {e.key: e for e in EarnedAchievement.objects.filter(athlete=athlete)}
    newly = []

    for definition in CATALOG:
        try:
            value, earned_on, activity = definition.evaluate(context)
        except Exception:  # noqa: BLE001 — one bad rule must not block the rest
            logger.exception("achievement %s failed to evaluate", definition.key)
            continue

        if earned_on is None or definition.key in already:
            continue

        EarnedAchievement.objects.create(
            athlete=athlete, key=definition.key, earned_on=earned_on,
            value=value, activity=activity if getattr(activity, "pk", None) else None,
        )
        newly.append(definition.key)

    return {"newly_earned": newly, "total": EarnedAchievement.objects.filter(athlete=athlete).count()}


def board(athlete) -> dict:
    """Everything, earned and locked, with honest progress on the locked ones."""
    context = build_context(athlete)
    earned = {e.key: e for e in EarnedAchievement.objects.filter(athlete=athlete)}
    items = []

    for definition in CATALOG:
        try:
            value, earned_on, _ = definition.evaluate(context)
        except Exception:  # noqa: BLE001
            logger.exception("achievement %s failed to evaluate", definition.key)
            continue

        row = earned.get(definition.key)
        is_earned = row is not None or earned_on is not None
        target = definition.target

        if definition.key == "no_overshoot":
            # Lower is better here, so progress cannot be value/target.
            progress = 100.0 if is_earned else max(0.0, min(99.0, (1 - min(value, 20) / 20) * 100))
        elif target:
            progress = min(100.0 if is_earned else 99.0, (value / target) * 100)
        else:
            progress = 100.0 if is_earned else 0.0

        items.append({
            "key": definition.key,
            "name": definition.name,
            "description": definition.description,
            "group": definition.group,
            "unit": definition.unit,
            "format": definition.format,
            "target": target,
            "value": round(value, 2),
            "progress": round(progress, 1),
            "earned": is_earned,
            "earned_on": row.earned_on if row else earned_on,
        })

    groups: dict[str, list] = {}
    for item in items:
        groups.setdefault(item["group"], []).append(item)

    return {
        "earned_count": sum(1 for i in items if i["earned"]),
        "total": len(items),
        "groups": [{"name": name, "items": rows} for name, rows in groups.items()],
        "recent": sorted(
            [i for i in items if i["earned"] and i["earned_on"]],
            key=lambda i: i["earned_on"], reverse=True,
        )[:3],
    }
