from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import Album, Media
from ..serializers import MediaSerializer
from ..services import build_storage_key, generate_presigned_upload_url
from ..tasks import generate_thumbnail


class MediaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = MediaSerializer
    queryset = Media.objects.filter(deleted_at__isnull=True)

    @action(detail=False, methods=["post"], url_path="presigned-upload")
    def presigned_upload(self, request):
        """
        Step 1 of the upload flow. The frontend tells us it wants to upload
        a file (album, filename, content_type, size, type); we create the
        Media row in "pending" state and hand back a presigned URL the
        browser can PUT the raw bytes to directly — the file itself never
        touches this server.
        """
        album_id = request.data.get("album")
        original_filename = request.data.get("original_filename")
        content_type = request.data.get("content_type")
        size = request.data.get("size")
        media_type = request.data.get("type")

        if not all([album_id, original_filename, content_type, size, media_type]):
            return Response(
                {
                    "detail": "album, original_filename, content_type, size and type are all required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        album = get_object_or_404(Album, pk=album_id, deleted_at__isnull=True)
        storage_key = build_storage_key(album.id, original_filename)

        media = Media.objects.create(
            album=album,
            type=media_type,
            original_filename=original_filename,
            storage_key=storage_key,
            size=size,
            content_type=content_type,
        )

        upload_url = generate_presigned_upload_url(storage_key, content_type)

        return Response(
            {"media": MediaSerializer(media).data, "upload_url": upload_url},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """
        Step 2: the frontend calls this once the PUT to the presigned URL
        succeeded, so the worker can generate the thumbnail asynchronously.
        """
        media = self.get_object()
        generate_thumbnail.delay(media.id)
        return Response(MediaSerializer(media).data)

    def perform_destroy(self, media):
        media.deleted_at = timezone.now()
        media.save(update_fields=["deleted_at"])