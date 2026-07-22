from rest_framework import serializers

from gallery.models import Media
from gallery.services.storage_service import generate_presigned_download_url


class MediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Media
        fields = [
            "id",
            "album",
            "type",
            "original_filename",
            "storage_key",
            "thumbnail_key",
            "thumbnail_url",   
            "file_url",       
            "size",
            "content_type",
            "width",
            "height",
            "duration",
            "taken_at",
            "order",
            "processing_status",
            "created_at",
        ]
        # storage_key / thumbnail_key / processing_status are set by the
        # backend during the upload flow (presigned URL) and by the
        # thumbnail worker, never sent by the client.
        read_only_fields = [
            "storage_key",
            "thumbnail_key",
            "processing_status",
            "created_at",
        ]

    def get_thumbnail_url(self, obj):
        return generate_presigned_download_url(obj.thumbnail_key) if obj.thumbnail_key else None
 
    def get_file_url(self, obj):
        return generate_presigned_download_url(obj.storage_key)