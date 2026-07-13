from django.db import models

from ..constants import (
    MEDIA_STATUS_CHOICES,
    MEDIA_STATUS_ERROR,
    MEDIA_STATUS_PENDING,
    MEDIA_STATUS_READY,
    MEDIA_TYPE_CHOICES,
    MEDIA_TYPE_PHOTO,
    MEDIA_TYPE_VIDEO,
)
from .album import Album


class Media(models.Model):
    TYPE_PHOTO = MEDIA_TYPE_PHOTO
    TYPE_VIDEO = MEDIA_TYPE_VIDEO
    TYPE_CHOICES = MEDIA_TYPE_CHOICES

    STATUS_PENDING = MEDIA_STATUS_PENDING
    STATUS_READY = MEDIA_STATUS_READY
    STATUS_ERROR = MEDIA_STATUS_ERROR
    STATUS_CHOICES = MEDIA_STATUS_CHOICES

    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="media")

    type = models.CharField(max_length=10, choices=TYPE_CHOICES)

    original_filename = models.CharField(max_length=255)

    # The actual key/path of the file in the bucket (R2/B2). Without this
    # there is no way to locate the original file: the filename alone isn't
    # enough because storage keys are generated as UUIDs to avoid collisions.
    storage_key = models.CharField(max_length=500, unique=True)
    thumbnail_key = models.CharField(max_length=500, blank=True)

    size = models.PositiveBigIntegerField(help_text="Size in bytes")
    content_type = models.CharField(max_length=100)

    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    duration = models.PositiveIntegerField(
        null=True, blank=True, help_text="Duration in seconds (video only)"
    )

    taken_at = models.DateTimeField(
        null=True, blank=True, help_text="Actual capture date of the photo/video (EXIF)"
    )
    order = models.PositiveIntegerField(default=0)

    processing_status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING
    )

    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["order", "taken_at", "created_at"]
        indexes = [
            models.Index(fields=["album", "type"]),
        ]

    def __str__(self):
        return f"{self.original_filename} ({self.type})"

    @property
    def is_video(self):
        return self.type == self.TYPE_VIDEO
