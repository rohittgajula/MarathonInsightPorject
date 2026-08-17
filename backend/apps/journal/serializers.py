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
            "alcohol_units", "sleep_hours", "sleep_quality", "felt",
            "pain_area", "illness", "stressed", "travel",
            "detected", "created_at",
        ]
        # Structured fields are derived from `text` on save, never posted directly.
        read_only_fields = [
            "id", "alcohol_units", "sleep_hours", "sleep_quality", "felt",
            "pain_area", "illness", "stressed", "travel", "detected", "created_at",
        ]

    detected = serializers.SerializerMethodField()

    def get_detected(self, obj) -> list:
        """What the parser actually took from the text.

        Returned so the UI can say 'nothing detected' out loud. Silently extracting
        nothing looked identical to the feature being broken.
        """
        found = []
        if obj.sleep_hours is not None:
            found.append(f"{obj.sleep_hours:g} h sleep")
        elif obj.sleep_quality:
            found.append({"short": "short night", "poor": "slept badly",
                          "good": "slept well"}[obj.sleep_quality])
        if obj.alcohol_units is not None:
            found.append(f"{obj.alcohol_units:g} units alcohol")
        if obj.pain_area:
            found.append(f"{obj.pain_area.replace('_', ' ')} pain")
        if obj.illness:
            found.append("unwell")
        if obj.stressed:
            found.append("stress")
        if obj.travel:
            found.append("travel")
        if obj.felt:
            found.append(f"felt {obj.felt}")
        return found


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
