from django.utils import timezone
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from ..models import Album
from ..serializers import AlbumAdminDetailSerializer, AlbumListSerializer


class AlbumViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Album.objects.filter(deleted_at__isnull=True)

    def get_queryset(self):
        # The dashboard only ever shows top-level albums
        if self.action == "list":
            # media_count is computed in the same query (one COUNT per album
            # via GROUP BY) and the cover is joined in.
            return (
                self.queryset.filter(parent__isnull=True)
                .select_related("cover")
                .with_media_count()
            )
        return self.queryset

    def get_serializer_class(self):
        if self.action == "list":
            return AlbumListSerializer
        # Admin-only: sub-albums come back as cover + count, without their
        # full media list (the public gallery uses AlbumDetailSerializer).
        return AlbumAdminDetailSerializer

    def perform_destroy(self, album):
        # Soft delete only — never remove the row or the bucket files here.
        # Cascades one level: deleting a parent takes its sub-albums with it.
        now = timezone.now()
        album.deleted_at = now
        album.save(update_fields=["deleted_at"])
        album.children.filter(deleted_at__isnull=True).update(deleted_at=now)
