from rest_framework import serializers

from .models import Activity, ActivityMetrics, ActivityRecord, Segment


class SegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Segment
        fields = [
            "index", "kind", "start_offset_s", "duration_s", "distance_m",
            "avg_pace_s_per_km", "avg_cadence_spm",
            "hr_start", "hr_end", "hr_avg", "hr_max",
            "hr_recovery_60s", "hr_overshoot_bpm",
        ]


class ActivityMetricsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityMetrics
        exclude = ["id", "activity"]


class ActivityListSerializer(serializers.ModelSerializer):
    """Deliberately excludes records and segments — the list view renders dozens of
    rows and must not pull a per-second series for each one."""

    metrics = ActivityMetricsSerializer(read_only=True)

    class Meta:
        model = Activity
        fields = [
            "id", "garmin_activity_id", "source", "sport",
            "started_at", "local_date",
            "total_distance_m", "total_timer_s", "total_elapsed_s",
            "avg_hr", "max_hr", "avg_cadence_spm", "calories",
            "metrics",
        ]


class ActivityDetailSerializer(ActivityListSerializer):
    segments = SegmentSerializer(many=True, read_only=True)
    chart_notes = serializers.SerializerMethodField()

    class Meta(ActivityListSerializer.Meta):
        fields = ActivityListSerializer.Meta.fields + [
            "total_ascent_m", "total_descent_m", "segments", "chart_notes",
        ]

    def get_chart_notes(self, obj) -> dict:
        from .chart_notes import build

        previous = (
            Activity.objects.filter(athlete_id=obj.athlete_id, started_at__lt=obj.started_at)
            .select_related("metrics")
            .order_by("-started_at")
            .first()
        )
        return build(obj, obj.athlete, previous)


class ActivityStreamSerializer(serializers.ModelSerializer):
    """Per-second series, served separately so the detail view can render immediately
    and load the chart data after."""

    class Meta:
        model = ActivityRecord
        fields = [
            "offset_s", "distance_m", "speed_mps", "cadence_spm",
            "heart_rate", "altitude_m", "latitude", "longitude",
        ]
