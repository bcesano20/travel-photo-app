from rest_framework import serializers

from gallery.models import Album
from gallery.services.storage_service import generate_presigned_download_url

from .media import MediaSerializer


def _cover_thumbnail_url(obj):
    if obj.cover and obj.cover.thumbnail_key:
        return generate_presigned_download_url(obj.cover.thumbnail_key)
    return None


def _media_count(obj):
    # Querysets built with Album.objects.with_media_count() already carry the
    # count. The fallback keeps the serializers correct without it.
    annotated = getattr(obj, "media_count", None)
    if annotated is not None:
        return annotated
    return obj.media.filter(deleted_at__isnull=True).count()


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
        return _media_count(obj)

    def get_cover_thumbnail_url(self, obj):
        return _cover_thumbnail_url(obj)


class AlbumChildSerializer(serializers.ModelSerializer):
    """A sub-album as listed inside its parent in the admin panel: cover and
    file count only. Its media is not serialized (that's one query plus two
    signed URLs per file, and the admin page never shows them)."""

    media_count = serializers.SerializerMethodField()
    cover_thumbnail_url = serializers.SerializerMethodField()

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
            "media_count",
            "created_at",
            "updated_at",
        ]

    def get_media_count(self, obj):
        return _media_count(obj)

    def get_cover_thumbnail_url(self, obj):
        return _cover_thumbnail_url(obj)


class AlbumDetailSerializer(serializers.ModelSerializer):
    """Full serializer: album + its media + each sub-album's media. Used by the
    public gallery, which needs every sub-album's files for its lightbox. The
    admin panel uses AlbumAdminDetailSerializer instead."""

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
        # `active_media` is set by prefetch_related_objects(..., to_attr=...)
        # in the public view. A plain .filter() would ignore a prefetch.
        media_qs = getattr(obj, "active_media", None)
        if media_qs is None:
            media_qs = obj.media.filter(deleted_at__isnull=True)
        return MediaSerializer(media_qs, many=True, context=self.context).data

    def get_children(self, obj):
        # Only one level of nesting is allowed, so a sub-album never has
        # children: skip the query (and the recursion) for those.
        if obj.parent_id is not None:
            return []
        children_qs = getattr(obj, "active_children", None)
        if children_qs is None:
            children_qs = obj.children.filter(deleted_at__isnull=True).select_related(
                "cover"
            )
        return AlbumDetailSerializer(children_qs, many=True, context=self.context).data


class AlbumAdminDetailSerializer(AlbumDetailSerializer):
    """Admin panel detail: the album's own media, but sub-albums reduced to
    cover + count (AlbumChildSerializer). Also used for create/update
    responses, so saving an album doesn't re-serialize all the children."""

    def get_children(self, obj):
        if obj.parent_id is not None:
            return []
        children_qs = (
            obj.children.filter(deleted_at__isnull=True)
            .select_related("cover")
            .with_media_count()
        )
        return AlbumChildSerializer(children_qs, many=True, context=self.context).data
