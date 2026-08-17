from django.contrib import admin

from .models import EarnedAchievement


@admin.register(EarnedAchievement)
class EarnedAchievementAdmin(admin.ModelAdmin):
    list_display = ["key", "athlete", "earned_on", "value"]
    list_filter = ["key"]
    date_hierarchy = "earned_on"
