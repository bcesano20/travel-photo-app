from rest_framework import serializers

from gallery.models import Album
from gallery.services.storage_service import generate_presigned_download_url

from .media import MediaSerializer


def _cover_thumbnail_url(obj):
    if obj.cover and obj.cover.thumbnail_key:
        return generate_presigned_download_url(obj.cover.thumbnail_key)
    return None


class AlbumListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for the album list in the private admin panel."""

    media_count = serializers.SerializerMethodField()
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

    def get_media_count(self, obj):
        return obj.media.filter(deleted_at__isnull=True).count()

    def get_cover_thumbnail_url(self, obj):
        return _cover_thumbnail_url(obj)


class AlbumDetailSerializer(serializers.ModelSerializer):
    """Full serializer: album + its media, used by both the admin panel and the public gallery."""

    parent = serializers.PrimaryKeyRelatedField(
        queryset=Album.objects.filter(deleted_at__isnull=True),
        required=False,
        allow_null=True,
    )
    cover_thumbnail_url = serializers.SerializerMethodField()
    media = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = Album
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "start_date",
            "end_date",
            "parent",
            "cover",
            "cover_thumbnail_url",
            "media",
            "children",
            "created_at",
            "updated_at",
        ]

    def validate_parent(self, value):
        if value is None:
            return value

        if value.parent_id is not None:
            raise serializers.ValidationError(
                "No se pueden crear sub-álbumes dentro de otro sub-álbum (solo un nivel)."
            )

        if self.instance is not None:
            if value.pk == self.instance.pk:
                raise serializers.ValidationError(
                    "Un álbum no puede ser su propio padre."
                )
            if self.instance.children.filter(deleted_at__isnull=True).exists():
                raise serializers.ValidationError(
                    "No podés convertir un álbum con sub-álbumes en un sub-álbum."
                )

        return value

    def get_cover_thumbnail_url(self, obj):
        return _cover_thumbnail_url(obj)

    def get_media(self, obj):
        media_qs = obj.media.filter(deleted_at__isnull=True)
        return MediaSerializer(media_qs, many=True, context=self.context).data

    def get_children(self, obj):
        children_qs = obj.children.filter(deleted_at__isnull=True)
        return AlbumDetailSerializer(children_qs, many=True, context=self.context).data
