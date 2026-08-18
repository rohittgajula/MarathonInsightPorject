import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("runproject")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


# Keep derived data honest without anyone remembering to trigger it.
#   - stale metrics: an algorithm change or a settings change on the athlete profile
#     marks activities metrics_current=False; this sweeps them up.
#   - garmin sync: hourly is deliberate. Garmin rate-limits aggressively and the
#     watch only reaches their servers when the phone app syncs, so polling faster
#     buys nothing but 429s.
app.conf.beat_schedule = {
    "rebuild-stale-metrics": {
        "task": "apps.ingest.tasks.rebuild_stale_metrics",
        "schedule": 300.0,
    },
    "sync-all-athletes": {
        "task": "apps.ingest.tasks.sync_all_athletes",
        "schedule": 3600.0,
    },
    # Logs written while the LLM quota was spent, or while the key was missing,
    # stay unread until something retries them. Ten minutes is well inside a free
    # tier's reset window and costs nothing when there is nothing to do.
    "sweep-unread-logs": {
        "task": "apps.journal.tasks.sweep_unread",
        "schedule": 600.0,
    },
}
