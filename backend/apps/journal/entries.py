"""Long-form journal entries.

Deliberately separate from DailyLog, which is one short line per day whose whole
purpose is to drive the readiness rules. A journal entry is the opposite: as long as
you like, several per day if you want, optionally attached to an activity, and it
changes nothing about tomorrow's session.

Keeping them apart matters. If reflective writing quietly altered training, you would
start editing your own diary to get the session you wanted, and the honest record —
the thing that is actually useful to read back in December — would be gone.
"""

from django.db import models

from apps.athletes.models import OwnedByAthlete


class JournalEntry(OwnedByAthlete):
    entry_date = models.DateField(db_index=True)
    title = models.CharField(max_length=160, blank=True)
    body = models.TextField()

    # Optional anchor: "how the long run felt" belongs to that run.
    activity = models.ForeignKey(
        "activities.Activity", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="journal_entries",
    )
    race = models.ForeignKey(
        "plans.Race", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="journal_entries",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "journal entries"
        ordering = ["-entry_date", "-created_at"]
        indexes = [models.Index(fields=["athlete", "entry_date"])]

    def __str__(self):
        return self.title or f"{self.entry_date}: {self.body[:40]}"

    @property
    def flags(self) -> dict:
        """Signals spotted in the text, surfaced but never acted on.

        If an entry mentions pain, the UI offers to add it to the day's quick log —
        an explicit choice, rather than a diary silently rewriting the plan.
        """
        from .models import extract

        found = extract(self.body)
        return {
            "pain_area": found["pain_area"],
            "illness": found["illness"],
        }
