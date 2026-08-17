from django.contrib import admin

from .models import Activity, ActivityMetrics, Segment


class SegmentInline(admin.TabularInline):
    model = Segment
    extra = 0
    readonly_fields = [f.name for f in Segment._meta.fields if f.name != "id"]
    can_delete = False


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ["local_date", "athlete", "sport", "total_distance_m", "avg_hr", "metrics_current"]
    list_filter = ["sport", "source", "metrics_current"]
    date_hierarchy = "local_date"
    inlines = [SegmentInline]


@admin.register(ActivityMetrics)
class ActivityMetricsAdmin(admin.ModelAdmin):
    list_display = [
        "activity", "run_block_count", "longest_run_s",
        "avg_run_pace_s_per_km", "pace_discipline_pct", "avg_hr_recovery_60s",
    ]
