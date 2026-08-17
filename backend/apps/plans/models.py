import datetime as dt

from django.db import models
from django.utils import timezone

from apps.athletes.models import OwnedByAthlete


class Race(OwnedByAthlete):
    """A target event.

    The race is what makes this a training system rather than a data viewer: weeks
    remaining is the denominator for every progression decision, so it lives in the
    database rather than being hardcoded per athlete.
    """

    class Goal(models.TextChoices):
        FINISH = "finish", "Finish — no time target"
        TIME = "time", "Target time"

    name = models.CharField(max_length=160)
    race_date = models.DateField(db_index=True)
    distance_m = models.PositiveIntegerField(help_text="Race distance in metres. 10K = 10000.")
    distance_label = models.CharField(max_length=20, blank=True, help_text="e.g. 10K, Half")
    location = models.CharField(max_length=160, blank=True)

    goal = models.CharField(max_length=10, choices=Goal.choices, default=Goal.FINISH)
    target_time_s = models.PositiveIntegerField(null=True, blank=True)

    # Exactly one race per athlete drives the plan; enforced below.
    is_target = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["race_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["athlete"],
                condition=models.Q(is_target=True),
                name="one_target_race_per_athlete",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.race_date})"

    def save(self, *args, **kwargs):
        if not self.distance_label:
            self.distance_label = self._auto_label()
        if self.is_target:
            # Demote any previous target rather than tripping the unique constraint.
            Race.objects.filter(athlete=self.athlete, is_target=True).exclude(pk=self.pk).update(
                is_target=False
            )
        super().save(*args, **kwargs)

    def _auto_label(self) -> str:
        known = {5000: "5K", 10000: "10K", 21097: "Half", 42195: "Marathon"}
        for metres, label in known.items():
            if abs(self.distance_m - metres) <= 100:
                return label
        return f"{self.distance_m / 1000:g}K"

    @property
    def days_until(self) -> int:
        return (self.race_date - timezone.localdate()).days

    @property
    def weeks_until(self) -> int:
        """Whole training weeks remaining, floored — a partial week is not a week
        you can plan a long run into."""
        return max(self.days_until // 7, 0)

    @property
    def is_past(self) -> bool:
        return self.race_date < timezone.localdate()

    def week_number(self, on: dt.date | None = None) -> int | None:
        """1-indexed plan week, counting backwards from race week.

        Week 1 is the first week of the plan; the race falls in the final week.
        Returns None before the plan starts or after the race.
        """
        on = on or timezone.localdate()
        if self.is_past:
            return None
        remaining_weeks = (self.race_date - on).days // 7
        return remaining_weeks + 1 if remaining_weeks >= 0 else None
