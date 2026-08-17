"""FIT file → persisted Activity pipeline.

Kept idempotent at both ends: a re-uploaded file is caught by its content hash, and a
re-synced Garmin activity is caught by its Garmin id. Either way the raw bytes are
stored first and everything downstream is derived, so `reprocess` can rebuild the
whole derived layer without touching the network.
"""

from __future__ import annotations

import datetime as dt
import logging
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from apps.activities.models import Activity, ActivityMetrics, ActivityRecord, Segment
from apps.analysis.metrics import compute
from apps.analysis.segmentation import ALGORITHM_VERSION, Sample, segment
from apps.athletes.models import Athlete

from .fit_parser import parse
from .models import RawFitFile

logger = logging.getLogger(__name__)


class DuplicateActivity(Exception):
    """Raised when the incoming file corresponds to an activity we already hold."""


def _aware(value: dt.datetime) -> dt.datetime:
    """FIT timestamps are naive UTC; make them explicit rather than guessing later."""
    if value is None:
        return timezone.now()
    if timezone.is_naive(value):
        return value.replace(tzinfo=dt.timezone.utc)
    return value


def _local_date(moment: dt.datetime, tz_name: str) -> dt.date:
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    return moment.astimezone(tz).date()


@transaction.atomic
def ingest_fit(raw: RawFitFile, garmin_activity_id: int | None = None) -> Activity:
    """Parse a stored RawFitFile into a full Activity with segments and metrics."""
    athlete = raw.athlete
    raw.file.open("rb")
    try:
        parsed = parse(raw.file)
    finally:
        raw.file.close()

    started_at = _aware(parsed.started_at)

    if garmin_activity_id is not None:
        existing = Activity.objects.filter(
            athlete=athlete, garmin_activity_id=garmin_activity_id
        ).first()
        if existing:
            raise DuplicateActivity(f"activity {garmin_activity_id} already ingested")

    activity = Activity.objects.create(
        athlete=athlete,
        garmin_activity_id=garmin_activity_id,
        source=Activity.Source.GARMIN_SYNC if garmin_activity_id else Activity.Source.FIT_UPLOAD,
        raw_file=raw,
        sport=parsed.sport,
        started_at=started_at,
        local_date=_local_date(started_at, athlete.timezone),
        total_distance_m=parsed.total_distance_m,
        total_timer_s=parsed.total_timer_s,
        total_elapsed_s=parsed.total_elapsed_s,
        avg_hr=parsed.avg_hr,
        max_hr=parsed.max_hr,
        avg_cadence_spm=parsed.avg_cadence_spm,
        total_ascent_m=parsed.total_ascent_m,
        total_descent_m=parsed.total_descent_m,
        calories=parsed.calories,
    )

    ActivityRecord.objects.bulk_create(
        [
            ActivityRecord(
                activity=activity,
                offset_s=s.offset_s,
                distance_m=s.distance_m,
                speed_mps=s.speed_mps,
                cadence_spm=s.cadence_spm,
                heart_rate=s.heart_rate,
                altitude_m=s.__dict__.get("_alt"),
                latitude=s.__dict__.get("_lat"),
                longitude=s.__dict__.get("_lon"),
            )
            for s in parsed.samples
        ],
        batch_size=2000,
    )

    build_derived(activity)

    raw.status = RawFitFile.Status.PARSED
    raw.parsed_at = timezone.now()
    raw.save(update_fields=["status", "parsed_at"])

    logger.info("ingested activity %s for athlete %s", activity.pk, athlete.pk)
    return activity


@transaction.atomic
def build_derived(activity: Activity) -> ActivityMetrics:
    """(Re)build segments and metrics from the stored per-second records.

    Safe to re-run at any time — this is what makes an algorithm change rollable
    across the entire history without re-downloading anything.
    """
    athlete = activity.athlete

    samples = [
        Sample(
            offset_s=r.offset_s,
            distance_m=r.distance_m,
            speed_mps=r.speed_mps,
            cadence_spm=r.cadence_spm,
            heart_rate=r.heart_rate,
        )
        for r in activity.records.all().order_by("offset_s")
    ]

    results = segment(samples, run_cadence_threshold=athlete.run_cadence_threshold)

    activity.segments.all().delete()
    Segment.objects.bulk_create(
        [
            Segment(
                activity=activity,
                index=s.index,
                kind=s.kind,
                start_offset_s=s.start_offset_s,
                duration_s=s.duration_s,
                distance_m=s.distance_m,
                avg_pace_s_per_km=s.avg_pace_s_per_km,
                avg_cadence_spm=s.avg_cadence_spm,
                hr_start=s.hr_start,
                hr_end=s.hr_end,
                hr_avg=s.hr_avg,
                hr_max=s.hr_max,
                hr_recovery_60s=s.hr_recovery_60s,
                hr_overshoot_bpm=s.hr_overshoot_bpm,
            )
            for s in results
        ]
    )

    computed = compute(
        results,
        easy_pace_min=athlete.easy_pace_min,
        easy_pace_max=athlete.easy_pace_max,
        hr_ceiling=athlete.hr_ceiling,
    )

    metrics, _ = ActivityMetrics.objects.update_or_create(
        activity=activity, defaults=computed.as_dict()
    )

    activity.metrics_current = True
    activity.save(update_fields=["metrics_current"])
    return metrics


def reprocess_athlete(athlete: Athlete) -> int:
    """Rebuild derived data for every activity. Use after an algorithm change."""
    count = 0
    for activity in Activity.objects.filter(athlete=athlete):
        build_derived(activity)
        count += 1
    return count


def stale_activities():
    """Activities whose metrics predate the current algorithm version."""
    return Activity.objects.filter(metrics__algorithm_version__lt=ALGORITHM_VERSION)
