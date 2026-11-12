from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
from django.test import SimpleTestCase

from gallery.services import storage_service
from gallery.services.storage_service import (
    PRESIGNED_EXPIRES_IN,
    build_storage_key,
    build_thumbnail_key,
    delete_object,
    download_object,
    generate_presigned_download_url,
    generate_presigned_upload_url,
    get_r2_client,
    upload_bytes,
)
from gallery.utils.test_utils import (
    SAMPLE_ALBUM_ID,
    SAMPLE_BYTES,
    SAMPLE_CONTENT_TYPE,
    SAMPLE_STORAGE_KEY,
    SAMPLE_THUMBNAIL_KEY,
    TEST_R2_ACCESS_KEY_ID,
    TEST_R2_BUCKET_NAME,
    TEST_R2_ENDPOINT_URL,
    TEST_R2_SECRET_ACCESS_KEY,
    R2TestCase,
    parse_presigned_url,
)

BOTO3_CLIENT = "gallery.services.storage_service.boto3.client"
GET_R2_CLIENT = "gallery.services.storage_service.get_r2_client"


class GetR2ClientTests(R2TestCase):
    @patch(BOTO3_CLIENT)
    def test_builds_the_client_from_the_r2_settings(self, boto3_client):
        client = get_r2_client()

        self.assertIs(client, boto3_client.return_value)
        boto3_client.assert_called_once()
        args, kwargs = boto3_client.call_args
        self.assertEqual(args, ("s3",))
        self.assertEqual(kwargs["endpoint_url"], TEST_R2_ENDPOINT_URL)
        self.assertEqual(kwargs["aws_access_key_id"], TEST_R2_ACCESS_KEY_ID)
        self.assertEqual(kwargs["aws_secret_access_key"], TEST_R2_SECRET_ACCESS_KEY)
        self.assertEqual(kwargs["region_name"], "auto")
        self.assertEqual(kwargs["config"].signature_version, "s3v4")

    @patch(BOTO3_CLIENT)
    def test_builds_the_client_only_once(self, boto3_client):
        # A request can sign hundreds of URLs.
        first = get_r2_client()
        second = get_r2_client()
        third = get_r2_client()

        self.assertIs(first, second)
        self.assertIs(second, third)
        self.assertEqual(boto3_client.call_count, 1)

    @patch(BOTO3_CLIENT)
    def test_cache_clear_builds_a_new_client(self, boto3_client):
        boto3_client.side_effect = [MagicMock(name="first"), MagicMock(name="second")]

        first = get_r2_client()
        get_r2_client.cache_clear()
        second = get_r2_client()

        self.assertIsNot(first, second)
        self.assertEqual(boto3_client.call_count, 2)

    def test_real_client_is_shared_and_points_at_r2(self):
        client = get_r2_client()

        self.assertIs(client, get_r2_client())
        self.assertEqual(client.meta.endpoint_url, TEST_R2_ENDPOINT_URL)


class BuildStorageKeyTests(SimpleTestCase):
    def test_key_has_album_folder_uuid_and_extension(self):
        key = build_storage_key(SAMPLE_ALBUM_ID, "beach.jpg")

        self.assertRegex(key, rf"^albums/{SAMPLE_ALBUM_ID}/[0-9a-f]{{32}}\.jpg$")

    def test_extension_is_lowercased(self):
        key = build_storage_key(SAMPLE_ALBUM_ID, "IMG_0001.HEIC")

        self.assertTrue(key.endswith(".heic"))

    def test_only_the_last_extension_is_kept(self):
        key = build_storage_key(SAMPLE_ALBUM_ID, "archive.tar.gz")

        self.assertTrue(key.endswith(".gz"))
        self.assertNotIn("tar", key)

    def test_filename_without_extension_gives_a_key_without_extension(self):
        key = build_storage_key(SAMPLE_ALBUM_ID, "README")

        self.assertRegex(key, rf"^albums/{SAMPLE_ALBUM_ID}/[0-9a-f]{{32}}$")

    def test_hidden_file_name_is_not_treated_as_an_extension(self):
        key = build_storage_key(SAMPLE_ALBUM_ID, ".bashrc")

        self.assertRegex(key, rf"^albums/{SAMPLE_ALBUM_ID}/[0-9a-f]{{32}}$")

    def test_client_filename_is_never_used_as_the_key(self):
        key = build_storage_key(SAMPLE_ALBUM_ID, "../../etc/passwd.JPG")

        self.assertRegex(key, rf"^albums/{SAMPLE_ALBUM_ID}/[0-9a-f]{{32}}\.jpg$")
        self.assertNotIn("..", key)
        self.assertNotIn("passwd", key)

    def test_key_lives_in_the_given_albums_folder(self):
        self.assertTrue(build_storage_key(1, "a.jpg").startswith("albums/1/"))
        self.assertTrue(build_storage_key(42, "a.jpg").startswith("albums/42/"))

    def test_same_filename_never_collides(self):
        keys = {build_storage_key(SAMPLE_ALBUM_ID, "same.jpg") for _ in range(1000)}

        self.assertEqual(len(keys), 1000)


class BuildThumbnailKeyTests(SimpleTestCase):
    def test_replaces_the_extension_with_thumb_jpg(self):
        self.assertEqual(build_thumbnail_key(SAMPLE_STORAGE_KEY), SAMPLE_THUMBNAIL_KEY)

    def test_thumbnail_of_a_video_is_a_jpg(self):
        self.assertEqual(
            build_thumbnail_key("albums/7/abc.mp4"), "albums/7/abc-thumb.jpg"
        )

    def test_only_the_last_extension_is_replaced(self):
        self.assertEqual(
            build_thumbnail_key("albums/7/abc.def.png"), "albums/7/abc.def-thumb.jpg"
        )

    def test_key_without_extension_just_gets_the_suffix(self):
        self.assertEqual(build_thumbnail_key("albums/7/abc"), "albums/7/abc-thumb.jpg")

    def test_thumbnail_key_differs_from_the_original(self):
        self.assertNotEqual(build_thumbnail_key(SAMPLE_STORAGE_KEY), SAMPLE_STORAGE_KEY)

    def test_stays_in_the_same_folder_as_the_original(self):
        generated = build_storage_key(SAMPLE_ALBUM_ID, "photo.jpeg")

        thumbnail = build_thumbnail_key(generated)

        self.assertEqual(thumbnail.rsplit("/", 1)[0], generated.rsplit("/", 1)[0])


class PresignedDownloadUrlTests(R2TestCase):
    def test_url_points_at_the_object_in_the_bucket(self):
        parts = parse_presigned_url(generate_presigned_download_url(SAMPLE_STORAGE_KEY))

        self.assertEqual(parts["scheme"], "https")
        self.assertEqual(parts["host"], TEST_R2_ENDPOINT_URL.removeprefix("https://"))
        self.assertEqual(parts["path"], f"/{TEST_R2_BUCKET_NAME}/{SAMPLE_STORAGE_KEY}")

    def test_url_is_signed_and_expires_in_fifteen_minutes(self):
        query = parse_presigned_url(
            generate_presigned_download_url(SAMPLE_STORAGE_KEY)
        )["query"]

        self.assertEqual(query["X-Amz-Algorithm"], "AWS4-HMAC-SHA256")
        self.assertEqual(query["X-Amz-Expires"], str(PRESIGNED_EXPIRES_IN))
        self.assertTrue(query["X-Amz-Credential"].startswith(TEST_R2_ACCESS_KEY_ID))
        self.assertRegex(query["X-Amz-Signature"], r"^[0-9a-f]{64}$")

    def test_only_the_host_header_is_signed(self):
        # No Content-Type is bound to a download, so <img>/<video> can use it.
        query = parse_presigned_url(
            generate_presigned_download_url(SAMPLE_STORAGE_KEY)
        )["query"]

        self.assertEqual(query["X-Amz-SignedHeaders"], "host")

    def test_secret_access_key_never_appears_in_the_url(self):
        url = generate_presigned_download_url(SAMPLE_STORAGE_KEY)

        self.assertNotIn(TEST_R2_SECRET_ACCESS_KEY, url)

    def test_different_keys_get_different_signatures(self):
        first = parse_presigned_url(generate_presigned_download_url("albums/1/a.jpg"))
        second = parse_presigned_url(generate_presigned_download_url("albums/1/b.jpg"))

        self.assertNotEqual(
            first["query"]["X-Amz-Signature"], second["query"]["X-Amz-Signature"]
        )

    def test_empty_key_returns_an_empty_string(self):
        self.assertEqual(generate_presigned_download_url(""), "")

    @patch(GET_R2_CLIENT)
    def test_empty_key_does_not_even_build_a_client(self, get_client):
        generate_presigned_download_url("")

        get_client.assert_not_called()

    @patch(GET_R2_CLIENT)
    def test_asks_boto3_for_a_get_object_url(self, get_client):
        client = get_client.return_value
        client.generate_presigned_url.return_value = "https://signed.example/url"

        url = generate_presigned_download_url(SAMPLE_STORAGE_KEY)

        self.assertEqual(url, "https://signed.example/url")
        client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": TEST_R2_BUCKET_NAME, "Key": SAMPLE_STORAGE_KEY},
            ExpiresIn=PRESIGNED_EXPIRES_IN,
        )


class PresignedUploadUrlTests(R2TestCase):
    def test_url_points_at_the_object_in_the_bucket(self):
        url = generate_presigned_upload_url(SAMPLE_STORAGE_KEY, SAMPLE_CONTENT_TYPE)

        parts = parse_presigned_url(url)

        self.assertEqual(parts["scheme"], "https")
        self.assertEqual(parts["host"], TEST_R2_ENDPOINT_URL.removeprefix("https://"))
        self.assertEqual(parts["path"], f"/{TEST_R2_BUCKET_NAME}/{SAMPLE_STORAGE_KEY}")

    def test_url_is_signed_and_expires_in_fifteen_minutes(self):
        url = generate_presigned_upload_url(SAMPLE_STORAGE_KEY, SAMPLE_CONTENT_TYPE)

        query = parse_presigned_url(url)["query"]

        self.assertEqual(query["X-Amz-Algorithm"], "AWS4-HMAC-SHA256")
        self.assertEqual(query["X-Amz-Expires"], str(PRESIGNED_EXPIRES_IN))
        self.assertTrue(query["X-Amz-Credential"].startswith(TEST_R2_ACCESS_KEY_ID))
        self.assertRegex(query["X-Amz-Signature"], r"^[0-9a-f]{64}$")

    def test_content_type_is_part_of_the_signature(self):
        # The browser must PUT with exactly this Content-Type, otherwise R2
        # rejects the upload: it can't be swapped for something else.
        url = generate_presigned_upload_url(SAMPLE_STORAGE_KEY, SAMPLE_CONTENT_TYPE)

        signed_headers = parse_presigned_url(url)["query"]["X-Amz-SignedHeaders"]

        self.assertIn("content-type", signed_headers.split(";"))

    def test_different_content_types_get_different_signatures(self):
        image = parse_presigned_url(
            generate_presigned_upload_url(SAMPLE_STORAGE_KEY, "image/jpeg")
        )
        video = parse_presigned_url(
            generate_presigned_upload_url(SAMPLE_STORAGE_KEY, "video/mp4")
        )

        self.assertNotEqual(
            image["query"]["X-Amz-Signature"], video["query"]["X-Amz-Signature"]
        )

    @patch(GET_R2_CLIENT)
    def test_asks_boto3_for_a_put_object_url(self, get_client):
        client = get_client.return_value
        client.generate_presigned_url.return_value = "https://signed.example/put"

        url = generate_presigned_upload_url(SAMPLE_STORAGE_KEY, SAMPLE_CONTENT_TYPE)

        self.assertEqual(url, "https://signed.example/put")
        client.generate_presigned_url.assert_called_once_with(
            "put_object",
            Params={
                "Bucket": TEST_R2_BUCKET_NAME,
                "Key": SAMPLE_STORAGE_KEY,
                "ContentType": SAMPLE_CONTENT_TYPE,
            },
            ExpiresIn=PRESIGNED_EXPIRES_IN,
        )


class ObjectOperationsTests(R2TestCase):
    """download_object / upload_bytes / delete_object, with a fake client."""

    def setUp(self):
        super().setUp()
        self.client = MagicMock(name="r2_client")
        patcher = patch.object(storage_service, "get_r2_client")
        self.get_client = patcher.start()
        self.get_client.return_value = self.client
        self.addCleanup(patcher.stop)

    def test_download_object_returns_the_bytes_of_the_object(self):
        self.client.get_object.return_value = {
            "Body": MagicMock(read=lambda: SAMPLE_BYTES)
        }

        data = download_object(SAMPLE_STORAGE_KEY)

        self.assertEqual(data, SAMPLE_BYTES)
        self.client.get_object.assert_called_once_with(
            Bucket=TEST_R2_BUCKET_NAME, Key=SAMPLE_STORAGE_KEY
        )

    def test_download_object_propagates_storage_errors(self):
        self.client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "missing"}}, "GetObject"
        )

        with self.assertRaises(ClientError):
            download_object(SAMPLE_STORAGE_KEY)

    def test_upload_bytes_writes_the_data_with_its_content_type(self):
        result = upload_bytes(SAMPLE_THUMBNAIL_KEY, SAMPLE_BYTES, SAMPLE_CONTENT_TYPE)

        self.assertIsNone(result)
        self.client.put_object.assert_called_once_with(
            Bucket=TEST_R2_BUCKET_NAME,
            Key=SAMPLE_THUMBNAIL_KEY,
            Body=SAMPLE_BYTES,
            ContentType=SAMPLE_CONTENT_TYPE,
        )

    def test_upload_bytes_propagates_storage_errors(self):
        self.client.put_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "PutObject"
        )

        with self.assertRaises(ClientError):
            upload_bytes(SAMPLE_THUMBNAIL_KEY, SAMPLE_BYTES, SAMPLE_CONTENT_TYPE)

    def test_delete_object_removes_the_key_from_the_bucket(self):
        result = delete_object(SAMPLE_STORAGE_KEY)

        self.assertIsNone(result)
        self.client.delete_object.assert_called_once_with(
            Bucket=TEST_R2_BUCKET_NAME, Key=SAMPLE_STORAGE_KEY
        )

    def test_delete_object_with_an_empty_key_does_nothing(self):
        # A Media without a thumbnail has thumbnail_key == "": deleting it must
        # never reach the bucket (an empty key could target the wrong object).
        delete_object("")

        self.get_client.assert_not_called()
        self.client.delete_object.assert_not_called()
