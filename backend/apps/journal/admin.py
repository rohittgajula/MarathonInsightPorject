from django.contrib import admin

from .models import DailyLog


@admin.register(DailyLog)
class DailyLogAdmin(admin.ModelAdmin):
    list_display = ["log_date", "athlete", "alcohol_units", "sleep_hours", "felt"]
    list_filter = ["felt"]
    date_hierarchy = "log_date"


from .wellness import DailyMetrics


@admin.register(DailyMetrics)
class DailyMetricsAdmin(admin.ModelAdmin):
    list_display = [
        "metric_date", "athlete", "sleep_score", "training_readiness",
        "resting_hr", "training_status",
    ]
    date_hierarchy = "metric_date"
