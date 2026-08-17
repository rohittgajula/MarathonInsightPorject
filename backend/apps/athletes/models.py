from django.contrib.auth.models import User
from django.db import models


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

    garmin_connected = models.BooleanField(default=False)
    garmin_last_sync = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name

    @property
    def token_dir(self) -> str:
        from django.conf import settings

        return f"{settings.GARMIN_TOKEN_ROOT}/athlete_{self.pk}"


class OwnedByAthlete(models.Model):
    """Base for every tenant-scoped model."""

    athlete = models.ForeignKey(Athlete, on_delete=models.CASCADE, related_name="%(class)ss")

    class Meta:
        abstract = True
