from datetime import date, timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from gallery.models import Album, Media
from gallery.utils.test_utils import (
    TEST_R2_BUCKET_NAME,
    AuthenticatedAPITestCase,
    count_queries,
    create_album,
    create_media,
    parse_presigned_url,
    soft_delete,
)

LIST_FIELDS = {
    "id",
    "name",
    "slug",
    "start_date",
    "end_date",
    "media_count",
    "cover_thumbnail_url",
    "created_at",
}
DETAIL_FIELDS = {
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
CHILD_FIELDS = {
    "id",
    "name",
    "slug",
    "description",
    "start_date",
    "end_date",
    "parent",
    "cover",
    "cover_thumbnail_url",
    "media_count",
    "created_at",
    "updated_at",
}

PARENT_IS_A_SUB_ALBUM = (
    "No se pueden crear sub-álbumes dentro de otro sub-álbum (solo un nivel)."
)
OWN_PARENT = "Un álbum no puede ser su propio padre."
HAS_CHILDREN = "No podés convertir un álbum con sub-álbumes en un sub-álbum."


def list_url():
    return reverse("album-list")


def detail_url(album_id):
    return reverse("album-detail", args=[album_id])


def create_album_with_cover(
    name="With Cover", thumbnail_key="albums/1/cover-thumb.jpg"
):
    album = create_album(name)
    cover = create_media(album, thumbnail_key=thumbnail_key)
    album.cover = cover
    album.save()
    return album


class AlbumAuthenticationTests(APITestCase):
    """Without a JWT, nothing in the album API is reachable."""

    def test_every_endpoint_requires_authentication(self):
        album = create_album()
        requests = [
            ("get", list_url()),
            ("post", list_url()),
            ("get", detail_url(album.pk)),
            ("put", detail_url(album.pk)),
            ("patch", detail_url(album.pk)),
            ("delete", detail_url(album.pk)),
        ]

        for method, url in requests:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, {}, format="json")

                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nothing_was_changed_by_the_rejected_requests(self):
        album = create_album("Intacto")

        self.client.patch(detail_url(album.pk), {"name": "Hacked"}, format="json")
        self.client.delete(detail_url(album.pk))

        album.refresh_from_db()
        self.assertEqual(album.name, "Intacto")
        self.assertIsNone(album.deleted_at)


class AlbumListTests(AuthenticatedAPITestCase):
    def test_empty_list(self):
        response = self.client.get(list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [])

    def test_returns_the_fields_the_dashboard_needs(self):
        create_album("Viaje a Bariloche", start_date=date(2026, 1, 10))

        album = self.client.get(list_url()).json()[0]

        self.assertEqual(set(album), LIST_FIELDS)
        self.assertEqual(album["name"], "Viaje a Bariloche")
        self.assertEqual(album["slug"], "viaje-a-bariloche")
        self.assertEqual(album["start_date"], "2026-01-10")

    def test_only_top_level_albums_are_listed(self):
        parent = create_album("Madre")
        create_album("Hija", parent=parent)

        names = [album["name"] for album in self.client.get(list_url()).json()]

        self.assertEqual(names, ["Madre"])

    def test_soft_deleted_albums_are_not_listed(self):
        create_album("Visible")
        soft_delete(create_album("Borrado"))

        names = [album["name"] for album in self.client.get(list_url()).json()]

        self.assertEqual(names, ["Visible"])

    def test_media_count_ignores_soft_deleted_media(self):
        album = create_album()
        create_media(album)
        create_media(album)
        soft_delete(create_media(album))

        listed = self.client.get(list_url()).json()[0]

        self.assertEqual(listed["media_count"], 2)

    def test_media_count_is_zero_for_an_empty_album(self):
        create_album()

        self.assertEqual(self.client.get(list_url()).json()[0]["media_count"], 0)

    def test_media_count_is_per_album(self):
        busy = create_album("Con fotos", start_date=date(2026, 2, 1))
        create_media(busy)
        create_media(busy)
        create_media(busy)
        create_album("Vacío", start_date=date(2026, 1, 1))

        counts = {
            a["name"]: a["media_count"] for a in self.client.get(list_url()).json()
        }

        self.assertEqual(counts, {"Con fotos": 3, "Vacío": 0})

    def test_cover_thumbnail_url_signs_the_cover_thumbnail_key(self):
        create_album_with_cover(thumbnail_key="albums/1/portada-thumb.jpg")

        url = self.client.get(list_url()).json()[0]["cover_thumbnail_url"]

        parts = parse_presigned_url(url)
        self.assertEqual(
            parts["path"], f"/{TEST_R2_BUCKET_NAME}/albums/1/portada-thumb.jpg"
        )
        self.assertIn("X-Amz-Signature", parts["query"])

    def test_cover_thumbnail_url_is_null_without_a_cover(self):
        create_album()

        self.assertIsNone(self.client.get(list_url()).json()[0]["cover_thumbnail_url"])

    def test_cover_thumbnail_url_is_null_while_the_thumbnail_is_pending(self):
        # A freshly uploaded cover has no thumbnail until the worker runs.
        create_album_with_cover(thumbnail_key="")

        self.assertIsNone(self.client.get(list_url()).json()[0]["cover_thumbnail_url"])

    def test_newest_start_date_comes_first(self):
        create_album("Antiguo", start_date=date(2024, 1, 1))
        create_album("Reciente", start_date=date(2026, 6, 1))
        create_album("Medio", start_date=date(2025, 3, 1))

        names = [album["name"] for album in self.client.get(list_url()).json()]

        self.assertEqual(names, ["Reciente", "Medio", "Antiguo"])

    def test_same_start_date_shows_the_latest_created_first(self):
        create_album("Primero", start_date=date(2026, 1, 1))
        create_album("Segundo", start_date=date(2026, 1, 1))

        names = [album["name"] for album in self.client.get(list_url()).json()]

        self.assertEqual(names, ["Segundo", "Primero"])

    def test_the_list_is_one_query_however_many_albums_there_are(self):
        # Regression test for the N+1 fix: cover and media count are loaded in
        # the same query. Before it, this was 1 + 2 queries per album.
        for number in range(6):
            album = create_album_with_cover(
                name=f"Viaje {number}", thumbnail_key=f"albums/{number}/c-thumb.jpg"
            )
            create_media(album)

        with self.assertNumQueries(1):
            response = self.client.get(list_url())

        self.assertEqual(len(response.json()), 6)


class AlbumRetrieveTests(AuthenticatedAPITestCase):
    def test_returns_the_full_album(self):
        album = create_album(
            "Viaje a Bariloche",
            description="Con amigos",
            start_date=date(2026, 1, 10),
            end_date=date(2026, 1, 20),
        )

        response = self.client.get(detail_url(album.pk))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(set(data), DETAIL_FIELDS)
        self.assertEqual(data["id"], album.pk)
        self.assertEqual(data["description"], "Con amigos")
        self.assertEqual(data["end_date"], "2026-01-20")
        self.assertIsNone(data["parent"])
        self.assertEqual(data["media"], [])
        self.assertEqual(data["children"], [])

    def test_unknown_album_is_404(self):
        self.assertEqual(
            self.client.get(detail_url(999999)).status_code, status.HTTP_404_NOT_FOUND
        )

    def test_soft_deleted_album_is_404(self):
        album = create_album()
        soft_delete(album)

        self.assertEqual(
            self.client.get(detail_url(album.pk)).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_media_excludes_soft_deleted_files_and_follows_the_manual_order(self):
        album = create_album()
        create_media(album, original_filename="tercera.jpg", order=3)
        create_media(album, original_filename="primera.jpg", order=1)
        create_media(album, original_filename="segunda.jpg", order=2)
        soft_delete(create_media(album, original_filename="borrada.jpg", order=0))

        media = self.client.get(detail_url(album.pk)).json()["media"]

        self.assertEqual(
            [item["original_filename"] for item in media],
            ["primera.jpg", "segunda.jpg", "tercera.jpg"],
        )

    def test_media_urls_are_presigned_for_the_files_keys(self):
        album = create_album()
        create_media(
            album,
            storage_key="albums/1/foto.jpg",
            thumbnail_key="albums/1/foto-thumb.jpg",
        )

        item = self.client.get(detail_url(album.pk)).json()["media"][0]

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
        create_media(album, thumbnail_key="", processing_status=Media.STATUS_PENDING)

        item = self.client.get(detail_url(album.pk)).json()["media"][0]

        self.assertIsNone(item["thumbnail_url"])
        self.assertEqual(item["processing_status"], "pending")

    def test_children_are_summaries_without_their_media(self):
        parent = create_album("Madre")
        child = create_album("Hija", parent=parent, description="Un día")
        create_media(child)
        create_media(child)

        children = self.client.get(detail_url(parent.pk)).json()["children"]

        self.assertEqual(len(children), 1)
        self.assertEqual(set(children[0]), CHILD_FIELDS)
        self.assertNotIn("media", children[0])
        self.assertNotIn("children", children[0])
        self.assertEqual(children[0]["name"], "Hija")
        self.assertEqual(children[0]["parent"], parent.pk)
        self.assertEqual(children[0]["media_count"], 2)

    def test_child_media_count_ignores_soft_deleted_media(self):
        parent = create_album("Madre")
        child = create_album("Hija", parent=parent)
        create_media(child)
        soft_delete(create_media(child))

        children = self.client.get(detail_url(parent.pk)).json()["children"]

        self.assertEqual(children[0]["media_count"], 1)

    def test_child_cover_thumbnail_url_is_signed(self):
        parent = create_album("Madre")
        child = create_album("Hija", parent=parent)
        child.cover = create_media(child, thumbnail_key="albums/9/hija-thumb.jpg")
        child.save()

        children = self.client.get(detail_url(parent.pk)).json()["children"]

        self.assertEqual(
            parse_presigned_url(children[0]["cover_thumbnail_url"])["path"],
            f"/{TEST_R2_BUCKET_NAME}/albums/9/hija-thumb.jpg",
        )

    def test_soft_deleted_children_are_not_included(self):
        parent = create_album("Madre")
        create_album("Visible", parent=parent)
        soft_delete(create_album("Borrada", parent=parent))

        children = self.client.get(detail_url(parent.pk)).json()["children"]

        self.assertEqual([child["name"] for child in children], ["Visible"])

    def test_children_are_ordered_like_the_album_list(self):
        # Counting media turns the query into a GROUP BY, where Django drops
        # Meta.ordering: this guards that the order is still applied.
        parent = create_album("Madre")
        create_album("Antigua", parent=parent, start_date=date(2024, 1, 1))
        create_album("Reciente", parent=parent, start_date=date(2026, 6, 1))
        create_album("Media", parent=parent, start_date=date(2025, 3, 1))

        children = self.client.get(detail_url(parent.pk)).json()["children"]

        self.assertEqual(
            [child["name"] for child in children], ["Reciente", "Media", "Antigua"]
        )

    def test_a_sub_album_can_be_retrieved_and_has_no_children(self):
        parent = create_album("Madre")
        child = create_album("Hija", parent=parent)

        data = self.client.get(detail_url(child.pk)).json()

        self.assertEqual(data["parent"], parent.pk)
        self.assertEqual(data["children"], [])

    def test_children_do_not_add_queries(self):
        # Sub-albums are loaded with their cover and count in a single query.
        few = create_album("Pocas")
        create_album("Una", parent=few)
        many = create_album("Muchas")
        for number in range(6):
            child = create_album(f"Hija {number}", parent=many)
            child.cover = create_media(child)
            child.save()

        few_queries = count_queries(lambda: self.client.get(detail_url(few.pk)))
        many_queries = count_queries(lambda: self.client.get(detail_url(many.pk)))

        self.assertEqual(few_queries, many_queries)

    def test_media_does_not_add_queries(self):
        few = create_album("Pocas")
        create_media(few)
        many = create_album("Muchas")
        for _ in range(12):
            create_media(many)

        few_queries = count_queries(lambda: self.client.get(detail_url(few.pk)))
        many_queries = count_queries(lambda: self.client.get(detail_url(many.pk)))

        self.assertEqual(few_queries, many_queries)


class AlbumCreateTests(AuthenticatedAPITestCase):
    def post(self, data):
        return self.client.post(list_url(), data, format="json")

    def test_creates_an_album_with_only_a_name(self):
        response = self.post({"name": "Viaje a Bariloche"})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(set(data), DETAIL_FIELDS)
        self.assertEqual(data["name"], "Viaje a Bariloche")
        self.assertEqual(data["slug"], "viaje-a-bariloche")
        self.assertEqual(data["description"], "")
        self.assertIsNone(data["parent"])
        self.assertEqual(data["media"], [])
        self.assertEqual(data["children"], [])
        self.assertTrue(Album.objects.filter(pk=data["id"]).exists())

    def test_saves_all_the_given_fields(self):
        response = self.post(
            {
                "name": "Patagonia",
                "description": "Dos semanas",
                "start_date": "2026-02-01",
                "end_date": "2026-02-14",
            }
        )

        album = Album.objects.get(pk=response.json()["id"])
        self.assertEqual(album.description, "Dos semanas")
        self.assertEqual(album.start_date, date(2026, 2, 1))
        self.assertEqual(album.end_date, date(2026, 2, 14))

    def test_slug_drops_accents(self):
        response = self.post({"name": "Cañón del Atuel"})

        self.assertEqual(response.json()["slug"], "canon-del-atuel")

    def test_same_name_gets_a_unique_slug(self):
        first = self.post({"name": "Viaje"}).json()
        second = self.post({"name": "Viaje"}).json()
        third = self.post({"name": "Viaje"}).json()

        self.assertEqual(
            [first["slug"], second["slug"], third["slug"]],
            ["viaje", "viaje-2", "viaje-3"],
        )

    def test_name_is_required(self):
        response = self.post({"description": "Sin nombre"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.json())
        self.assertEqual(Album.objects.count(), 0)

    def test_blank_name_is_rejected(self):
        response = self.post({"name": ""})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.json())

    def test_can_create_a_sub_album(self):
        parent = create_album("Madre")

        response = self.post({"name": "Hija", "parent": parent.pk})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["parent"], parent.pk)
        children = self.client.get(detail_url(parent.pk)).json()["children"]
        self.assertEqual([child["name"] for child in children], ["Hija"])
        listed = [a["name"] for a in self.client.get(list_url()).json()]
        self.assertEqual(listed, ["Madre"])

    def test_a_sub_album_cannot_be_the_parent_of_another(self):
        parent = create_album("Madre")
        child = create_album("Hija", parent=parent)

        response = self.post({"name": "Nieta", "parent": child.pk})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["parent"], [PARENT_IS_A_SUB_ALBUM])
        self.assertFalse(Album.objects.filter(name="Nieta").exists())

    def test_parent_cannot_be_a_soft_deleted_album(self):
        parent = create_album("Madre")
        soft_delete(parent)

        response = self.post({"name": "Hija", "parent": parent.pk})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("parent", response.json())

    def test_parent_must_exist(self):
        response = self.post({"name": "Hija", "parent": 999999})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("parent", response.json())

    def test_deleted_at_cannot_be_set_from_the_api(self):
        response = self.post({"name": "Intento", "deleted_at": "2020-01-01T00:00:00Z"})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(Album.objects.get(pk=response.json()["id"]).deleted_at)


class AlbumUpdateTests(AuthenticatedAPITestCase):
    def patch(self, album, data):
        return self.client.patch(detail_url(album.pk), data, format="json")

    def test_patch_updates_only_the_given_fields(self):
        album = create_album("Viejo", description="Original")

        response = self.patch(album, {"name": "Nuevo"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["name"], "Nuevo")
        album.refresh_from_db()
        self.assertEqual(album.name, "Nuevo")
        self.assertEqual(album.description, "Original")

    def test_renaming_keeps_the_slug(self):
        album = create_album("Viaje")

        response = self.patch(album, {"name": "Otro nombre"})

        self.assertEqual(response.json()["slug"], "viaje")

    def test_patch_updates_description_and_dates(self):
        album = create_album()

        self.patch(
            album,
            {
                "description": "Nueva",
                "start_date": "2026-03-01",
                "end_date": "2026-03-09",
            },
        )

        album.refresh_from_db()
        self.assertEqual(album.description, "Nueva")
        self.assertEqual(album.start_date, date(2026, 3, 1))
        self.assertEqual(album.end_date, date(2026, 3, 9))

    def test_put_replaces_the_album_and_needs_a_name(self):
        album = create_album("Viejo")

        rejected = self.client.put(detail_url(album.pk), {}, format="json")
        accepted = self.client.put(
            detail_url(album.pk), {"name": "Nuevo"}, format="json"
        )

        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", rejected.json())
        self.assertEqual(accepted.status_code, status.HTTP_200_OK)
        album.refresh_from_db()
        self.assertEqual(album.name, "Nuevo")

    def test_the_response_has_the_admin_detail_shape(self):
        parent = create_album("Madre")
        create_album("Hija", parent=parent)

        data = self.patch(parent, {"description": "x"}).json()

        self.assertEqual(set(data), DETAIL_FIELDS)
        self.assertEqual(set(data["children"][0]), CHILD_FIELDS)

    def test_unknown_album_is_404(self):
        response = self.client.patch(detail_url(999999), {"name": "x"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_soft_deleted_album_cannot_be_updated(self):
        album = create_album("Borrado")
        soft_delete(album)

        response = self.patch(album, {"name": "Revivido"})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        album.refresh_from_db()
        self.assertEqual(album.name, "Borrado")

    def test_album_can_be_moved_under_another_album(self):
        parent = create_album("Madre")
        album = create_album("Suelto")

        response = self.patch(album, {"parent": parent.pk})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        album.refresh_from_db()
        self.assertEqual(album.parent_id, parent.pk)
        listed = [a["name"] for a in self.client.get(list_url()).json()]
        self.assertEqual(listed, ["Madre"])

    def test_sub_album_can_be_promoted_to_top_level(self):
        parent = create_album("Madre")
        child = create_album("Hija", parent=parent)

        response = self.patch(child, {"parent": None})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        child.refresh_from_db()
        self.assertIsNone(child.parent_id)
        listed = {a["name"] for a in self.client.get(list_url()).json()}
        self.assertEqual(listed, {"Madre", "Hija"})

    def test_album_cannot_be_its_own_parent(self):
        album = create_album()

        response = self.patch(album, {"parent": album.pk})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["parent"], [OWN_PARENT])

    def test_album_with_sub_albums_cannot_become_a_sub_album(self):
        parent = create_album("Madre")
        create_album("Hija", parent=parent)
        other = create_album("Otra")

        response = self.patch(parent, {"parent": other.pk})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["parent"], [HAS_CHILDREN])
        parent.refresh_from_db()
        self.assertIsNone(parent.parent_id)

    def test_only_deleted_sub_albums_do_not_block_becoming_a_sub_album(self):
        parent = create_album("Madre")
        soft_delete(create_album("Borrada", parent=parent))
        other = create_album("Otra")

        response = self.patch(parent, {"parent": other.pk})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_parent_cannot_be_a_sub_album(self):
        root = create_album("Raíz")
        child = create_album("Hija", parent=root)
        album = create_album("Suelto")

        response = self.patch(album, {"parent": child.pk})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["parent"], [PARENT_IS_A_SUB_ALBUM])

    def test_cover_can_be_set_to_a_photo_of_the_album(self):
        album = create_album()
        media = create_media(album, thumbnail_key="albums/3/nueva-thumb.jpg")

        data = self.patch(album, {"cover": media.pk}).json()

        self.assertEqual(data["cover"], media.pk)
        self.assertEqual(
            parse_presigned_url(data["cover_thumbnail_url"])["path"],
            f"/{TEST_R2_BUCKET_NAME}/albums/3/nueva-thumb.jpg",
        )

    def test_deleted_at_cannot_be_set_from_the_api(self):
        album = create_album()

        self.patch(album, {"deleted_at": "2020-01-01T00:00:00Z"})

        album.refresh_from_db()
        self.assertIsNone(album.deleted_at)


class AlbumDestroyTests(AuthenticatedAPITestCase):
    def test_delete_is_a_soft_delete(self):
        album = create_album()
        before = timezone.now()

        response = self.client.delete(detail_url(album.pk))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        album.refresh_from_db()  # the row is still there
        self.assertIsNotNone(album.deleted_at)
        self.assertGreaterEqual(album.deleted_at, before)

    def test_deleted_album_disappears_from_the_list_and_detail(self):
        album = create_album("Borrar")
        create_album("Quedarse")

        self.client.delete(detail_url(album.pk))

        names = [a["name"] for a in self.client.get(list_url()).json()]
        self.assertEqual(names, ["Quedarse"])
        self.assertEqual(
            self.client.get(detail_url(album.pk)).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_media_of_the_album_is_kept(self):
        # Bucket files and their records are only purged later, never here.
        album = create_album()
        media = create_media(album)

        self.client.delete(detail_url(album.pk))

        media.refresh_from_db()
        self.assertIsNone(media.deleted_at)

    def test_deleting_a_parent_deletes_its_sub_albums_too(self):
        parent = create_album("Madre")
        first = create_album("Hija 1", parent=parent)
        second = create_album("Hija 2", parent=parent)

        self.client.delete(detail_url(parent.pk))

        for album in (parent, first, second):
            album.refresh_from_db()
            self.assertIsNotNone(album.deleted_at)
        self.assertEqual(first.deleted_at, parent.deleted_at)
        self.assertEqual(second.deleted_at, parent.deleted_at)
        self.assertEqual(
            self.client.get(detail_url(first.pk)).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_sub_albums_deleted_earlier_keep_their_original_deletion_date(self):
        parent = create_album("Madre")
        long_ago = timezone.now() - timedelta(days=30)
        old = create_album("Vieja", parent=parent)
        soft_delete(old, long_ago)

        self.client.delete(detail_url(parent.pk))

        old.refresh_from_db()
        self.assertEqual(old.deleted_at, long_ago)

    def test_deleting_a_sub_album_leaves_the_parent_and_siblings(self):
        parent = create_album("Madre")
        gone = create_album("Se va", parent=parent)
        stays = create_album("Se queda", parent=parent)

        response = self.client.delete(detail_url(gone.pk))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        parent.refresh_from_db()
        stays.refresh_from_db()
        self.assertIsNone(parent.deleted_at)
        self.assertIsNone(stays.deleted_at)
        children = self.client.get(detail_url(parent.pk)).json()["children"]
        self.assertEqual([child["name"] for child in children], ["Se queda"])

    def test_deleting_an_album_does_not_touch_other_albums(self):
        gone = create_album("Se va")
        stays = create_album("Se queda")

        self.client.delete(detail_url(gone.pk))

        stays.refresh_from_db()
        self.assertIsNone(stays.deleted_at)

    def test_deleting_twice_is_404(self):
        album = create_album()
        self.client.delete(detail_url(album.pk))

        response = self.client.delete(detail_url(album.pk))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_album_is_404(self):
        response = self.client.delete(detail_url(999999))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
