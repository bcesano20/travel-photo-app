from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..serializers import AlbumDetailSerializer
from ..services import resolve_share_link


class PublicAlbumView(APIView):
    """
    The one endpoint a visitor ever hits. No auth at all — access is
    entirely governed by the token (and password, if the link has one).
    """

    permission_classes = [AllowAny]

    def get(self, request, token):
        album = resolve_share_link(token, password=request.query_params.get("password"))
        return Response(AlbumDetailSerializer(album).data)

    def post(self, request, token):
        # Same check as GET, but takes the password from the body instead
        # of the query string — used by the "this album is protected" form,
        # so the password doesn't end up sitting in server/proxy access logs.
        album = resolve_share_link(token, password=request.data.get("password"))
        return Response(AlbumDetailSerializer(album).data)