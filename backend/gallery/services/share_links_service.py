"""
Resolves a public share-link token into an Album, enforcing validity and
the optional password. Kept out of the view so the same logic can be reused
(e.g. from a management command or a future rate-limiting layer) without
depending on request/response objects.
"""

from rest_framework.exceptions import NotFound, PermissionDenied

from ..constants import SHARE_LINK_NOT_FOUND_MESSAGE
from ..models import Album, ShareLink


def resolve_share_link(token: str, password: str | None = None) -> Album:
    try:
        link = ShareLink.objects.select_related("album").get(token=token)
    except ShareLink.DoesNotExist:
        raise NotFound(SHARE_LINK_NOT_FOUND_MESSAGE)

    if not link.is_valid:
        raise NotFound(SHARE_LINK_NOT_FOUND_MESSAGE)

    if link.album.is_deleted:
        raise NotFound(SHARE_LINK_NOT_FOUND_MESSAGE)

    if link.password_hash and not link.check_password(password or ""):
        raise PermissionDenied("Incorrect password.")

    return link.album