from django.contrib import admin

from .models import Athlete


@admin.register(Athlete)
class AthleteAdmin(admin.ModelAdmin):
    list_display = ["display_name", "user", "timezone", "garmin_connected", "garmin_last_sync"]
    search_fields = ["display_name", "user__username"]
