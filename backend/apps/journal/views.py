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
        """One log per day: posting again for the same date edits it.

        The UI calls this button 'Update note', so appending a second row for the
        same day was a silent lie — the calendar then showed whichever one it
        happened to read first.
        """
        log_date = serializer.validated_data.get("log_date") or timezone.localdate()
        existing = DailyLog.objects.filter(athlete=self.athlete, log_date=log_date).first()
        if existing:
            existing.text = serializer.validated_data.get("text", existing.text)
            existing.save()
            serializer.instance = existing
            return
        serializer.save(athlete=self.athlete, log_date=log_date)
