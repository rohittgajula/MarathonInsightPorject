from rest_framework import serializers

from .models import DAY_TYPES, DAY_TYPE_LABELS, Athlete


class AthleteSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    running_days_per_week = serializers.IntegerField(read_only=True)
    day_type_labels = serializers.SerializerMethodField()

    class Meta:
        model = Athlete
        fields = [
            "id", "username", "display_name", "timezone",
            "date_of_birth", "resting_hr", "max_hr",
            "easy_pace_min", "easy_pace_max",
            "hr_easy_min", "hr_easy_max", "hr_ceiling",
            "run_cadence_threshold", "training_days",
            "running_days_per_week", "day_type_labels",
            "garmin_connected", "garmin_last_sync",
        ]
        read_only_fields = [
            "id", "username", "garmin_connected", "garmin_last_sync",
            "running_days_per_week", "day_type_labels",
        ]

    def get_day_type_labels(self, obj) -> dict:
        return DAY_TYPE_LABELS

    def validate_training_days(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Expected an object keyed by weekday.")
        cleaned = {}
        for key in range(7):
            day = value.get(str(key), "rest")
            if day not in DAY_TYPES:
                raise serializers.ValidationError(
                    f"'{day}' is not a valid day type. Choose from: {', '.join(DAY_TYPES)}."
                )
            cleaned[str(key)] = day
        running = sum(1 for v in cleaned.values() if v in ("jog", "intervals", "long"))
        if running > 5:
            # A hard stop rather than a warning: this is the mistake that ends a
            # first training block, and the plan cannot absorb it.
            raise serializers.ValidationError(
                f"{running} running days a week is too many while building a base. "
                "Five is the ceiling; three is what this plan is written around."
            )
        return cleaned
