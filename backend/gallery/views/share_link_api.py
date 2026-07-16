from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from ..models import ShareLink
from ..serializers import ShareLinkSerializer


class ShareLinkViewSet(viewsets.ModelViewSet):
    """Private management of share links (create/revoke/list) — owner only."""

    permission_classes = [IsAuthenticated]
    serializer_class = ShareLinkSerializer
    queryset = ShareLink.objects.all()

    def get_queryset(self):
        queryset = super().get_queryset()
        album_id = self.request.query_params.get("album")
        if album_id:
            queryset = queryset.filter(album_id=album_id)
        return queryset
