from rest_framework import serializers

from .entries import JournalEntry
from .models import DailyLog


class DailyLogSerializer(serializers.ModelSerializer):
    # Optional so the quick-entry box can post just text and get today's date.
    log_date = serializers.DateField(required=False)

    class Meta:
        model = DailyLog
        fields = [
            "id", "log_date", "text",
            "alcohol_units", "sleep_hours", "felt",
            "created_at",
        ]
        # Structured fields are derived from `text` on save, never posted directly.
        read_only_fields = ["id", "alcohol_units", "sleep_hours", "felt", "created_at"]


class JournalEntrySerializer(serializers.ModelSerializer):
    entry_date = serializers.DateField(required=False)
    flags = serializers.ReadOnlyField()
    activity_label = serializers.SerializerMethodField()

    class Meta:
        model = JournalEntry
        fields = [
            "id", "entry_date", "title", "body",
            "activity", "activity_label", "race",
            "flags", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "flags", "activity_label", "created_at", "updated_at"]

    def get_activity_label(self, obj) -> str:
        if not obj.activity:
            return ""
        a = obj.activity
        return f"{a.local_date} · {a.total_distance_m / 1000:.2f} km {a.sport}"

    def validate_body(self, value):
        if not value.strip():
            raise serializers.ValidationError("An entry needs some text.")
        return value
