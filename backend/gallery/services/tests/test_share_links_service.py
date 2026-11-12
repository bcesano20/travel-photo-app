from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from gallery.services import resolve_share_link
from gallery.utils.constants import SHARE_LINK_NOT_FOUND_MESSAGE
from gallery.utils.test_utils import (
    FAST_PASSWORD_HASHERS,
    SAMPLE_SHARE_PASSWORD,
    WRONG_SHARE_PASSWORD,
    create_album,
    create_media,
    create_share_link,
)

NOW = "django.utils.timezone.now"


def make_dead_links():
    """One link per reason why a link stops working, keyed by that reason."""
    revoked = create_share_link(password=SAMPLE_SHARE_PASSWORD, is_active=False)
    expired = create_share_link(
        password=SAMPLE_SHARE_PASSWORD,
        expires_at=timezone.now() - timedelta(minutes=1),
    )
    deleted = create_share_link(password=SAMPLE_SHARE_PASSWORD)
    deleted.album.deleted_at = timezone.now()
    deleted.album.save(update_fields=["deleted_at"])
    return {"revoked": revoked, "expired": expired, "deleted album": deleted}


@override_settings(PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)
class ResolveValidLinkTests(TestCase):
    def test_returns_the_album_of_the_link(self):
        link = create_share_link()

        album = resolve_share_link(link.token)

        self.assertEqual(album.pk, link.album.pk)
        self.assertEqual(album.name, link.album.name)

    def test_each_link_resolves_to_its_own_album(self):
        first = create_share_link(album=create_album("Primero"))
        second = create_share_link(album=create_album("Segundo"))

        self.assertEqual(resolve_share_link(first.token).name, "Primero")
        self.assertEqual(resolve_share_link(second.token).name, "Segundo")

    def test_two_links_to_the_same_album_both_work(self):
        album = create_album()
        first = create_share_link(album=album)
        second = create_share_link(album=album)

        self.assertEqual(resolve_share_link(first.token).pk, album.pk)
        self.assertEqual(resolve_share_link(second.token).pk, album.pk)

    def test_link_without_password_ignores_any_password_sent(self):
        link = create_share_link()

        self.assertEqual(resolve_share_link(link.token).pk, link.album.pk)
        self.assertEqual(resolve_share_link(link.token, password="").pk, link.album.pk)
        self.assertEqual(
            resolve_share_link(link.token, password=WRONG_SHARE_PASSWORD).pk,
            link.album.pk,
        )

    def test_link_with_a_future_expiration_is_valid(self):
        link = create_share_link(expires_at=timezone.now() + timedelta(days=7))

        self.assertEqual(resolve_share_link(link.token).pk, link.album.pk)

    def test_link_is_still_valid_at_the_exact_expiration_instant(self):
        expires_at = timezone.now()
        link = create_share_link(expires_at=expires_at)

        with patch(NOW, return_value=expires_at):
            album = resolve_share_link(link.token)

        self.assertEqual(album.pk, link.album.pk)

    def test_link_stops_working_right_after_its_expiration(self):
        expires_at = timezone.now()
        link = create_share_link(expires_at=expires_at)

        with patch(NOW, return_value=expires_at + timedelta(microseconds=1)):
            with self.assertRaises(NotFound):
                resolve_share_link(link.token)

    def test_album_cover_is_loaded_in_the_same_query(self):
        # The public serializer reads the cover's thumbnail key; joining it here
        # avoids one extra query per request.
        album = create_album()
        album.cover = create_media(album)
        album.save()
        link = create_share_link(album=album)

        with self.assertNumQueries(1):
            resolved = resolve_share_link(link.token)
            cover_key = resolved.cover.storage_key

        self.assertEqual(cover_key, album.cover.storage_key)

    def test_album_without_cover_resolves_in_one_query(self):
        link = create_share_link()

        with self.assertNumQueries(1):
            resolved = resolve_share_link(link.token)

        self.assertIsNone(resolved.cover)


@override_settings(PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)
class ResolveNotFoundTests(TestCase):
    def assertNotFound(self, token, password=None):
        with self.assertRaises(NotFound) as caught:
            resolve_share_link(token, password=password)
        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(str(caught.exception.detail), SHARE_LINK_NOT_FOUND_MESSAGE)

    def test_unknown_token(self):
        self.assertNotFound("this-token-does-not-exist")

    def test_empty_token(self):
        self.assertNotFound("")

    def test_partial_token_does_not_match(self):
        link = create_share_link()

        self.assertNotFound(link.token[:-1])
        self.assertNotFound(link.token + "x")

    def test_token_is_case_sensitive(self):
        link = create_share_link()

        self.assertNotFound(link.token.swapcase())

    def test_revoked_link(self):
        link = create_share_link(is_active=False)

        self.assertNotFound(link.token)

    def test_expired_link(self):
        link = create_share_link(expires_at=timezone.now() - timedelta(seconds=1))

        self.assertNotFound(link.token)

    def test_link_of_a_soft_deleted_album(self):
        link = create_share_link()
        link.album.deleted_at = timezone.now()
        link.album.save(update_fields=["deleted_at"])

        self.assertNotFound(link.token)

    def test_every_reason_gives_the_same_error(self):
        # Visitors must not be able to tell a revoked link from an expired one
        # or a deleted album from a token that never existed.
        links = make_dead_links()

        for reason, link in links.items():
            with self.subTest(reason=reason):
                self.assertNotFound(link.token, password=SAMPLE_SHARE_PASSWORD)
        with self.subTest(reason="unknown token"):
            self.assertNotFound("this-token-does-not-exist")

    def test_dead_link_never_reveals_that_it_had_a_password(self):
        # The validity checks run before the password check, so a wrong or
        # missing password on a dead link is "not found", never "forbidden".
        links = make_dead_links()

        for reason, link in links.items():
            for password in (None, "", WRONG_SHARE_PASSWORD):
                with self.subTest(reason=reason, password=password):
                    self.assertNotFound(link.token, password=password)


@override_settings(PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)
class ResolvePasswordTests(TestCase):
    def setUp(self):
        self.link = create_share_link(password=SAMPLE_SHARE_PASSWORD)

    def assertForbidden(self, password):
        with self.assertRaises(PermissionDenied) as caught:
            resolve_share_link(self.link.token, password=password)
        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(str(caught.exception.detail), "Incorrect password.")

    def test_correct_password_returns_the_album(self):
        album = resolve_share_link(self.link.token, password=SAMPLE_SHARE_PASSWORD)

        self.assertEqual(album.pk, self.link.album.pk)

    def test_missing_password_is_forbidden(self):
        self.assertForbidden(None)

    def test_empty_password_is_forbidden(self):
        self.assertForbidden("")

    def test_wrong_password_is_forbidden(self):
        self.assertForbidden(WRONG_SHARE_PASSWORD)

    def test_password_is_case_sensitive(self):
        self.assertForbidden(SAMPLE_SHARE_PASSWORD.upper())

    def test_password_must_match_exactly(self):
        self.assertForbidden(SAMPLE_SHARE_PASSWORD + " ")
        self.assertForbidden(SAMPLE_SHARE_PASSWORD[:-1])

    def test_the_stored_hash_is_not_accepted_as_a_password(self):
        # Defends against treating password_hash as if it were the password.
        self.assertForbidden(self.link.password_hash)

    def test_password_of_another_link_is_not_accepted(self):
        create_share_link(password=WRONG_SHARE_PASSWORD)

        self.assertForbidden(WRONG_SHARE_PASSWORD)
