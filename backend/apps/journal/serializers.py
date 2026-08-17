from rest_framework import serializers

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
