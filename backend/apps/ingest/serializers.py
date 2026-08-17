from rest_framework import serializers

from .models import RawFitFile


class RawFitFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawFitFile
        fields = [
            "id", "original_name", "sha256", "size_bytes",
            "status", "error", "uploaded_at", "parsed_at",
        ]
        read_only_fields = fields
