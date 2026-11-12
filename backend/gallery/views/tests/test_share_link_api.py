"""
Tests for the private share-link API (`ShareLinkViewSet`): create, list, revoke,
change password / expiration, delete.

NOTE about `gallery/utils/test_utils.py`: another agent is editing that file, so
everything new that these tests needed is defined HERE, at the top of the file.
If you want to share it with other test modules, these are good candidates to
move there:

- `SHARE_LINK_FIELDS` and `SUB_ALBUM_LINK_ERROR` (expected API contract),
- the URL helpers `list_url`, `detail_url`, `public_url`,
- `public_get` / `public_post` (an anonymous client hitting the public gallery
  endpoint, useful to prove that a change in the private API has the effect a
  visitor sees). `PublicAPITestCase` in test_utils may already cover part of it.
"""

import re
from unittest import expectedFailure

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from gallery.models import ShareLink
from gallery.utils.test_utils import (
    FAST_PASSWORD_HASHERS,
    SAMPLE_SHARE_PASSWORD,
    WRONG_SHARE_PASSWORD,
    AuthenticatedAPITestCase,
    create_album,
    create_share_link,
    soft_delete,
)

SHARE_LINK_FIELDS = {
    "id",
    "album",
    "token",
    "expires_at",
    "is_active",
    "created_at",
    "url",
}
SUB_ALBUM_LINK_ERROR = (
    "Los sub-álbumes no tienen enlace propio — compartí el álbum principal."
)
# secrets.token_urlsafe(32): 32 random bytes, base64url, no padding.
TOKEN_FORMAT = re.compile(r"^[A-Za-z0-9_-]{43}$")
PAST = "2020-01-01T00:00:00Z"
FUTURE = "2999-01-01T00:00:00Z"


def list_url():
    return reverse("share-link-list")


def detail_url(link_id):
    return reverse("share-link-detail", args=[link_id])


def public_url(token):
    return reverse("public-album", args=[token])


def public_get(token):
    """What a visitor sees: an anonymous request to the public gallery."""
    return APIClient().get(public_url(token))


def public_post(token, password):
    return APIClient().post(public_url(token), {"password": password}, format="json")


class ShareLinkAuthenticationTests(APITestCase):
    """Without a JWT nobody can create, list, revoke or delete links."""

    def test_every_endpoint_requires_authentication(self):
        link = create_share_link()
        requests = [
            ("get", list_url()),
            ("post", list_url()),
            ("get", detail_url(link.pk)),
            ("put", detail_url(link.pk)),
            ("patch", detail_url(link.pk)),
            ("delete", detail_url(link.pk)),
        ]

        for method, url in requests:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, {}, format="json")

                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejected_requests_change_nothing(self):
        link = create_share_link()

        self.client.patch(detail_url(link.pk), {"is_active": False}, format="json")
        self.client.delete(detail_url(link.pk))
        self.client.post(list_url(), {"album": link.album_id}, format="json")

        link.refresh_from_db()
        self.assertTrue(link.is_active)
        self.assertEqual(ShareLink.objects.count(), 1)


@override_settings(PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)
class ShareLinkListTests(AuthenticatedAPITestCase):
    def test_empty_list(self):
        response = self.client.get(list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [])

    def test_returns_the_link_fields(self):
        link = create_share_link()

        item = self.client.get(list_url()).json()[0]

        self.assertEqual(set(item), SHARE_LINK_FIELDS)
        self.assertEqual(item["id"], link.pk)
        self.assertEqual(item["album"], link.album_id)
        self.assertEqual(item["token"], link.token)
        self.assertTrue(item["is_active"])
        self.assertIsNone(item["expires_at"])

    def test_the_url_is_the_relative_public_path(self):
        link = create_share_link()

        item = self.client.get(list_url()).json()[0]

        self.assertEqual(item["url"], f"/gallery/{link.token}")

    def test_the_owner_also_sees_revoked_and_expired_links(self):
        # The admin manages every link; only the public side hides dead ones.
        create_share_link(is_active=False)
        create_share_link(expires_at="2020-01-01T00:00:00Z")
        create_share_link()

        links = self.client.get(list_url()).json()

        self.assertEqual(len(links), 3)
        self.assertEqual(
            sorted(link["is_active"] for link in links), [False, True, True]
        )

    def test_password_and_hash_are_never_returned(self):
        create_share_link(password=SAMPLE_SHARE_PASSWORD)

        response = self.client.get(list_url())

        item = response.json()[0]
        self.assertNotIn("password", item)
        self.assertNotIn("password_hash", item)
        self.assertNotIn(SAMPLE_SHARE_PASSWORD, response.content.decode())

    def test_can_filter_by_album(self):
        mine = create_album("Mío")
        other = create_album("Otro")
        wanted = create_share_link(album=mine)
        create_share_link(album=mine, is_active=False)
        create_share_link(album=other)

        links = self.client.get(list_url(), {"album": mine.pk}).json()

        self.assertEqual(len(links), 2)
        self.assertEqual({link["album"] for link in links}, {mine.pk})
        self.assertIn(wanted.pk, [link["id"] for link in links])

    def test_filtering_by_an_album_without_links_is_empty(self):
        create_share_link()
        lonely = create_album("Sin enlaces")

        response = self.client.get(list_url(), {"album": lonely.pk})

        self.assertEqual(response.json(), [])

    def test_without_a_filter_every_album_is_listed(self):
        create_share_link(album=create_album("Uno"))
        create_share_link(album=create_album("Dos"))

        self.assertEqual(len(self.client.get(list_url()).json()), 2)

    def test_the_list_is_one_query_however_many_links_there_are(self):
        album = create_album()
        for _ in range(6):
            create_share_link(album=album)

        with self.assertNumQueries(1):
            response = self.client.get(list_url())

        self.assertEqual(len(response.json()), 6)


class ShareLinkRetrieveTests(AuthenticatedAPITestCase):
    def test_returns_the_link(self):
        link = create_share_link(expires_at="2999-01-01T00:00:00Z")

        response = self.client.get(detail_url(link.pk))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.json()), SHARE_LINK_FIELDS)
        self.assertEqual(response.json()["token"], link.token)
        self.assertTrue(response.json()["expires_at"].startswith("2999-01-01"))

    def test_unknown_link_is_404(self):
        response = self.client.get(detail_url(999999))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@override_settings(PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)
class ShareLinkCreateTests(AuthenticatedAPITestCase):
    def post(self, data):
        return self.client.post(list_url(), data, format="json")

    def test_creates_an_open_link_from_just_the_album(self):
        album = create_album()

        response = self.post({"album": album.pk})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(set(data), SHARE_LINK_FIELDS)
        self.assertEqual(data["album"], album.pk)
        self.assertTrue(data["is_active"])
        self.assertIsNone(data["expires_at"])
        link = ShareLink.objects.get(pk=data["id"])
        self.assertEqual(link.password_hash, "")
        self.assertEqual(data["url"], f"/gallery/{data['token']}")

    def test_the_token_is_a_random_urlsafe_string(self):
        album = create_album()

        first = self.post({"album": album.pk}).json()["token"]
        second = self.post({"album": album.pk}).json()["token"]

        self.assertRegex(first, TOKEN_FORMAT)
        self.assertRegex(second, TOKEN_FORMAT)
        self.assertNotEqual(first, second)

    def test_the_client_cannot_choose_the_token(self):
        album = create_album()

        response = self.post({"album": album.pk, "token": "mi-token-elegido"})

        self.assertNotEqual(response.json()["token"], "mi-token-elegido")
        self.assertFalse(ShareLink.objects.filter(token="mi-token-elegido").exists())

    def test_created_at_cannot_be_set(self):
        response = self.post({"album": create_album().pk, "created_at": PAST})

        link = ShareLink.objects.get(pk=response.json()["id"])
        self.assertGreater(link.created_at.year, 2020)

    def test_saves_the_expiration_date(self):
        response = self.post({"album": create_album().pk, "expires_at": FUTURE})

        link = ShareLink.objects.get(pk=response.json()["id"])
        self.assertEqual(link.expires_at.year, 2999)

    def test_the_password_is_stored_hashed_and_never_returned(self):
        response = self.post(
            {"album": create_album().pk, "password": SAMPLE_SHARE_PASSWORD}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("password", response.json())
        self.assertNotIn(SAMPLE_SHARE_PASSWORD, response.content.decode())
        link = ShareLink.objects.get(pk=response.json()["id"])
        self.assertNotEqual(link.password_hash, "")
        self.assertNotIn(SAMPLE_SHARE_PASSWORD, link.password_hash)
        self.assertTrue(link.check_password(SAMPLE_SHARE_PASSWORD))
        self.assertFalse(link.check_password(WRONG_SHARE_PASSWORD))

    def test_an_empty_password_means_no_protection(self):
        response = self.post({"album": create_album().pk, "password": ""})

        link = ShareLink.objects.get(pk=response.json()["id"])
        self.assertEqual(link.password_hash, "")

    def test_the_album_is_required(self):
        response = self.post({})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("album", response.json())
        self.assertEqual(ShareLink.objects.count(), 0)

    def test_the_album_must_exist(self):
        response = self.post({"album": 999999})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("album", response.json())

    def test_sub_albums_cannot_be_shared_on_their_own(self):
        parent = create_album("Madre")
        child = create_album("Hija", parent=parent)

        response = self.post({"album": child.pk})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["album"], [SUB_ALBUM_LINK_ERROR])
        self.assertEqual(ShareLink.objects.count(), 0)

    def test_the_new_link_opens_the_album_for_a_visitor(self):
        album = create_album("Viaje a Bariloche")

        token = self.post({"album": album.pk}).json()["token"]

        response = public_get(token)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["id"], album.pk)

    def test_a_link_created_with_a_password_asks_visitors_for_it(self):
        album = create_album()
        token = self.post(
            {"album": album.pk, "password": SAMPLE_SHARE_PASSWORD}
        ).json()["token"]

        self.assertEqual(public_get(token).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            public_post(token, WRONG_SHARE_PASSWORD).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        opened = public_post(token, SAMPLE_SHARE_PASSWORD)
        self.assertEqual(opened.status_code, status.HTTP_200_OK)
        self.assertEqual(opened.json()["id"], album.pk)


@override_settings(PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)
class ShareLinkUpdateTests(AuthenticatedAPITestCase):
    def patch(self, link, data):
        return self.client.patch(detail_url(link.pk), data, format="json")

    def test_revoking_a_link_closes_it_for_visitors(self):
        # Revoke = PATCH is_active=false on /api/share-links/<id>/ (the album and
        # its media are untouched). Note: the frontend currently builds
        # ".../share-links//<id>/" (double slash), which does not match any
        # route, so this exact URL is what its button needs to call.
        link = create_share_link()
        self.assertEqual(public_get(link.token).status_code, status.HTTP_200_OK)

        response = self.patch(link, {"is_active": False})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.json()["is_active"])
        self.assertEqual(public_get(link.token).status_code, status.HTTP_404_NOT_FOUND)
        link.album.refresh_from_db()
        self.assertIsNone(link.album.deleted_at)

    def test_revoking_one_link_leaves_the_other_links_of_the_album_working(self):
        album = create_album()
        revoked = create_share_link(album=album)
        kept = create_share_link(album=album)

        self.patch(revoked, {"is_active": False})

        self.assertEqual(
            public_get(revoked.token).status_code, status.HTTP_404_NOT_FOUND
        )
        self.assertEqual(public_get(kept.token).status_code, status.HTTP_200_OK)

    def test_a_revoked_link_can_be_reactivated(self):
        link = create_share_link(is_active=False)

        self.patch(link, {"is_active": True})

        self.assertEqual(public_get(link.token).status_code, status.HTTP_200_OK)

    def test_setting_a_past_expiration_closes_the_link(self):
        link = create_share_link()

        self.patch(link, {"expires_at": PAST})

        self.assertEqual(public_get(link.token).status_code, status.HTTP_404_NOT_FOUND)

    def test_clearing_the_expiration_reopens_the_link(self):
        link = create_share_link(expires_at=PAST)

        response = self.patch(link, {"expires_at": None})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.json()["expires_at"])
        self.assertEqual(public_get(link.token).status_code, status.HTTP_200_OK)

    def test_a_password_can_be_added_to_an_open_link(self):
        link = create_share_link()

        response = self.patch(link, {"password": SAMPLE_SHARE_PASSWORD})

        self.assertNotIn("password", response.json())
        self.assertEqual(public_get(link.token).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            public_post(link.token, SAMPLE_SHARE_PASSWORD).status_code,
            status.HTTP_200_OK,
        )

    def test_the_password_can_be_changed(self):
        link = create_share_link(password=SAMPLE_SHARE_PASSWORD)

        self.patch(link, {"password": WRONG_SHARE_PASSWORD})

        self.assertEqual(
            public_post(link.token, SAMPLE_SHARE_PASSWORD).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            public_post(link.token, WRONG_SHARE_PASSWORD).status_code,
            status.HTTP_200_OK,
        )

    def test_an_empty_password_removes_the_protection(self):
        link = create_share_link(password=SAMPLE_SHARE_PASSWORD)

        self.patch(link, {"password": ""})

        link.refresh_from_db()
        self.assertEqual(link.password_hash, "")
        self.assertEqual(public_get(link.token).status_code, status.HTTP_200_OK)

    def test_not_sending_a_password_keeps_the_current_one(self):
        link = create_share_link(password=SAMPLE_SHARE_PASSWORD)

        self.patch(link, {"is_active": True})

        self.assertEqual(public_get(link.token).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            public_post(link.token, SAMPLE_SHARE_PASSWORD).status_code,
            status.HTTP_200_OK,
        )

    def test_the_token_cannot_be_changed(self):
        link = create_share_link()
        original = link.token

        response = self.patch(link, {"token": "otro-token"})

        self.assertEqual(response.json()["token"], original)
        link.refresh_from_db()
        self.assertEqual(link.token, original)

    def test_a_link_cannot_be_moved_to_a_sub_album(self):
        link = create_share_link()
        child = create_album("Hija", parent=create_album("Madre"))

        response = self.patch(link, {"album": child.pk})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["album"], [SUB_ALBUM_LINK_ERROR])
        link.refresh_from_db()
        self.assertNotEqual(link.album_id, child.pk)

    def test_put_needs_the_album(self):
        link = create_share_link()

        rejected = self.client.put(detail_url(link.pk), {}, format="json")
        accepted = self.client.put(
            detail_url(link.pk), {"album": link.album_id}, format="json"
        )

        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("album", rejected.json())
        self.assertEqual(accepted.status_code, status.HTTP_200_OK)

    def test_unknown_link_is_404(self):
        response = self.client.patch(
            detail_url(999999), {"is_active": False}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ShareLinkDestroyTests(AuthenticatedAPITestCase):
    def test_deleting_removes_the_link_for_good(self):
        link = create_share_link()

        response = self.client.delete(detail_url(link.pk))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ShareLink.objects.filter(pk=link.pk).exists())

    def test_a_deleted_link_stops_working_for_visitors(self):
        link = create_share_link()
        self.assertEqual(public_get(link.token).status_code, status.HTTP_200_OK)

        self.client.delete(detail_url(link.pk))

        self.assertEqual(public_get(link.token).status_code, status.HTTP_404_NOT_FOUND)

    def test_the_album_and_other_links_are_kept(self):
        album = create_album()
        gone = create_share_link(album=album)
        stays = create_share_link(album=album)

        self.client.delete(detail_url(gone.pk))

        album.refresh_from_db()
        self.assertIsNone(album.deleted_at)
        self.assertTrue(ShareLink.objects.filter(pk=stays.pk).exists())
        self.assertEqual(public_get(stays.token).status_code, status.HTTP_200_OK)

    def test_deleting_twice_is_404(self):
        link = create_share_link()
        self.client.delete(detail_url(link.pk))

        response = self.client.delete(detail_url(link.pk))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_link_is_404(self):
        response = self.client.delete(detail_url(999999))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ShareLinkKnownGapTests(AuthenticatedAPITestCase):
    """
    Behaviour the API SHOULD have but does not yet (found while writing these
    tests). They assert the correct behaviour and are marked `expectedFailure`,
    so the suite stays green today. Once the code is fixed a test here becomes an
    "unexpected success" and fails the run: remove its decorator then.
    """

    @expectedFailure
    def test_a_soft_deleted_album_cannot_get_a_new_link(self):
        # Today the link is created (201), but its public URL is always 404.
        album = create_album()
        soft_delete(album)

        response = self.client.post(list_url(), {"album": album.pk}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ShareLink.objects.count(), 0)

    @expectedFailure
    def test_a_malformed_album_filter_is_not_a_server_error(self):
        # Today `?album=abc` raises ValueError (HTTP 500).
        response = self.client.get(list_url(), {"album": "abc"})

        self.assertLess(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
