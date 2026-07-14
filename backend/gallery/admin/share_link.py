from django.contrib import admin

from ..models import ShareLink


@admin.register(ShareLink)
class ShareLinkAdmin(admin.ModelAdmin):
    list_display = ["album", "token", "is_active", "expires_at", "created_at"]
    readonly_fields = ["token"]
