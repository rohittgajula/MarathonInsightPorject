from rest_framework import serializers

from . import schedule as schedule_module
from .models import Race


class RaceSerializer(serializers.ModelSerializer):
    days_until = serializers.IntegerField(read_only=True)
    weeks_until = serializers.IntegerField(read_only=True)
    is_past = serializers.BooleanField(read_only=True)
    week_number = serializers.SerializerMethodField()
    # What this race costs the calendar around it, so the Races page can say what
    # adding one does before the athlete finds out from the week table.
    recovery_days = serializers.SerializerMethodField()
    taper_days = serializers.SerializerMethodField()

    class Meta:
        model = Race
        fields = [
            "id", "name", "race_date", "distance_m", "distance_label", "location",
            "goal", "target_time_s", "is_target", "notes",
            "days_until", "weeks_until", "is_past", "week_number",
            "recovery_days", "taper_days",
        ]
        read_only_fields = [
            "id", "days_until", "weeks_until", "is_past", "week_number",
            "recovery_days", "taper_days",
        ]

    def get_week_number(self, obj) -> int | None:
        return obj.week_number()

    def get_recovery_days(self, obj) -> int:
        return schedule_module.recovery_days((obj.distance_m or 10000) / 1000)

    def get_taper_days(self, obj) -> int:
        return schedule_module.taper_days((obj.distance_m or 10000) / 1000)

    def validate_distance_m(self, value):
        if value < 400:
            raise serializers.ValidationError("Race distance must be at least 400 m.")
        return value

    def validate_race_date(self, value):
        """One race per date.

        Two races on one day is either a duplicate or a mistake, and the schedule
        has to pick one of them to prescribe — silently choosing the earlier row
        would make the calendar disagree with the race list.
        """
        view = self.context.get("view")
        if view is None:
            return value
        clash = Race.objects.filter(athlete=view.athlete, race_date=value)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        existing = clash.first()
        if existing is not None:
            raise serializers.ValidationError(
                f'You already have "{existing.name}" on {value}. '
                "Edit that one, or pick a different date."
            )
        return value
