from django.utils import timezone
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from ..models import Album
from ..serializers import AlbumDetailSerializer, AlbumListSerializer


class AlbumViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Album.objects.filter(deleted_at__isnull=True)

    def get_serializer_class(self):
        if self.action == "list":
            return AlbumListSerializer
        return AlbumDetailSerializer

    def perform_destroy(self, album):
        # Soft delete only — never remove the row or the bucket files here.
        album.deleted_at = timezone.now()
        album.save(update_fields=["deleted_at"])