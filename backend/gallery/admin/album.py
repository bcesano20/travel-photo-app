from django.contrib import admin

from ..models import Album
from .media import MediaInline


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ["name", "start_date", "end_date", "created_at", "deleted_at"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MediaInline]
