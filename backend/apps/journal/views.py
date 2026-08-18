import logging

from rest_framework import viewsets

from apps.athletes.mixins import AthleteScopedMixin
from apps.athletes.permissions import IsAthleteOwner

from .entries import JournalEntry
from .models import DailyLog
from .serializers import DailyLogSerializer, JournalEntrySerializer
from .tasks import analyse_log

logger = logging.getLogger(__name__)


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
        log_date = serializer.validated_data.get("log_date") or self.athlete.local_today
        addition = (serializer.validated_data.get("text") or "").strip()
        existing = DailyLog.objects.filter(athlete=self.athlete, log_date=log_date).first()

        if existing:
            # Append rather than replace. A day is written in pieces — a note in the
            # morning about sleep, another after the run about a niggle — and the old
            # behaviour silently destroyed the earlier one. Raw text is meant to be
            # kept permanently; overwriting it was the one thing this must not do.
            existing.text = f"{existing.text.rstrip()}\n{addition}" if addition else existing.text
            existing.ai_status = "pending"
            existing.save()
            serializer.instance = existing
        else:
            serializer.save(athlete=self.athlete, log_date=log_date)
        self._enqueue(serializer.instance)

    def perform_destroy(self, instance):
        """Deleting a day's log is the only way to undo an append."""
        instance.delete()

    def perform_update(self, serializer):
        serializer.save(ai_status="pending")
        self._enqueue(serializer.instance)

    @staticmethod
    def _enqueue(log) -> None:
        """Hand the entry to Claude, out of band.

        Failing to queue must never fail the write: the athlete's text is the record
        and the reading is an enrichment on top of it. If the broker is down the row
        simply stays `pending` until `reparse_logs` sweeps it up.
        """
        if log is None or log.pk is None:
            return
        try:
            analyse_log.delay(log.pk)
        except Exception:
            logger.exception("could not queue log %s for analysis", log.pk)


class JournalEntryViewSet(AthleteScopedMixin, viewsets.ModelViewSet):
    """Long-form entries. Unlike DailyLog these are unconstrained: write as many as
    you like, whenever, and nothing here changes the training plan."""

    queryset = JournalEntry.objects.select_related("activity", "race").all()
    serializer_class = JournalEntrySerializer
    permission_classes = [IsAthleteOwner]
    filterset_fields = ["entry_date", "activity", "race"]

    def perform_create(self, serializer):
        serializer.save(
            athlete=self.athlete,
            entry_date=serializer.validated_data.get("entry_date") or self.athlete.local_today,
        )
