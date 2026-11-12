"""
Shared constants and helpers for the gallery tests.

Nothing here talks to the network: the R2 values are fake, and presigned URLs
are signed locally by boto3 (signing needs no request to the bucket).
"""

import uuid
from urllib.parse import parse_qs, urlparse

from django.db import connection
from django.test import SimpleTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APITestCase

from gallery.models import Album, CustomUser, Media, ShareLink
from gallery.services.storage_service import get_r2_client

# ---- Fake Cloudflare R2 configuration ----

TEST_R2_ACCOUNT_ID = "test-account"
TEST_R2_ACCESS_KEY_ID = "test-access-key"
TEST_R2_SECRET_ACCESS_KEY = "test-secret-key"
TEST_R2_BUCKET_NAME = "test-bucket"
TEST_R2_ENDPOINT_URL = f"https://{TEST_R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

TEST_R2_SETTINGS = {
    "R2_ACCOUNT_ID": TEST_R2_ACCOUNT_ID,
    "R2_ACCESS_KEY_ID": TEST_R2_ACCESS_KEY_ID,
    "R2_SECRET_ACCESS_KEY": TEST_R2_SECRET_ACCESS_KEY,
    "R2_BUCKET_NAME": TEST_R2_BUCKET_NAME,
}

# ---- Sample storage data ----

SAMPLE_ALBUM_ID = 7
SAMPLE_STORAGE_KEY = f"albums/{SAMPLE_ALBUM_ID}/0123456789abcdef0123456789abcdef.jpg"
SAMPLE_THUMBNAIL_KEY = (
    f"albums/{SAMPLE_ALBUM_ID}/0123456789abcdef0123456789abcdef-thumb.jpg"
)
SAMPLE_CONTENT_TYPE = "image/jpeg"
SAMPLE_BYTES = b"\xff\xd8\xff\xe0 fake jpeg bytes"


# ---- Share links ----

# Includes non-ASCII characters on purpose: passwords are typed by a person.
SAMPLE_SHARE_PASSWORD = "clave-ñú-123"
WRONG_SHARE_PASSWORD = "otra-clave"

# Django's default hasher (PBKDF2) is deliberately slow, about a third of a
# second per hash. Tests that create password-protected links apply this with
# `@override_settings(PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)`. Never use MD5 for
# real passwords: this is for tests only.
FAST_PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


# ---- Model factories (they hit the database: use them in TestCase) ----
def create_album(name="Viaje a Barcelona", **kwargs) -> Album:
    return Album.objects.create(name=name, **kwargs)


def create_media(album: Album, **kwargs) -> Media:
    """A ready photo. `storage_key` is unique per call, as the model requires."""
    test_media = {
        "type": Media.TYPE_PHOTO,
        "original_filename": "photo.jpg",
        "storage_key": f"albums/{album.id}/{uuid.uuid4().hex}.jpg",
        "size": 1024,
        "content_type": "image/jpeg",
        "processing_status": Media.STATUS_READY,
    }
    test_media.update(kwargs)
    return Media.objects.create(album=album, **test_media)


def create_share_link(album=None, password=None, **kwargs) -> ShareLink:
    """
    A share link for `album` (a new album if omitted). Pass `password` to
    protect it; other fields (`is_active`, `expires_at`...) go in `kwargs`.
    """
    link = ShareLink(album=album or create_album(), **kwargs)
    if password:
        link.set_password(password)
    link.save()
    return link


def create_user(email="admin@example.com", **kwargs) -> CustomUser:
    """The single admin. No password is set (so nothing is hashed): tests
    authenticate with `client.force_authenticate`."""
    return CustomUser.objects.create_user(
        username=kwargs.pop("username", "admin"), email=email, **kwargs
    )


def soft_delete(obj, when=None):
    """Marks an Album or Media as deleted the way the API does (`deleted_at`)."""
    obj.deleted_at = when or timezone.now()
    obj.save(update_fields=["deleted_at"])


def count_queries(func) -> int:
    """Runs `func()` and returns how many SQL queries it executed."""
    with CaptureQueriesContext(connection) as queries:
        func()
    return len(queries)


class R2SettingsMixin:
    """
    Gives a test case the fake R2 setup:

    - Overrides the R2 settings with fake values, so tests never depend on the
      real credentials in `.env`.
    - Clears the cached boto3 client before and after every test. The client is
      memoized per process (`@lru_cache`), so without this a client built with
      one test's settings or mocks would leak into the next test.

    Put it BEFORE the Django test class: `class T(R2SettingsMixin, TestCase)`.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._r2_settings = override_settings(**TEST_R2_SETTINGS)
        cls._r2_settings.enable()

    @classmethod
    def tearDownClass(cls):
        cls._r2_settings.disable()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        get_r2_client.cache_clear()
        self.addCleanup(get_r2_client.cache_clear)


class R2TestCase(R2SettingsMixin, SimpleTestCase):
    """For tests of the storage service. It is a SimpleTestCase on purpose: no
    database is created or touched."""


class AuthenticatedAPITestCase(R2SettingsMixin, APITestCase):
    """
    For tests of the private (admin) API: fake R2 settings, plus `self.user`
    already authenticated on `self.client`. Use `self.client.force_authenticate(
    user=None)` to test the unauthenticated case.
    """

    def setUp(self):
        super().setUp()
        self.user = create_user()
        self.client.force_authenticate(user=self.user)


class PublicAPITestCase(R2SettingsMixin, APITestCase):
    """
    For tests of the public (share-link) API: fake R2 settings and an anonymous
    `self.client`, exactly like a visitor (no JWT, no `force_authenticate`).
    """


def parse_presigned_url(url: str) -> dict:
    """
    Splits a presigned URL into the parts the tests assert on. Query values are
    flattened (`{"X-Amz-Expires": "900"}`) because every signing parameter
    appears exactly once.
    """
    parsed = urlparse(url)
    return {
        "scheme": parsed.scheme,
        "host": parsed.netloc,
        "path": parsed.path,
        "query": {key: values[0] for key, values in parse_qs(parsed.query).items()},
    }
