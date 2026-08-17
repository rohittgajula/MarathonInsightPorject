from django.contrib import admin

from .models import RawFitFile


@admin.register(RawFitFile)
class RawFitFileAdmin(admin.ModelAdmin):
    list_display = ["original_name", "athlete", "status", "size_bytes", "uploaded_at", "parsed_at"]
    list_filter = ["status"]
    readonly_fields = ["sha256", "size_bytes", "uploaded_at", "parsed_at"]
