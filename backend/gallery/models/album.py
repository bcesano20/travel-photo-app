from django.db import models
from django.utils.text import slugify


class Album(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    # Referenced as a string because Media is defined in another module
    # (avoids a circular import between the two model files).
    cover = models.ForeignKey(
        "Media",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cover_of",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-start_date", "-created_at"]

    def __str__(self):
        return self.name

    # This is to avoid create Albums with the same slug, media url for the location like `viajes/bariloche`
    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            slug = base
            i = 1
            while Album.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                i += 1
                slug = f"{base}-{i}"
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def is_deleted(self):
        return self.deleted_at is not None
