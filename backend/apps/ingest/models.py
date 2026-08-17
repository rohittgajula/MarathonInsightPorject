import hashlib

from django.db import models

from apps.athletes.models import OwnedByAthlete


def fit_upload_path(instance, filename):
    return f"fit/athlete_{instance.athlete_id}/{filename}"


class RawFitFile(OwnedByAthlete):
    """The original bytes, kept permanently.

    Two reasons this is non-negotiable: Garmin has no personal API, so the unofficial
    sync can break at any time and manual export becomes the fallback; and the
    segmentation algorithm will improve, at which point every past activity needs
    reprocessing from source rather than from a lossy summary.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PARSED = "parsed", "Parsed"
        FAILED = "failed", "Failed"

    file = models.FileField(upload_to=fit_upload_path)
    original_name = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64, db_index=True)
    size_bytes = models.PositiveIntegerField()

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    error = models.TextField(blank=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)
    parsed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]
        constraints = [
            models.UniqueConstraint(fields=["athlete", "sha256"], name="uniq_athlete_fit_hash")
        ]

    def __str__(self):
        return f"{self.original_name} ({self.status})"

    @staticmethod
    def hash_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()
