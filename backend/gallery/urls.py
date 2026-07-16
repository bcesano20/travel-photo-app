from django.urls import include, path

from rest_framework.routers import DefaultRouter

from gallery.views import AlbumViewSet, MediaViewSet, PublicAlbumView, ShareLinkViewSet

router = DefaultRouter()
router.register("albums", AlbumViewSet, basename="album")
router.register("media", MediaViewSet, basename="media")
router.register("share-links", ShareLinkViewSet, basename="share-link")

urlpatterns = [
    # Private, JWT-authenticated CRUD (albums, media, share-links)
    path("", include(router.urls)),
    # Public, token-only read access — this is what the public gallery hits
    path("public/albums/<str:token>/", PublicAlbumView.as_view(), name="public-album"),
]
