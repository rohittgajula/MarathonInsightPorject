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
