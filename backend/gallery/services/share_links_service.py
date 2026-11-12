"""
Resolves a public share-link token into an Album, enforcing validity and
the optional password. Kept out of the view so the same logic can be reused
(e.g. from a management command or a future rate-limiting layer) without
depending on request/response objects.
"""

from rest_framework.exceptions import NotFound, PermissionDenied

from ..models import Album, ShareLink
from ..utils.constants import SHARE_LINK_NOT_FOUND_MESSAGE


def resolve_share_link(token: str, password: str | None = None) -> Album:
    try:
        # album__cover is joined here because the serializer needs the cover's
        # thumbnail key, and reading it lazily would cost one more query.
        link = ShareLink.objects.select_related("album__cover").get(token=token)
    except ShareLink.DoesNotExist:
        raise NotFound(SHARE_LINK_NOT_FOUND_MESSAGE)

    if not link.is_valid:
        raise NotFound(SHARE_LINK_NOT_FOUND_MESSAGE)

    if link.album.is_deleted:
        raise NotFound(SHARE_LINK_NOT_FOUND_MESSAGE)

    if link.password_hash and not link.check_password(password or ""):
        raise PermissionDenied("Incorrect password.")

    return link.album
