from django.db.models import Prefetch, prefetch_related_objects
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Album, Media
from ..serializers import AlbumDetailSerializer
from ..services import resolve_share_link


def _serialize_album_tree(album):
    """
    Loads the album's media, its sub-albums and each sub-album's media in 3
    queries total (instead of one media query per sub-album), then serializes.
    AlbumDetailSerializer reads the `active_media` / `active_children`
    attributes set here.
    """
    active_media = Prefetch(
        "media",
        queryset=Media.objects.filter(deleted_at__isnull=True),
        to_attr="active_media",
    )
    active_children = Prefetch(
        "children",
        queryset=Album.objects.filter(deleted_at__isnull=True)
        .select_related("cover")
        .prefetch_related(active_media),
        to_attr="active_children",
    )
    prefetch_related_objects([album], active_media, active_children)
    return AlbumDetailSerializer(album).data


class PublicAlbumView(APIView):
    """
    The one endpoint a visitor ever hits. No auth at all — access is
    entirely governed by the token (and password, if the link has one).
    """

    permission_classes = [AllowAny]

    def get(self, request, token):
        album = resolve_share_link(token, password=request.query_params.get("password"))
        return Response(_serialize_album_tree(album))

    def post(self, request, token):
        # Same check as GET, but takes the password from the body instead
        # of the query string — used by the "this album is protected" form,
        # so the password doesn't end up sitting in server/proxy access logs.
        album = resolve_share_link(token, password=request.data.get("password"))
        return Response(_serialize_album_tree(album))
