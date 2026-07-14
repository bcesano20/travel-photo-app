from django.contrib import admin

from ..models import Media


# This make the Media editable in the Album admin panel
class MediaInline(admin.TabularInline):
    model = Media
    extra = 0
    fields = ["type", "original_filename", "size", "processing_status", "order"]
    readonly_fields = ["size", "processing_status"]


@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    list_display = ["original_filename", "album", "type", "processing_status", "size"]
    list_filter = ["type", "processing_status"]
    search_fields = ["original_filename", "storage_key"]
