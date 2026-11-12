from datetime import date, timedelta

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from gallery.utils.constants import SHARE_LINK_NOT_FOUND_MESSAGE
from gallery.utils.test_utils import (
    FAST_PASSWORD_HASHERS,
    SAMPLE_SHARE_PASSWORD,
    TEST_R2_BUCKET_NAME,
    WRONG_SHARE_PASSWORD,
    PublicAPITestCase,
    count_queries,
    create_album,
    create_media,
    create_share_link,
    parse_presigned_url,
    soft_delete,
)

# Same shape as the admin detail, but sub-albums are full albums (with media).
ALBUM_FIELDS = {
    "id",
    "name",
    "slug",
    "description",
    "start_date",
    "end_date",
    "parent",
    "cover",
    "cover_thumbnail_url",
    "media",
    "children",
    "created_at",
    "updated_at",
}
INCORRECT_PASSWORD = "Incorrect password."


def public_url(token):
    return reverse("public-album", args=[token])


def media_names(album_data):
    return [item["original_filename"] for item in album_data["media"]]


class PublicAlbumAccessTests(PublicAPITestCase):
    """The endpoint needs no login: the token is the only credential."""

    def test_anonymous_visitor_can_open_a_valid_link(self):
        link = create_share_link(album=create_album("Viaje a Bariloche"))

        response = self.client.get(public_url(link.token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["name"], "Viaje a Bariloche")

    def test_the_token_is_the_only_thing_that_selects_the_album(self):
        first = create_share_link(album=create_album("Primero"))
        second = create_share_link(album=create_album("Segundo"))

        self.assertEqual(
            self.client.get(public_url(first.token)).json()["name"], "Primero"
        )
        self.assertEqual(
            self.client.get(public_url(second.token)).json()["name"], "Segundo"
        )

    def test_two_links_to_the_same_album_both_work(self):
        album = create_album()
        first = create_share_link(album=album)
        second = create_share_link(album=album)

        for link in (first, second):
            with self.subTest(token=link.token):
                response = self.client.get(public_url(link.token))

                self.assertEqual(response.json()["id"], album.pk)

    def test_the_view_is_read_only(self):
        link = create_share_link()

        for method in ("put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    public_url(link.token), {}, format="json"
                )

                self.assertEqual(
                    response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
                )

    def test_the_link_can_not_be_used_to_change_the_album(self):
        album = create_album("Intacto")
        link = create_share_link(album=album)

        self.client.patch(public_url(link.token), {"name": "Hackeado"}, format="json")
        self.client.delete(public_url(link.token))

        album.refresh_from_db()
        self.assertEqual(album.name, "Intacto")
        self.assertIsNone(album.deleted_at)


class PublicAlbumContentTests(PublicAPITestCase):
    def test_returns_the_album_fields(self):
        album = create_album(
            "Viaje a Bariloche",
            description="Con amigos",
            start_date=date(2026, 1, 10),
            end_date=date(2026, 1, 20),
        )
        link = create_share_link(album=album)

        data = self.client.get(public_url(link.token)).json()

        self.assertEqual(set(data), ALBUM_FIELDS)
        self.assertEqual(data["id"], album.pk)
        self.assertEqual(data["slug"], "viaje-a-bariloche")
        self.assertEqual(data["description"], "Con amigos")
        self.assertEqual(data["start_date"], "2026-01-10")
        self.assertEqual(data["end_date"], "2026-01-20")
        self.assertIsNone(data["parent"])
        self.assertEqual(data["media"], [])
        self.assertEqual(data["children"], [])

    def test_media_excludes_soft_deleted_files_and_follows_the_manual_order(self):
        album = create_album()
        create_media(album, original_filename="tercera.jpg", order=3)
        create_media(album, original_filename="primera.jpg", order=1)
        create_media(album, original_filename="segunda.jpg", order=2)
        soft_delete(create_media(album, original_filename="borrada.jpg", order=0))
        link = create_share_link(album=album)

        data = self.client.get(public_url(link.token)).json()

        self.assertEqual(
            media_names(data), ["primera.jpg", "segunda.jpg", "tercera.jpg"]
        )

    def test_media_urls_are_presigned_for_the_files_keys(self):
        album = create_album()
        create_media(
            album,
            storage_key="albums/1/foto.jpg",
            thumbnail_key="albums/1/foto-thumb.jpg",
        )
        link = create_share_link(album=album)

        item = self.client.get(public_url(link.token)).json()["media"][0]

        self.assertEqual(
            parse_presigned_url(item["file_url"])["path"],
            f"/{TEST_R2_BUCKET_NAME}/albums/1/foto.jpg",
        )
        self.assertEqual(
            parse_presigned_url(item["thumbnail_url"])["path"],
            f"/{TEST_R2_BUCKET_NAME}/albums/1/foto-thumb.jpg",
        )

    def test_thumbnail_url_is_null_until_the_thumbnail_exists(self):
        album = create_album()
        create_media(album, thumbnail_key="", processing_status="pending")
        link = create_share_link(album=album)

        item = self.client.get(public_url(link.token)).json()["media"][0]

        self.assertIsNone(item["thumbnail_url"])

    def test_cover_thumbnail_url_signs_the_cover_thumbnail_key(self):
        album = create_album()
        album.cover = create_media(album, thumbnail_key="albums/1/portada-thumb.jpg")
        album.save()
        link = create_share_link(album=album)

        data = self.client.get(public_url(link.token)).json()

        self.assertEqual(data["cover"], album.cover.pk)
        self.assertEqual(
            parse_presigned_url(data["cover_thumbnail_url"])["path"],
            f"/{TEST_R2_BUCKET_NAME}/albums/1/portada-thumb.jpg",
        )

    def test_cover_thumbnail_url_is_null_without_a_cover(self):
        link = create_share_link()

        data = self.client.get(public_url(link.token)).json()

        self.assertIsNone(data["cover"])
        self.assertIsNone(data["cover_thumbnail_url"])

    def test_only_the_shared_albums_media_is_returned(self):
        shared = create_album("Compartido")
        create_media(shared, original_filename="mia.jpg")
        create_media(create_album("Privado"), original_filename="ajena.jpg")
        link = create_share_link(album=shared)

        data = self.client.get(public_url(link.token)).json()

        self.assertEqual(media_names(data), ["mia.jpg"])


class PublicAlbumSubAlbumTests(PublicAPITestCase):
    def test_sub_albums_come_with_their_full_media(self):
        # Unlike the admin panel, the public lightbox needs every sub-album file.
        parent = create_album("Madre")
        child = create_album("Hija", parent=parent, description="Un día")
        create_media(child, original_filename="uno.jpg", order=1)
        create_media(child, original_filename="dos.jpg", order=2)
        link = create_share_link(album=parent)

        children = self.client.get(public_url(link.token)).json()["children"]

        self.assertEqual(len(children), 1)
        self.assertEqual(set(children[0]), ALBUM_FIELDS)
        self.assertEqual(children[0]["name"], "Hija")
        self.assertEqual(children[0]["parent"], parent.pk)
        self.assertEqual(children[0]["children"], [])
        self.assertEqual(media_names(children[0]), ["uno.jpg", "dos.jpg"])

    def test_sub_album_media_excludes_soft_deleted_files(self):
        parent = create_album("Madre")
        child = create_album("Hija", parent=parent)
        create_media(child, original_filename="visible.jpg")
        soft_delete(create_media(child, original_filename="borrada.jpg"))
        link = create_share_link(album=parent)

        children = self.client.get(public_url(link.token)).json()["children"]

        self.assertEqual(media_names(children[0]), ["visible.jpg"])

    def test_each_sub_album_keeps_its_own_media(self):
        parent = create_album("Madre")
        first = create_album("Hija 1", parent=parent, start_date=date(2026, 2, 1))
        second = create_album("Hija 2", parent=parent, start_date=date(2026, 1, 1))
        create_media(first, original_filename="de-la-primera.jpg")
        create_media(second, original_filename="de-la-segunda.jpg")
        link = create_share_link(album=parent)

        children = self.client.get(public_url(link.token)).json()["children"]

        by_name = {child["name"]: media_names(child) for child in children}
        self.assertEqual(
            by_name,
            {"Hija 1": ["de-la-primera.jpg"], "Hija 2": ["de-la-segunda.jpg"]},
        )

    def test_the_parents_own_media_is_separate_from_its_sub_albums(self):
        parent = create_album("Madre")
        create_media(parent, original_filename="de-la-madre.jpg")
        create_media(
            create_album("Hija", parent=parent), original_filename="de-la-hija.jpg"
        )
        link = create_share_link(album=parent)

        data = self.client.get(public_url(link.token)).json()

        self.assertEqual(media_names(data), ["de-la-madre.jpg"])
        self.assertEqual(media_names(data["children"][0]), ["de-la-hija.jpg"])

    def test_soft_deleted_sub_albums_are_not_included(self):
        parent = create_album("Madre")
        create_album("Visible", parent=parent)
        soft_delete(create_album("Borrada", parent=parent))
        link = create_share_link(album=parent)

        children = self.client.get(public_url(link.token)).json()["children"]

        self.assertEqual([child["name"] for child in children], ["Visible"])

    def test_sub_albums_of_another_album_are_not_included(self):
        shared = create_album("Compartida")
        create_album("Mía", parent=shared)
        create_album("Ajena", parent=create_album("Otra madre"))
        link = create_share_link(album=shared)

        children = self.client.get(public_url(link.token)).json()["children"]

        self.assertEqual([child["name"] for child in children], ["Mía"])

    def test_sub_album_cover_thumbnail_url_is_signed(self):
        parent = create_album("Madre")
        child = create_album("Hija", parent=parent)
        child.cover = create_media(child, thumbnail_key="albums/9/hija-thumb.jpg")
        child.save()
        link = create_share_link(album=parent)

        children = self.client.get(public_url(link.token)).json()["children"]

        self.assertEqual(
            parse_presigned_url(children[0]["cover_thumbnail_url"])["path"],
            f"/{TEST_R2_BUCKET_NAME}/albums/9/hija-thumb.jpg",
        )

    def test_sub_albums_are_ordered_newest_start_date_first(self):
        parent = create_album("Madre")
        create_album("Antigua", parent=parent, start_date=date(2024, 1, 1))
        create_album("Reciente", parent=parent, start_date=date(2026, 6, 1))
        create_album("Media", parent=parent, start_date=date(2025, 3, 1))
        link = create_share_link(album=parent)

        children = self.client.get(public_url(link.token)).json()["children"]

        self.assertEqual(
            [child["name"] for child in children], ["Reciente", "Media", "Antigua"]
        )

    def test_a_link_to_a_sub_album_shares_only_that_sub_album(self):
        parent = create_album("Madre")
        create_media(parent, original_filename="de-la-madre.jpg")
        child = create_album("Hija", parent=parent)
        create_media(child, original_filename="de-la-hija.jpg")
        link = create_share_link(album=child)

        data = self.client.get(public_url(link.token)).json()

        self.assertEqual(data["name"], "Hija")
        self.assertEqual(data["parent"], parent.pk)
        self.assertEqual(media_names(data), ["de-la-hija.jpg"])
        self.assertEqual(data["children"], [])


class PublicAlbumQueryCountTests(PublicAPITestCase):
    """Regression tests for the N+1 fix in `_serialize_album_tree`."""

    def test_media_does_not_add_queries(self):
        few = create_album("Pocas")
        create_media(few)
        many = create_album("Muchas")
        for _ in range(12):
            create_media(many)
        few_link = create_share_link(album=few)
        many_link = create_share_link(album=many)

        few_queries = count_queries(lambda: self.client.get(public_url(few_link.token)))
        many_queries = count_queries(
            lambda: self.client.get(public_url(many_link.token))
        )

        self.assertEqual(few_queries, many_queries)

    def test_sub_albums_and_their_media_do_not_add_queries(self):
        # Before the Prefetch, each sub-album cost its own media query.
        few = create_album("Pocas")
        create_media(create_album("Una", parent=few))
        many = create_album("Muchas")
        for number in range(6):
            child = create_album(f"Hija {number}", parent=many)
            child.cover = create_media(child)
            child.save()
            create_media(child)
            create_media(child)
        few_link = create_share_link(album=few)
        many_link = create_share_link(album=many)

        few_queries = count_queries(lambda: self.client.get(public_url(few_link.token)))
        many_queries = count_queries(
            lambda: self.client.get(public_url(many_link.token))
        )

        self.assertEqual(few_queries, many_queries)

    def test_a_whole_tree_is_loaded_in_a_fixed_number_of_queries(self):
        # link + album/cover, media, sub-albums and the sub-albums' media.
        parent = create_album("Madre")
        parent.cover = create_media(parent)
        parent.save()
        for number in range(3):
            create_media(create_album(f"Hija {number}", parent=parent))
        link = create_share_link(album=parent)

        with self.assertNumQueries(4):
            response = self.client.get(public_url(link.token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["children"]), 3)


class PublicAlbumNotFoundTests(PublicAPITestCase):
    def assertNotFound(self, response):
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), {"detail": SHARE_LINK_NOT_FOUND_MESSAGE})

    def test_unknown_token(self):
        self.assertNotFound(self.client.get(public_url("this-token-does-not-exist")))

    def test_revoked_link(self):
        link = create_share_link(is_active=False)

        self.assertNotFound(self.client.get(public_url(link.token)))

    def test_expired_link(self):
        link = create_share_link(expires_at=timezone.now() - timedelta(minutes=1))

        self.assertNotFound(self.client.get(public_url(link.token)))

    def test_link_with_a_future_expiration_still_works(self):
        link = create_share_link(expires_at=timezone.now() + timedelta(days=7))

        response = self.client.get(public_url(link.token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_link_of_a_soft_deleted_album(self):
        link = create_share_link()
        soft_delete(link.album)

        self.assertNotFound(self.client.get(public_url(link.token)))

    def test_deleting_the_album_closes_its_links_without_deleting_them(self):
        link = create_share_link()
        self.assertEqual(
            self.client.get(public_url(link.token)).status_code, status.HTTP_200_OK
        )

        soft_delete(link.album)

        self.assertNotFound(self.client.get(public_url(link.token)))

    def test_every_reason_gives_the_same_response(self):
        # A visitor must not be able to tell a revoked link from an expired one
        # or a deleted album from a token that never existed.
        revoked = create_share_link(is_active=False)
        expired = create_share_link(expires_at=timezone.now() - timedelta(minutes=1))
        deleted = create_share_link()
        soft_delete(deleted.album)
        tokens = {
            "revoked": revoked.token,
            "expired": expired.token,
            "deleted album": deleted.token,
            "unknown": "this-token-does-not-exist",
        }

        for reason, token in tokens.items():
            with self.subTest(reason=reason):
                self.assertNotFound(self.client.get(public_url(token)))
                self.assertNotFound(
                    self.client.post(public_url(token), {}, format="json")
                )

    @override_settings(PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)
    def test_a_dead_link_never_reveals_that_it_had_a_password(self):
        link = create_share_link(password=SAMPLE_SHARE_PASSWORD, is_active=False)

        for password in (None, "", WRONG_SHARE_PASSWORD, SAMPLE_SHARE_PASSWORD):
            with self.subTest(password=password):
                response = self.client.post(
                    public_url(link.token), {"password": password}, format="json"
                )

                self.assertNotFound(response)


@override_settings(PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)
class PublicAlbumPasswordTests(PublicAPITestCase):
    def setUp(self):
        super().setUp()
        album = create_album("Protegido")
        create_media(album, original_filename="secreta.jpg")
        self.link = create_share_link(album=album, password=SAMPLE_SHARE_PASSWORD)
        self.url = public_url(self.link.token)

    def post_password(self, password):
        return self.client.post(self.url, {"password": password}, format="json")

    def assertForbidden(self, response):
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # Nothing about the album leaks through the error.
        self.assertEqual(response.json(), {"detail": INCORRECT_PASSWORD})

    # -- GET (password in the query string)

    def test_get_without_a_password_is_forbidden(self):
        self.assertForbidden(self.client.get(self.url))

    def test_get_with_the_correct_password(self):
        response = self.client.get(self.url, {"password": SAMPLE_SHARE_PASSWORD})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["name"], "Protegido")
        self.assertEqual(media_names(response.json()), ["secreta.jpg"])

    def test_get_with_a_wrong_password_is_forbidden(self):
        self.assertForbidden(
            self.client.get(self.url, {"password": WRONG_SHARE_PASSWORD})
        )

    def test_get_with_an_empty_password_is_forbidden(self):
        self.assertForbidden(self.client.get(self.url, {"password": ""}))

    # -- POST (password in the body, so it stays out of the access logs)

    def test_post_with_the_correct_password(self):
        response = self.post_password(SAMPLE_SHARE_PASSWORD)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["name"], "Protegido")
        self.assertEqual(media_names(response.json()), ["secreta.jpg"])

    def test_post_accepts_a_form_encoded_body(self):
        response = self.client.post(
            self.url, {"password": SAMPLE_SHARE_PASSWORD}, format="multipart"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_post_with_a_wrong_password_is_forbidden(self):
        self.assertForbidden(self.post_password(WRONG_SHARE_PASSWORD))

    def test_post_with_an_empty_password_is_forbidden(self):
        self.assertForbidden(self.post_password(""))

    def test_post_with_a_null_password_is_forbidden(self):
        self.assertForbidden(self.post_password(None))

    def test_post_without_a_body_is_forbidden(self):
        self.assertForbidden(self.client.post(self.url))

    def test_post_without_the_password_field_is_forbidden(self):
        self.assertForbidden(self.client.post(self.url, {"other": "x"}, format="json"))

    def test_post_ignores_a_password_in_the_query_string(self):
        # POST reads the body only: a correct password in the URL does not count.
        response = self.client.post(
            f"{self.url}?password={SAMPLE_SHARE_PASSWORD}", {}, format="json"
        )

        self.assertForbidden(response)

    def test_get_ignores_a_password_in_the_body(self):
        response = self.client.generic(
            "GET",
            self.url,
            f'{{"password": "{SAMPLE_SHARE_PASSWORD}"}}',
            content_type="application/json",
        )

        self.assertForbidden(response)

    def test_password_must_match_exactly(self):
        for password in (
            SAMPLE_SHARE_PASSWORD.upper(),
            SAMPLE_SHARE_PASSWORD + " ",
            SAMPLE_SHARE_PASSWORD[:-1],
            self.link.password_hash,
        ):
            with self.subTest(password=password):
                self.assertForbidden(self.post_password(password))

    def test_the_password_of_another_link_is_not_accepted(self):
        create_share_link(password=WRONG_SHARE_PASSWORD)

        self.assertForbidden(self.post_password(WRONG_SHARE_PASSWORD))

    def test_a_link_without_a_password_ignores_any_password_sent(self):
        open_link = create_share_link(album=create_album("Abierto"))
        url = public_url(open_link.token)

        for response in (
            self.client.get(url),
            self.client.get(url, {"password": WRONG_SHARE_PASSWORD}),
            self.client.post(url, {"password": WRONG_SHARE_PASSWORD}, format="json"),
            self.client.post(url, {}, format="json"),
        ):
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.json()["name"], "Abierto")

    def test_a_wrong_password_loads_no_media(self):
        # The password is checked before the album tree is built, so a failed
        # attempt costs only the link lookup.
        queries = count_queries(lambda: self.post_password(WRONG_SHARE_PASSWORD))

        self.assertEqual(queries, 1)
