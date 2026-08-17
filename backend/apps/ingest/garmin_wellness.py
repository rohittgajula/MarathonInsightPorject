"""Pull daily wellness metrics from Garmin Connect.

Written defensively on purpose. Garmin's unofficial endpoints return different shapes
depending on device, subscription tier and whether the watch was worn overnight, and
several of them return `None` or an empty dict rather than erroring. Every read goes
through `_dig`, and one endpoint failing never aborts the day or the run — a partial
row is far more useful than no row.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Optional

from apps.athletes.models import Athlete
from apps.journal.wellness import DailyMetrics

logger = logging.getLogger(__name__)


def _dig(payload: Any, *path, default=None):
    """Walk nested dict/list keys, returning default at the first miss."""
    current = payload
    for key in path:
        if current is None:
            return default
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list):
            if not current:
                return default
            current = current[key] if isinstance(key, int) else None
        else:
            return default
    return default if current is None else current


def _int(value) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _float(value) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def fetch_day(client, day: dt.date) -> dict:
    """Collect one day's metrics. Each endpoint is isolated so one failure is partial."""
    iso = day.isoformat()
    out: dict = {}

    def attempt(label, fn):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — a missing metric is not a sync failure
            logger.debug("garmin %s unavailable for %s: %s", label, iso, exc)
            return None

    sleep = attempt("sleep", lambda: client.get_sleep_data(iso))
    if sleep:
        daily = _dig(sleep, "dailySleepDTO", default={}) or {}
        out.update(
            sleep_seconds=_int(daily.get("sleepTimeSeconds")),
            sleep_need_seconds=_int(_dig(daily, "sleepNeed", "actual"))
                               or _int(daily.get("sleepNeedSeconds")),
            sleep_score=_int(_dig(daily, "sleepScores", "overall", "value")),
            deep_sleep_seconds=_int(daily.get("deepSleepSeconds")),
            rem_sleep_seconds=_int(daily.get("remSleepSeconds")),
            awake_seconds=_int(daily.get("awakeSleepSeconds")),
        )
        out["hrv_overnight_avg"] = _int(_dig(sleep, "avgOvernightHrv"))

    readiness = attempt("training readiness", lambda: client.get_training_readiness(iso))
    if readiness:
        first = readiness[0] if isinstance(readiness, list) and readiness else readiness
        out.update(
            training_readiness=_int(_dig(first, "score")),
            training_readiness_level=str(_dig(first, "level", default="") or "")[:32],
        )

    status = attempt("training status", lambda: client.get_training_status(iso))
    if status:
        latest = _dig(status, "mostRecentTrainingLoadBalance",
                      "metricsTrainingLoadBalanceDTOMap", default={}) or {}
        entry = next(iter(latest.values()), {}) if isinstance(latest, dict) else {}
        out.update(
            acute_load=_float(entry.get("monthlyLoadAerobicLow"))
                       or _float(_dig(status, "acuteTrainingLoadDTO", "acwrPercent")),
            chronic_load=_float(entry.get("monthlyLoadAerobicHigh")),
        )
        recent = _dig(status, "mostRecentTrainingStatus",
                      "latestTrainingStatusData", default={}) or {}
        first_device = next(iter(recent.values()), {}) if isinstance(recent, dict) else {}
        out["training_status"] = str(first_device.get("trainingStatus") or "")[:40]
        acwr = _dig(first_device, "acuteTrainingLoadDTO", default={}) or {}
        out["acute_load"] = out.get("acute_load") or _float(acwr.get("dailyAcuteChronicWorkloadRatio"))

    hrv = attempt("hrv", lambda: client.get_hrv_data(iso))
    if hrv:
        out["hrv_status"] = str(_dig(hrv, "hrvSummary", "status", default="") or "")[:24]
        out["hrv_overnight_avg"] = out.get("hrv_overnight_avg") or _int(
            _dig(hrv, "hrvSummary", "lastNightAvg"))

    rhr = attempt("resting hr", lambda: client.get_rhr_day(iso))
    if rhr:
        values = _dig(rhr, "allMetrics", "metricsMap", "WELLNESS_RESTING_HEART_RATE",
                      default=[]) or []
        if values:
            out["resting_hr"] = _int(_dig(values, 0, "value"))

    stats = attempt("daily stats", lambda: client.get_stats(iso))
    if stats:
        out.update(
            steps=_int(stats.get("totalSteps")),
            stress_avg=_int(stats.get("averageStressLevel")),
            body_battery_high=_int(stats.get("bodyBatteryHighestValue")),
            body_battery_low=_int(stats.get("bodyBatteryLowestValue")),
        )
        out["resting_hr"] = out.get("resting_hr") or _int(stats.get("restingHeartRate"))

    # Drop keys that came back empty so an existing row is never overwritten with None.
    return {k: v for k, v in out.items() if v not in (None, "")}


def sync_wellness(athlete: Athlete, client, days: int = 14) -> dict:
    """Upsert the last `days` days of wellness metrics."""
    from django.utils import timezone

    today = timezone.localdate()
    written = 0
    empty = 0

    for offset in range(days):
        day = today - dt.timedelta(days=offset)
        try:
            payload = fetch_day(client, day)
        except Exception as exc:  # noqa: BLE001
            if "429" in str(exc):
                logger.warning("rate limited during wellness sync, stopping at %s", day)
                break
            logger.exception("wellness fetch failed for %s", day)
            continue

        if not payload:
            empty += 1
            continue

        DailyMetrics.objects.update_or_create(
            athlete=athlete, metric_date=day, defaults=payload
        )
        written += 1

    return {"days_written": written, "days_empty": empty}
