from rest_framework import serializers

from .models import Race


class RaceSerializer(serializers.ModelSerializer):
    days_until = serializers.IntegerField(read_only=True)
    weeks_until = serializers.IntegerField(read_only=True)
    is_past = serializers.BooleanField(read_only=True)
    week_number = serializers.SerializerMethodField()

    class Meta:
        model = Race
        fields = [
            "id", "name", "race_date", "distance_m", "distance_label", "location",
            "goal", "target_time_s", "is_target", "notes",
            "days_until", "weeks_until", "is_past", "week_number",
        ]
        read_only_fields = ["id", "days_until", "weeks_until", "is_past", "week_number"]

    def get_week_number(self, obj) -> int | None:
        return obj.week_number()

    def validate_distance_m(self, value):
        if value < 400:
            raise serializers.ValidationError("Race distance must be at least 400 m.")
        return value
