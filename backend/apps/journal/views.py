from django.utils import timezone
from rest_framework import viewsets

from apps.athletes.mixins import AthleteScopedMixin
from apps.athletes.permissions import IsAthleteOwner

from .models import DailyLog
from .serializers import DailyLogSerializer


class DailyLogViewSet(AthleteScopedMixin, viewsets.ModelViewSet):
    queryset = DailyLog.objects.all()
    serializer_class = DailyLogSerializer
    permission_classes = [IsAthleteOwner]
    filterset_fields = ["log_date"]

    def perform_create(self, serializer):
        serializer.save(
            athlete=self.athlete,
            log_date=serializer.validated_data.get("log_date") or timezone.localdate(),
        )
