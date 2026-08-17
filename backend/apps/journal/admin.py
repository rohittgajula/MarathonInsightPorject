from django.contrib import admin

from .models import DailyLog


@admin.register(DailyLog)
class DailyLogAdmin(admin.ModelAdmin):
    list_display = ["log_date", "athlete", "alcohol_units", "sleep_hours", "felt"]
    list_filter = ["felt"]
    date_hierarchy = "log_date"
