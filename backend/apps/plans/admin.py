from django.contrib import admin

from .models import Race


@admin.register(Race)
class RaceAdmin(admin.ModelAdmin):
    list_display = ["name", "athlete", "race_date", "distance_label", "is_target"]
    list_filter = ["is_target", "goal"]
