from rest_framework import serializers

from .models import Athlete


class AthleteSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Athlete
        fields = [
            "id", "username", "display_name", "timezone",
            "date_of_birth", "resting_hr", "max_hr",
            "easy_pace_min", "easy_pace_max",
            "hr_easy_min", "hr_easy_max", "hr_ceiling",
            "run_cadence_threshold",
            "garmin_connected", "garmin_last_sync",
        ]
        read_only_fields = ["id", "username", "garmin_connected", "garmin_last_sync"]
