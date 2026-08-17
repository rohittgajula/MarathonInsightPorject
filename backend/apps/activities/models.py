from django.db import models

from apps.athletes.models import OwnedByAthlete


class Activity(OwnedByAthlete):
    """One recorded session. Summary fields mirror the FIT `session` message."""

    class Source(models.TextChoices):
        GARMIN_SYNC = "garmin_sync", "Garmin sync"
        FIT_UPLOAD = "fit_upload", "Manual FIT upload"

    # Garmin's own id when we have it; lets sync stay idempotent across re-runs.
    garmin_activity_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    source = models.CharField(max_length=20, choices=Source.choices)
    raw_file = models.ForeignKey(
        "ingest.RawFitFile", on_delete=models.SET_NULL, null=True, blank=True, related_name="activities"
    )

    sport = models.CharField(max_length=40, default="running")
    started_at = models.DateTimeField(db_index=True)
    local_date = models.DateField(db_index=True, help_text="Calendar date in the athlete's timezone.")

    total_distance_m = models.FloatField(default=0)
    total_timer_s = models.FloatField(default=0)
    total_elapsed_s = models.FloatField(default=0)

    avg_hr = models.PositiveSmallIntegerField(null=True, blank=True)
    max_hr = models.PositiveSmallIntegerField(null=True, blank=True)
    avg_cadence_spm = models.FloatField(null=True, blank=True)
    total_ascent_m = models.FloatField(null=True, blank=True)
    total_descent_m = models.FloatField(null=True, blank=True)
    calories = models.PositiveIntegerField(null=True, blank=True)

    # Set false when the segmentation algorithm changes, to flag for reprocessing.
    metrics_current = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "activities"
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["athlete", "garmin_activity_id"],
                condition=models.Q(garmin_activity_id__isnull=False),
                name="uniq_athlete_garmin_activity",
            )
        ]

    def __str__(self):
        return f"{self.local_date} {self.sport} {self.total_distance_m / 1000:.2f}km"


class ActivityRecord(models.Model):
    """Per-second sample. The FIT file's real payload — a 28 min run is ~1,670 rows.

    Kept deliberately narrow and without an auto PK-heavy index set, because these
    are written in bulk and only ever read as a full ordered series per activity.
    """

    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="records")
    offset_s = models.FloatField(help_text="Seconds since activity start.")

    distance_m = models.FloatField(null=True)
    speed_mps = models.FloatField(null=True)
    cadence_spm = models.FloatField(null=True, help_text="Full steps/min, both legs.")
    heart_rate = models.PositiveSmallIntegerField(null=True)
    altitude_m = models.FloatField(null=True)
    latitude = models.FloatField(null=True)
    longitude = models.FloatField(null=True)

    # Running dynamics. Present on an Instinct 2X with a compatible sensor and absent
    # otherwise, so every one is nullable. Stored now because the raw file has them
    # and re-parsing later is free, whereas re-collecting a run is not.
    power_w = models.FloatField(null=True)
    vertical_oscillation_mm = models.FloatField(null=True)
    ground_contact_ms = models.FloatField(null=True)
    stride_length_m = models.FloatField(null=True)
    vertical_ratio = models.FloatField(null=True)
    respiration_rate = models.FloatField(null=True)
    temperature_c = models.FloatField(null=True)

    class Meta:
        ordering = ["offset_s"]
        indexes = [models.Index(fields=["activity", "offset_s"])]


class Segment(models.Model):
    """A contiguous run / walk / stop block, derived from cadence.

    This is the entity Garmin does not give you: lap data hides the fact that a
    "2.6 km run" was actually five short run blocks with walking in between.
    """

    class Kind(models.TextChoices):
        RUN = "run", "Run"
        WALK = "walk", "Walk"
        STOP = "stop", "Stop"

    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="segments")
    index = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=8, choices=Kind.choices, db_index=True)

    start_offset_s = models.FloatField()
    duration_s = models.FloatField()
    distance_m = models.FloatField()

    avg_pace_s_per_km = models.FloatField(null=True)
    avg_cadence_spm = models.FloatField(null=True)
    hr_start = models.PositiveSmallIntegerField(null=True)
    hr_end = models.PositiveSmallIntegerField(null=True)
    hr_avg = models.PositiveSmallIntegerField(null=True)
    hr_max = models.PositiveSmallIntegerField(null=True)

    # Both only populated on recovery blocks following a run block of 60 s or more.
    # Measured from peak HR rather than the block boundary, because cardiac lag keeps
    # HR climbing for 15-25 s after running stops.
    hr_recovery_60s = models.SmallIntegerField(
        null=True, blank=True, help_text="Peak HR minus HR 60s later. Higher is fitter."
    )
    hr_overshoot_bpm = models.SmallIntegerField(
        null=True, blank=True,
        help_text="How far HR kept climbing after the run block stopped. Lower is fitter.",
    )

    class Meta:
        ordering = ["activity", "index"]
        unique_together = [("activity", "index")]

    def __str__(self):
        return f"{self.kind} {self.duration_s:.0f}s"


class ActivityMetrics(models.Model):
    """Derived per-activity rollup. Recomputed from records+segments, never authored."""

    activity = models.OneToOneField(Activity, on_delete=models.CASCADE, related_name="metrics")

    run_time_s = models.FloatField(default=0)
    walk_time_s = models.FloatField(default=0)
    stop_time_s = models.FloatField(default=0)
    run_distance_m = models.FloatField(default=0)
    walk_distance_m = models.FloatField(default=0)

    run_block_count = models.PositiveSmallIntegerField(default=0)
    longest_run_s = models.FloatField(default=0)
    longest_run_m = models.FloatField(default=0)

    avg_run_pace_s_per_km = models.FloatField(null=True)
    avg_run_cadence_spm = models.FloatField(null=True)

    # Share of running seconds spent inside the athlete's prescribed easy-pace band.
    pace_discipline_pct = models.FloatField(null=True)
    # Share of running seconds spent above hr_ceiling.
    hr_over_ceiling_pct = models.FloatField(null=True)
    # Mean HRR60 across qualifying walk breaks. Rises as fitness improves.
    avg_hr_recovery_60s = models.FloatField(null=True)
    avg_hr_overshoot_bpm = models.FloatField(null=True)

    computed_at = models.DateTimeField(auto_now=True)
    algorithm_version = models.PositiveSmallIntegerField(default=1)

    class Meta:
        verbose_name_plural = "activity metrics"

    def __str__(self):
        return f"metrics for {self.activity_id}"
