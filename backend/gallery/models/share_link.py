import secrets

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone

from .album import Album


class ShareLink(models.Model):
    album = models.ForeignKey(
        Album, on_delete=models.CASCADE, related_name="share_links"
    )
    token = models.CharField(max_length=64, unique=True, editable=False)
    password_hash = models.CharField(max_length=128, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password) if raw_password else ""

    def check_password(self, raw_password):
        if not self.password_hash:
            return True
        return check_password(raw_password, self.password_hash)

    @property
    def is_valid(self):
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    def __str__(self):
        status = "active" if self.is_valid else "inactive"
        return f"Share link for {self.album.name} ({status})"
