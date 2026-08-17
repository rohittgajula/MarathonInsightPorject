import logging

from celery import shared_task

from apps.activities.models import Activity
from apps.athletes.models import Athlete

from .services import build_derived

logger = logging.getLogger(__name__)


@shared_task
def rebuild_activity_metrics(activity_id: int) -> int:
    build_derived(Activity.objects.get(pk=activity_id))
    return activity_id


@shared_task
def rebuild_stale_metrics() -> int:
    """Sweep for activities whose derived data is out of date.

    Runs on a schedule so an algorithm change or a settings change on the athlete
    profile propagates without anyone remembering to trigger it.
    """
    stale = Activity.objects.filter(metrics_current=False)
    count = 0
    for activity in stale.iterator():
        try:
            build_derived(activity)
            count += 1
        except Exception:
            logger.exception("rebuild failed for activity %s", activity.pk)
    if count:
        logger.info("rebuilt metrics for %s activities", count)
    return count


@shared_task
def sync_all_athletes() -> dict:
    """Background pull for every connected athlete.

    Failures are logged per athlete rather than raised: one athlete's expired token
    must not stop the others from syncing.
    """
    from .garmin import GarminAuthError, GarminRateLimited, sync_athlete

    summary = {"synced": 0, "skipped": 0, "imported": 0}
    for athlete in Athlete.objects.filter(garmin_connected=True):
        try:
            result = sync_athlete(athlete, limit=10)
            summary["synced"] += 1
            summary["imported"] += result.imported
        except GarminRateLimited:
            logger.warning("athlete %s rate limited; will retry next run", athlete.pk)
            summary["skipped"] += 1
        except GarminAuthError:
            logger.warning("athlete %s needs to log in again", athlete.pk)
            athlete.garmin_connected = False
            athlete.save(update_fields=["garmin_connected"])
            summary["skipped"] += 1
        except Exception:
            logger.exception("sync failed for athlete %s", athlete.pk)
            summary["skipped"] += 1
    return summary
