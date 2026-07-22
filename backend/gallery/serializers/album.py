from rest_framework import serializers

from gallery.models import Album
from gallery.services.storage_service import generate_presigned_download_url

from .media import MediaSerializer


class AlbumListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for the album list in the private admin panel."""

    media_count = serializers.IntegerField(source="media.count", read_only=True)
    cover_thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Album
        fields = [
            "id",
            "name",
            "slug",
            "start_date",
            "end_date",
            "media_count",
            "cover_thumbnail_url",
            "created_at",
        ]

    def get_cover_thumbnail_url(self, obj):
        if obj.cover and obj.cover.thumbnail_key:
            return generate_presigned_download_url(obj.cover.thumbnail_key)
        return None


class AlbumDetailSerializer(serializers.ModelSerializer):
    """Full serializer: album + its media, used by both the admin panel and the public gallery."""

    media = MediaSerializer(many=True, read_only=True)

    class Meta:
        model = Album
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "start_date",
            "end_date",
            "cover",
            "media",
            "created_at",
            "updated_at",
        ]
