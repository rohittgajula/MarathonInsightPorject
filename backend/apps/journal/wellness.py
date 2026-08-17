"""Daily wellness metrics pulled from Garmin.

Paired with DailyLog on purpose: the log is what the athlete *says* about a day,
this is what the watch *measured*. Both describe the same day from different angles,
and the readiness layer prefers the measurement when it has one.

Every field is nullable. Garmin's payloads differ by device, by subscription tier and
by whether the watch was worn overnight, so a missing value is normal and must never
be confused with a zero.
"""

from django.db import models

from apps.athletes.models import OwnedByAthlete


class DailyMetrics(OwnedByAthlete):
    metric_date = models.DateField(db_index=True)

    # Sleep. `sleep_need_seconds` is Garmin's own estimate of required sleep, which is
    # personalised, so the deficit below is more meaningful than a fixed 8-hour rule.
    sleep_seconds = models.PositiveIntegerField(null=True, blank=True)
    sleep_need_seconds = models.PositiveIntegerField(null=True, blank=True)
    sleep_score = models.PositiveSmallIntegerField(null=True, blank=True)
    deep_sleep_seconds = models.PositiveIntegerField(null=True, blank=True)
    rem_sleep_seconds = models.PositiveIntegerField(null=True, blank=True)
    awake_seconds = models.PositiveIntegerField(null=True, blank=True)

    resting_hr = models.PositiveSmallIntegerField(null=True, blank=True)
    hrv_overnight_avg = models.PositiveSmallIntegerField(null=True, blank=True)
    hrv_status = models.CharField(max_length=24, blank=True)

    body_battery_high = models.PositiveSmallIntegerField(null=True, blank=True)
    body_battery_low = models.PositiveSmallIntegerField(null=True, blank=True)

    training_readiness = models.PositiveSmallIntegerField(null=True, blank=True)
    training_readiness_level = models.CharField(max_length=32, blank=True)

    # Acute is roughly the last 7 days of load, chronic the last 28. The ratio between
    # them is the standard overreaching signal.
    acute_load = models.FloatField(null=True, blank=True)
    chronic_load = models.FloatField(null=True, blank=True)
    training_status = models.CharField(max_length=40, blank=True)

    steps = models.PositiveIntegerField(null=True, blank=True)
    stress_avg = models.PositiveSmallIntegerField(null=True, blank=True)

    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "daily metrics"
        ordering = ["-metric_date"]
        constraints = [
            models.UniqueConstraint(fields=["athlete", "metric_date"], name="uniq_athlete_day")
        ]

    def __str__(self):
        return f"{self.metric_date} metrics"

    @property
    def sleep_hours(self):
        return round(self.sleep_seconds / 3600, 1) if self.sleep_seconds else None

    @property
    def sleep_need_hours(self):
        return round(self.sleep_need_seconds / 3600, 1) if self.sleep_need_seconds else None

    @property
    def sleep_deficit_hours(self):
        """Positive means short of what Garmin says this athlete needs."""
        if not (self.sleep_seconds and self.sleep_need_seconds):
            return None
        return round((self.sleep_need_seconds - self.sleep_seconds) / 3600, 1)

    @property
    def load_ratio(self):
        """Acute:chronic. Above ~1.5 is the classic ramping-too-fast flag."""
        if not (self.acute_load and self.chronic_load):
            return None
        return round(self.acute_load / self.chronic_load, 2)
