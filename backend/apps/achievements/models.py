from django.db import models

from apps.athletes.models import OwnedByAthlete


class EarnedAchievement(OwnedByAthlete):
    """One achievement, earned once.

    Definitions live in code (catalog.py); only the earning is stored. That way a
    reworded or retuned achievement does not require a data migration, and evaluation
    stays idempotent — re-running never duplicates or re-dates anything.

    `earned_on` is the date the athlete actually did the thing, not the date the code
    noticed. Backfilling history must produce the same dates as having run all along,
    otherwise the achievement is a record of when a feature shipped.
    """

    key = models.CharField(max_length=48)
    earned_on = models.DateField()
    value = models.FloatField(null=True, blank=True, help_text="The measurement that earned it.")
    activity = models.ForeignKey(
        "activities.Activity", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="achievements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-earned_on", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["athlete", "key"], name="uniq_athlete_achievement")
        ]

    def __str__(self):
        return f"{self.key} on {self.earned_on}"
