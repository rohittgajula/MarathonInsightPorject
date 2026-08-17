from django.contrib.auth.models import User
from django.db import models

# Weekday -> what that day is for. Keys are "0" (Monday) .. "6" (Sunday).
DAY_TYPES = ["rest", "walk", "cross", "jog", "intervals", "long"]

DAY_TYPE_LABELS = {
    "rest": "Rest",
    "walk": "Easy walk",
    "cross": "Cross-training",
    "jog": "Easy jog",
    "intervals": "Run/walk intervals",
    "long": "Long run",
}

# Three running days with a weekend long run. Monday stays rest: new runners are
# injured by frequency far more often than by distance.
def default_training_days() -> dict:
    return {"0": "rest", "1": "intervals", "2": "rest", "3": "intervals",
            "4": "rest", "5": "walk", "6": "long"}


class Athlete(models.Model):
    """Tenancy root. Every piece of data in the system hangs off an Athlete."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="athlete")
    display_name = models.CharField(max_length=120)
    timezone = models.CharField(max_length=64, default="UTC")

    date_of_birth = models.DateField(null=True, blank=True)
    resting_hr = models.PositiveSmallIntegerField(null=True, blank=True)
    max_hr = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Observed max, not a formula estimate."
    )

    # Easy-pace prescription, in seconds per km. Pace discipline is scored against this
    # band, so it is per-athlete rather than a global constant.
    easy_pace_min = models.PositiveSmallIntegerField(
        default=600, help_text="Fast edge of the easy band, sec/km. 600 = 10:00/km."
    )
    easy_pace_max = models.PositiveSmallIntegerField(
        default=645, help_text="Slow edge of the easy band, sec/km. 645 = 10:45/km."
    )

    # Heart-rate guardrails for easy running.
    hr_easy_min = models.PositiveSmallIntegerField(default=130)
    hr_easy_max = models.PositiveSmallIntegerField(default=145)
    hr_ceiling = models.PositiveSmallIntegerField(
        default=155, help_text="Cross this during a run block and the athlete should walk."
    )

    # Cadence at or above this is classified as running rather than walking.
    run_cadence_threshold = models.PositiveSmallIntegerField(default=140)

    # Which weekday is for what. Editable, because a fixed Tue/Thu/Sun week does not
    # survive contact with anyone's actual life.
    training_days = models.JSONField(default=default_training_days)

    garmin_connected = models.BooleanField(default=False)
    garmin_last_sync = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name

    @property
    def local_now(self):
        """Now, in the athlete's own timezone.

        Django's TIME_ZONE is UTC, so timezone.localdate() answers a question nobody
        asked: at 00:48 in Kolkata it is still yesterday in UTC, and the whole app
        would show yesterday's session. Every 'today' must come from here.
        """
        from zoneinfo import ZoneInfo

        from django.utils import timezone

        try:
            zone = ZoneInfo(self.timezone or "UTC")
        except Exception:
            zone = ZoneInfo("UTC")
        return timezone.now().astimezone(zone)

    @property
    def local_today(self):
        return self.local_now.date()

    @property
    def running_days_per_week(self) -> int:
        return sum(1 for v in (self.training_days or {}).values()
                   if v in ("jog", "intervals", "long"))

    def day_type(self, weekday: int) -> str:
        """weekday: 0 = Monday."""
        return (self.training_days or {}).get(str(weekday), "rest")

    @property
    def token_dir(self) -> str:
        from django.conf import settings

        return f"{settings.GARMIN_TOKEN_ROOT}/athlete_{self.pk}"


class OwnedByAthlete(models.Model):
    """Base for every tenant-scoped model."""

    athlete = models.ForeignKey(Athlete, on_delete=models.CASCADE, related_name="%(class)ss")

    class Meta:
        abstract = True
