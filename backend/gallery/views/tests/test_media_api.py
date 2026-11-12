from unittest import expectedFailure
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from gallery.models import Media
from gallery.services.storage_service import PRESIGNED_EXPIRES_IN
from gallery.utils.test_utils import (
    SAMPLE_CONTENT_TYPE,
    TEST_R2_BUCKET_NAME,
    AuthenticatedAPITestCase,
    create_album,
    create_media,
    parse_presigned_url,
    soft_delete,
)

MEDIA_FIELDS = {
    "id",
    "album",
    "type",
    "original_filename",
    "storage_key",
    "thumbnail_key",
    "thumbnail_url",
    "file_url",
    "size",
    "content_type",
    "width",
    "height",
    "duration",
    "taken_at",
    "order",
    "processing_status",
    "created_at",
}
REQUIRED_UPLOAD_FIELDS = ["album", "original_filename", "content_type", "size", "type"]
REQUIRED_FIELDS_MESSAGE = (
    "album, original_filename, content_type, size and type are all required."
)

GENERATE_THUMBNAIL = "gallery.views.media_api.generate_thumbnail"
PRESIGN_UPLOAD = "gallery.views.media_api.generate_presigned_upload_url"


def list_url():
    return reverse("media-list")


def detail_url(media_id):
    return reverse("media-detail", args=[media_id])


def upload_url():
    return reverse("media-presigned-upload")


def confirm_url(media_id):
    return reverse("media-confirm", args=[media_id])


def upload_payload(album, **overrides):
    """A valid body for the presigned-upload endpoint."""
    payload = {
        "album": album.pk,
        "original_filename": "atardecer.jpg",
        "content_type": SAMPLE_CONTENT_TYPE,
        "size": 2048,
        "type": "photo",
    }
    payload.update(overrides)
    return payload


class MediaAuthenticationTests(APITestCase):
    """Without a JWT, nothing in the media API is reachable."""

    @patch(GENERATE_THUMBNAIL)
    def test_every_endpoint_requires_authentication(self, generate_thumbnail):
        album = create_album()
        media = create_media(album)
        requests = [
            ("get", list_url()),
            ("post", list_url()),
            ("get", detail_url(media.pk)),
            ("put", detail_url(media.pk)),
            ("patch", detail_url(media.pk)),
            ("delete", detail_url(media.pk)),
            ("post", upload_url()),
            ("post", confirm_url(media.pk)),
        ]

        for method, url in requests:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, {}, format="json")

                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        generate_thumbnail.delay.assert_not_called()
        self.assertEqual(Media.objects.count(), 1)

    def test_a_rejected_upload_request_creates_nothing(self):
        album = create_album()

        self.client.post(upload_url(), upload_payload(album), format="json")

        self.assertEqual(Media.objects.count(), 0)


class MediaListTests(AuthenticatedAPITestCase):
    def test_empty_list(self):
        response = self.client.get(list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [])

    def test_returns_the_media_fields(self):
        album = create_album()
        media = create_media(
            album, original_filename="playa.jpg", width=4000, height=3000
        )

        item = self.client.get(list_url()).json()[0]

        self.assertEqual(set(item), MEDIA_FIELDS)
        self.assertEqual(item["id"], media.pk)
        self.assertEqual(item["album"], album.pk)
        self.assertEqual(item["original_filename"], "playa.jpg")
        self.assertEqual(item["type"], "photo")
        self.assertEqual((item["width"], item["height"]), (4000, 3000))

    def test_soft_deleted_media_is_not_listed(self):
        album = create_album()
        create_media(album, original_filename="visible.jpg")
        soft_delete(create_media(album, original_filename="borrada.jpg"))

        names = [
            item["original_filename"] for item in self.client.get(list_url()).json()
        ]

        self.assertEqual(names, ["visible.jpg"])

    def test_lists_the_media_of_every_album(self):
        create_media(create_album("Uno"), original_filename="a.jpg")
        create_media(create_album("Dos"), original_filename="b.jpg")

        names = {
            item["original_filename"] for item in self.client.get(list_url()).json()
        }

        self.assertEqual(names, {"a.jpg", "b.jpg"})

    def test_follows_the_manual_order_then_upload_order(self):
        album = create_album()
        create_media(album, original_filename="tercera.jpg", order=2)
        create_media(album, original_filename="primera.jpg", order=1)
        create_media(album, original_filename="segunda.jpg", order=1)

        names = [
            item["original_filename"] for item in self.client.get(list_url()).json()
        ]

        self.assertEqual(names, ["primera.jpg", "segunda.jpg", "tercera.jpg"])

    def test_urls_are_signed_for_the_files_keys(self):
        album = create_album()
        create_media(
            album,
            storage_key="albums/1/foto.jpg",
            thumbnail_key="albums/1/foto-thumb.jpg",
        )

        item = self.client.get(list_url()).json()[0]

        self.assertEqual(
            parse_presigned_url(item["file_url"])["path"],
            f"/{TEST_R2_BUCKET_NAME}/albums/1/foto.jpg",
        )
        self.assertEqual(
            parse_presigned_url(item["thumbnail_url"])["path"],
            f"/{TEST_R2_BUCKET_NAME}/albums/1/foto-thumb.jpg",
        )

    def test_thumbnail_url_is_null_until_the_thumbnail_exists(self):
        create_media(create_album(), thumbnail_key="")

        item = self.client.get(list_url()).json()[0]

        self.assertIsNone(item["thumbnail_url"])
        self.assertTrue(item["file_url"])

    def test_the_list_is_one_query_however_much_media_there_is(self):
        album = create_album()
        for _ in range(8):
            create_media(album, thumbnail_key="albums/1/t-thumb.jpg")

        with self.assertNumQueries(1):
            response = self.client.get(list_url())

        self.assertEqual(len(response.json()), 8)


class MediaRetrieveTests(AuthenticatedAPITestCase):
    def test_returns_the_media(self):
        media = create_media(create_album(), original_filename="lago.jpg")

        response = self.client.get(detail_url(media.pk))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.json()), MEDIA_FIELDS)
        self.assertEqual(response.json()["original_filename"], "lago.jpg")

    def test_unknown_media_is_404(self):
        response = self.client.get(detail_url(999999))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_soft_deleted_media_is_404(self):
        media = create_media(create_album())
        soft_delete(media)

        response = self.client.get(detail_url(media.pk))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class MediaUpdateTests(AuthenticatedAPITestCase):
    def patch(self, media, data):
        return self.client.patch(detail_url(media.pk), data, format="json")

    def test_patch_changes_the_manual_order(self):
        media = create_media(create_album(), order=0)

        response = self.patch(media, {"order": 5})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["order"], 5)
        media.refresh_from_db()
        self.assertEqual(media.order, 5)

    def test_patch_only_touches_the_given_fields(self):
        media = create_media(create_album(), original_filename="vieja.jpg", order=3)

        self.patch(media, {"original_filename": "nueva.jpg"})

        media.refresh_from_db()
        self.assertEqual(media.original_filename, "nueva.jpg")
        self.assertEqual(media.order, 3)

    def test_server_managed_fields_cannot_be_changed(self):
        # storage_key / thumbnail_key / processing_status belong to the upload
        # flow and the worker: a client must not be able to repoint a record at
        # another object in the bucket.
        media = create_media(
            create_album(),
            storage_key="albums/1/original.jpg",
            thumbnail_key="albums/1/original-thumb.jpg",
            processing_status=Media.STATUS_READY,
        )

        response = self.patch(
            media,
            {
                "storage_key": "albums/99/otra-cosa.jpg",
                "thumbnail_key": "albums/99/otra-cosa-thumb.jpg",
                "processing_status": "error",
                "created_at": "2000-01-01T00:00:00Z",
                "deleted_at": "2000-01-01T00:00:00Z",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        media.refresh_from_db()
        self.assertEqual(media.storage_key, "albums/1/original.jpg")
        self.assertEqual(media.thumbnail_key, "albums/1/original-thumb.jpg")
        self.assertEqual(media.processing_status, Media.STATUS_READY)
        self.assertGreater(media.created_at.year, 2000)
        self.assertIsNone(media.deleted_at)

    def test_soft_deleted_media_cannot_be_updated(self):
        media = create_media(create_album(), order=1)
        soft_delete(media)

        response = self.patch(media, {"order": 9})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        media.refresh_from_db()
        self.assertEqual(media.order, 1)


class MediaDestroyTests(AuthenticatedAPITestCase):
    def test_delete_is_a_soft_delete(self):
        media = create_media(create_album())
        before = timezone.now()

        response = self.client.delete(detail_url(media.pk))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        media.refresh_from_db()  # the row is still there
        self.assertIsNotNone(media.deleted_at)
        self.assertGreaterEqual(media.deleted_at, before)

    def test_deleted_media_disappears_everywhere(self):
        album = create_album()
        media = create_media(album, original_filename="borrar.jpg")
        create_media(album, original_filename="quedarse.jpg")

        self.client.delete(detail_url(media.pk))

        names = [
            item["original_filename"] for item in self.client.get(list_url()).json()
        ]
        self.assertEqual(names, ["quedarse.jpg"])
        self.assertEqual(
            self.client.get(detail_url(media.pk)).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        album_url = reverse("album-detail", args=[album.pk])
        in_album = self.client.get(album_url).json()["media"]
        self.assertEqual([m["original_filename"] for m in in_album], ["quedarse.jpg"])

    @patch("gallery.services.storage_service.get_r2_client")
    def test_the_file_in_the_bucket_is_not_deleted(self, get_client):
        # Purging the bucket is a separate, later step (see CLAUDE.md).
        media = create_media(create_album())

        self.client.delete(detail_url(media.pk))

        get_client.assert_not_called()

    def test_other_media_is_not_touched(self):
        album = create_album()
        gone = create_media(album)
        stays = create_media(album)

        self.client.delete(detail_url(gone.pk))

        stays.refresh_from_db()
        self.assertIsNone(stays.deleted_at)

    def test_deleting_twice_is_404(self):
        media = create_media(create_album())
        self.client.delete(detail_url(media.pk))

        response = self.client.delete(detail_url(media.pk))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_media_is_404(self):
        response = self.client.delete(detail_url(999999))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class MediaPresignedUploadTests(AuthenticatedAPITestCase):
    """Step 1 of the upload flow: create the record, hand out a PUT URL."""

    def post(self, data):
        return self.client.post(upload_url(), data, format="json")

    def test_creates_a_pending_record_and_returns_the_upload_url(self):
        album = create_album()

        response = self.post(upload_payload(album))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(set(data), {"media", "upload_url"})
        self.assertEqual(set(data["media"]), MEDIA_FIELDS)
        media = Media.objects.get()
        self.assertEqual(data["media"]["id"], media.pk)
        self.assertEqual(media.album_id, album.pk)
        self.assertEqual(media.type, "photo")
        self.assertEqual(media.original_filename, "atardecer.jpg")
        self.assertEqual(media.content_type, SAMPLE_CONTENT_TYPE)
        self.assertEqual(media.size, 2048)
        self.assertEqual(media.processing_status, Media.STATUS_PENDING)
        self.assertEqual(media.thumbnail_key, "")
        self.assertIsNone(media.deleted_at)

    def test_the_record_has_no_thumbnail_yet(self):
        response = self.post(upload_payload(create_album()))

        media = response.json()["media"]

        self.assertEqual(media["processing_status"], "pending")
        self.assertIsNone(media["thumbnail_url"])

    def test_the_storage_key_is_generated_by_the_server(self):
        album = create_album()

        response = self.post(upload_payload(album, original_filename="Foto.JPG"))

        key = response.json()["media"]["storage_key"]
        self.assertRegex(key, rf"^albums/{album.pk}/[0-9a-f]{{32}}\.jpg$")
        self.assertEqual(Media.objects.get().storage_key, key)

    def test_the_client_filename_is_display_text_only(self):
        album = create_album()
        hostile = "../../etc/passwd.JPG"

        response = self.post(upload_payload(album, original_filename=hostile))

        media = Media.objects.get()
        self.assertEqual(media.original_filename, hostile)
        self.assertRegex(media.storage_key, rf"^albums/{album.pk}/[0-9a-f]{{32}}\.jpg$")
        self.assertNotIn("..", response.json()["media"]["storage_key"])

    def test_upload_url_targets_the_new_key_and_is_signed(self):
        response = self.post(upload_payload(create_album()))

        data = response.json()
        parts = parse_presigned_url(data["upload_url"])
        self.assertEqual(parts["scheme"], "https")
        self.assertEqual(
            parts["path"], f"/{TEST_R2_BUCKET_NAME}/{data['media']['storage_key']}"
        )
        self.assertEqual(parts["query"]["X-Amz-Expires"], str(PRESIGNED_EXPIRES_IN))
        self.assertIn("content-type", parts["query"]["X-Amz-SignedHeaders"].split(";"))

    @patch(PRESIGN_UPLOAD, return_value="https://signed.example/put")
    def test_upload_url_is_signed_for_the_declared_content_type(self, presign):
        response = self.post(upload_payload(create_album(), content_type="image/heic"))

        key = response.json()["media"]["storage_key"]
        presign.assert_called_once_with(key, "image/heic")
        self.assertEqual(response.json()["upload_url"], "https://signed.example/put")

    def test_videos_are_accepted(self):
        response = self.post(
            upload_payload(
                create_album(),
                original_filename="viaje.MP4",
                content_type="video/mp4",
                type="video",
            )
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        media = Media.objects.get()
        self.assertEqual(media.type, "video")
        self.assertTrue(media.storage_key.endswith(".mp4"))

    def test_can_upload_into_a_sub_album(self):
        parent = create_album("Madre")
        child = create_album("Hija", parent=parent)

        response = self.post(upload_payload(child))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Media.objects.get().album_id, child.pk)

    def test_the_same_filename_twice_makes_two_records_with_different_keys(self):
        album = create_album()

        self.post(upload_payload(album))
        self.post(upload_payload(album))

        keys = set(Media.objects.values_list("storage_key", flat=True))
        self.assertEqual(Media.objects.count(), 2)
        self.assertEqual(len(keys), 2)

    def test_every_field_is_required(self):
        album = create_album()

        for field in REQUIRED_UPLOAD_FIELDS:
            with self.subTest(missing=field):
                payload = upload_payload(album)
                del payload[field]

                response = self.post(payload)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(response.json(), {"detail": REQUIRED_FIELDS_MESSAGE})

        self.assertEqual(Media.objects.count(), 0)

    def test_empty_values_count_as_missing(self):
        album = create_album()

        for field in ("original_filename", "content_type", "type"):
            with self.subTest(empty=field):
                response = self.post(upload_payload(album, **{field: ""}))

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(Media.objects.count(), 0)

    def test_unknown_album_is_404(self):
        response = self.post({**upload_payload(create_album()), "album": 999999})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Media.objects.count(), 0)

    def test_soft_deleted_album_is_404(self):
        album = create_album()
        soft_delete(album)

        response = self.post(upload_payload(album))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Media.objects.count(), 0)

    def test_a_failed_request_does_not_leave_a_record_behind(self):
        album = create_album()
        payload = upload_payload(album)
        del payload["size"]

        self.post(payload)

        self.assertEqual(Media.objects.count(), 0)


class MediaConfirmTests(AuthenticatedAPITestCase):
    """Step 2 of the upload flow: the browser finished the PUT, start the worker."""

    def setUp(self):
        super().setUp()
        patcher = patch(GENERATE_THUMBNAIL)
        self.generate_thumbnail = patcher.start()
        self.addCleanup(patcher.stop)

    def test_queues_the_thumbnail_job_for_that_media(self):
        media = create_media(create_album(), processing_status=Media.STATUS_PENDING)

        response = self.client.post(confirm_url(media.pk))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # The id (not the object): Celery serializes arguments as JSON.
        self.generate_thumbnail.delay.assert_called_once_with(media.pk)

    def test_returns_the_media_still_pending(self):
        # Going from pending to ready is the worker's job, not this endpoint's.
        media = create_media(create_album(), processing_status=Media.STATUS_PENDING)

        response = self.client.post(confirm_url(media.pk))

        self.assertEqual(set(response.json()), MEDIA_FIELDS)
        self.assertEqual(response.json()["id"], media.pk)
        self.assertEqual(response.json()["processing_status"], "pending")
        media.refresh_from_db()
        self.assertEqual(media.processing_status, Media.STATUS_PENDING)

    def test_only_the_confirmed_media_is_queued(self):
        album = create_album()
        create_media(album)
        target = create_media(album)

        self.client.post(confirm_url(target.pk))

        self.generate_thumbnail.delay.assert_called_once_with(target.pk)

    def test_unknown_media_is_404_and_queues_nothing(self):
        response = self.client.post(confirm_url(999999))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.generate_thumbnail.delay.assert_not_called()

    def test_soft_deleted_media_is_404_and_queues_nothing(self):
        media = create_media(create_album())
        soft_delete(media)

        response = self.client.post(confirm_url(media.pk))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.generate_thumbnail.delay.assert_not_called()

    def test_the_full_upload_flow(self):
        album = create_album()
        created = self.client.post(
            upload_url(), upload_payload(album), format="json"
        ).json()["media"]

        confirmed = self.client.post(confirm_url(created["id"]))

        self.assertEqual(confirmed.status_code, status.HTTP_200_OK)
        self.generate_thumbnail.delay.assert_called_once_with(created["id"])


class MediaKnownGapTests(AuthenticatedAPITestCase):
    """
    Behaviour the API SHOULD have but does not yet (found while writing these
    tests). They assert the correct behaviour and are marked `expectedFailure`,
    so the suite stays green today. Once the view is fixed a test here turns
    into an "unexpected success" and fails the run: remove its decorator then.
    """

    @expectedFailure
    def test_an_unknown_media_type_is_rejected(self):
        # Today "document" is accepted with a 201 and saved as the type.
        album = create_album()

        response = self.client.post(
            upload_url(), upload_payload(album, type="document"), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Media.objects.count(), 0)

    @expectedFailure
    def test_a_non_numeric_size_is_a_400_not_a_server_error(self):
        # Today this is an unhandled ValueError (HTTP 500).
        response = self.client.post(
            upload_url(), upload_payload(create_album(), size="abc"), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @expectedFailure
    def test_a_negative_size_is_a_400_not_a_server_error(self):
        # Today the database rejects it and the request ends in an HTTP 500.
        response = self.client.post(
            upload_url(), upload_payload(create_album(), size=-5), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @expectedFailure
    def test_a_malformed_album_id_is_not_a_server_error(self):
        # Today the lookup raises ValueError (HTTP 500).
        payload = {**upload_payload(create_album()), "album": "abc"}

        response = self.client.post(upload_url(), payload, format="json")

        self.assertIn(
            response.status_code,
            (status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND),
        )

    @expectedFailure
    def test_the_plain_create_endpoint_does_not_make_file_less_records(self):
        # POST /api/media/ is the stock ModelViewSet create. storage_key is
        # read-only there, so it saves a record with an empty key (and a second
        # one crashes on the unique constraint). Uploads must go through
        # presigned-upload.
        album = create_album()

        self.client.post(
            list_url(),
            {
                "album": album.pk,
                "type": "photo",
                "original_filename": "x.jpg",
                "size": 1,
                "content_type": "image/jpeg",
            },
            format="json",
        )

        self.assertFalse(Media.objects.filter(storage_key="").exists())
