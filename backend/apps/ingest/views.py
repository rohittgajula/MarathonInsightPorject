import logging

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.activities.serializers import ActivityDetailSerializer
from apps.athletes.mixins import AthleteScopedMixin
from apps.athletes.permissions import IsAthleteOwner

from .models import RawFitFile
from .serializers import RawFitFileSerializer
from .services import DuplicateActivity, ingest_fit

logger = logging.getLogger(__name__)

MAX_FIT_BYTES = 25 * 1024 * 1024


class RawFitFileViewSet(AthleteScopedMixin, viewsets.ModelViewSet):
    """Manual FIT upload.

    A first-class path, not a fallback: Garmin has no personal API, so the unofficial
    sync can break at any time and hand-exporting a .fit file has to stay a complete
    route into the system.
    """

    queryset = RawFitFile.objects.all()
    serializer_class = RawFitFileSerializer
    permission_classes = [IsAthleteOwner]
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def create(self, request, *args, **kwargs):
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)
        if upload.size > MAX_FIT_BYTES:
            return Response(
                {"detail": f"File exceeds {MAX_FIT_BYTES // (1024 * 1024)} MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = upload.read()
        upload.seek(0)
        digest = RawFitFile.hash_bytes(data)

        existing = RawFitFile.objects.filter(athlete=self.athlete, sha256=digest).first()
        if existing:
            activity = existing.activities.first()
            return Response(
                {
                    "detail": "This file has already been uploaded.",
                    "raw_file": RawFitFileSerializer(existing).data,
                    "activity": ActivityDetailSerializer(activity).data if activity else None,
                },
                status=status.HTTP_200_OK,
            )

        raw = RawFitFile.objects.create(
            athlete=self.athlete,
            file=upload,
            original_name=upload.name,
            sha256=digest,
            size_bytes=upload.size,
        )

        try:
            activity = ingest_fit(raw)
        except DuplicateActivity as exc:
            raw.status = RawFitFile.Status.FAILED
            raw.error = str(exc)
            raw.save(update_fields=["status", "error"])
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except Exception as exc:  # noqa: BLE001 - surface the parse failure to the user
            logger.exception("FIT parse failed for raw file %s", raw.pk)
            raw.status = RawFitFile.Status.FAILED
            raw.error = str(exc)
            raw.parsed_at = timezone.now()
            raw.save(update_fields=["status", "error", "parsed_at"])
            return Response(
                {"detail": f"Could not parse this FIT file: {exc}"},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(
            {
                "raw_file": RawFitFileSerializer(raw).data,
                "activity": ActivityDetailSerializer(activity).data,
            },
            status=status.HTTP_201_CREATED,
        )
