from django.db.models import Prefetch
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.athletes.mixins import AthleteScopedMixin
from apps.athletes.permissions import IsAthleteOwner

from .models import Activity
from .serializers import (
    ActivityDetailSerializer,
    ActivityListSerializer,
    ActivityStreamSerializer,
)


class ActivityViewSet(AthleteScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Activity.objects.select_related("metrics").all()
    permission_classes = [IsAthleteOwner]
    filterset_fields = ["sport", "local_date", "source"]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == "retrieve":
            qs = qs.prefetch_related("segments")
        date_from = self.request.query_params.get("from")
        date_to = self.request.query_params.get("to")
        if date_from:
            qs = qs.filter(local_date__gte=date_from)
        if date_to:
            qs = qs.filter(local_date__lte=date_to)
        return qs

    def get_serializer_class(self):
        return ActivityDetailSerializer if self.action == "retrieve" else ActivityListSerializer

    @action(detail=True, methods=["get"])
    def stream(self, request, pk=None):
        """Per-second series for charting. Separate from the detail payload so the
        page can render summary and segments without waiting on ~1,700 rows."""
        activity = self.get_object()
        records = activity.records.all().order_by("offset_s")
        return Response(ActivityStreamSerializer(records, many=True).data)

    @action(detail=True, methods=["post"])
    def reprocess(self, request, pk=None):
        """Rebuild segments and metrics from stored records, e.g. after the athlete
        changes their cadence threshold or easy-pace band."""
        from apps.ingest.services import build_derived

        activity = self.get_object()
        build_derived(activity)
        activity.refresh_from_db()
        return Response(ActivityDetailSerializer(activity).data)
