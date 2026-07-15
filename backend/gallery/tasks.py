"""
The async worker: given a Media that was just uploaded to the bucket,
generate its thumbnail and fill in the metadata the upload flow couldn't
know on its own (dimensions, duration, EXIF capture date).
"""

import io
import json
import os
import subprocess
import tempfile
from datetime import datetime

from celery import shared_task
from django.utils import timezone
from PIL import ExifTags, Image, ImageOps

from .models import Media
from .services import build_thumbnail_key, download_object, upload_bytes

THUMBNAIL_MAX_SIZE = (800, 800)


def _process_photo(media: Media) -> None:
    original_bytes = download_object(media.storage_key)
    image = Image.open(io.BytesIO(original_bytes))
    # Portrait phone photos carry an EXIF Orientation tag instead of storing
    # pixels pre-rotated; without this, width/height and the thumbnail can
    # end up sideways relative to how every viewer renders the original.
    image = ImageOps.exif_transpose(image) or image

    media.width, media.height = image.size
    media.taken_at = _read_exif_taken_at(image) or media.taken_at

    thumbnail = image.convert("RGB")
    thumbnail.thumbnail(THUMBNAIL_MAX_SIZE)

    buffer = io.BytesIO()
    thumbnail.save(buffer, format="JPEG", quality=85)

    thumbnail_key = build_thumbnail_key(media.storage_key)
    upload_bytes(thumbnail_key, buffer.getvalue(), "image/jpeg")
    media.thumbnail_key = thumbnail_key


def _read_exif_taken_at(image: "Image.Image"):
    try:
        exif = image.getexif()
    except Exception:
        return None
    if not exif:
        return None

    # DateTimeOriginal lives in the Exif sub-IFD (pointed to by tag 0x8769),
    # not the base IFD that getexif() returns directly — it has to be
    # fetched explicitly or it silently looks missing on most real photos.
    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)

    tag_ids = {name: tag_id for tag_id, name in ExifTags.TAGS.items()}
    for tag_name in ("DateTimeOriginal", "DateTime"):
        tag_id = tag_ids.get(tag_name)
        raw = exif_ifd.get(tag_id) or exif.get(tag_id)
        if not raw:
            continue
        try:
            naive = datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
            return timezone.make_aware(naive)
        except (ValueError, TypeError):
            continue
    return None


def _process_video(media: Media) -> None:
    """
    Requires the `ffmpeg` and `ffprobe` binaries on the worker's machine —
    these are system dependencies, not pip packages (see requirements.txt).
    """
    original_bytes = download_object(media.storage_key)

    # NamedTemporaryFile can't be reopened by a second process while our
    # handle is still open (fails with PermissionError on Windows), and
    # ffprobe/ffmpeg need to open these paths themselves. mkstemp + closing
    # our own fd before handing the path to subprocess avoids that.
    source_fd, source_path = tempfile.mkstemp(suffix=".mp4")
    thumb_fd, thumb_path = tempfile.mkstemp(suffix=".jpg")
    try:
        with os.fdopen(source_fd, "wb") as source:
            source.write(original_bytes)
        os.close(thumb_fd)

        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                source_path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        info = json.loads(probe.stdout)
        video_stream = next(s for s in info["streams"] if s["codec_type"] == "video")

        media.width = video_stream.get("width")
        media.height = video_stream.get("height")
        media.duration = int(float(info["format"].get("duration", 0)))

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                source_path,
                "-ss",
                "00:00:01.000",
                "-vframes",
                "1",
                thumb_path,
            ],
            capture_output=True,
            check=True,
        )

        thumbnail_key = build_thumbnail_key(media.storage_key)
        with open(thumb_path, "rb") as thumb:
            upload_bytes(thumbnail_key, thumb.read(), "image/jpeg")
        media.thumbnail_key = thumbnail_key
    finally:
        os.unlink(source_path)
        os.unlink(thumb_path)


@shared_task(bind=True, max_retries=2, autoretry_for=(Exception,), retry_backoff=True)
def generate_thumbnail(self, media_id: int) -> None:
    try:
        media = Media.objects.get(pk=media_id)
    except Media.DoesNotExist:
        return  # the Media was deleted before the task got to run

    try:
        if media.type == Media.TYPE_PHOTO:
            _process_photo(media)
        else:
            _process_video(media)
        media.processing_status = Media.STATUS_READY
        media.save()
    except Exception:
        # Only mark it as a hard error once retries are exhausted — earlier
        # failures are just transient blips autoretry_for will retry.
        if self.request.retries >= self.max_retries:
            media.processing_status = Media.STATUS_ERROR
            media.save(update_fields=["processing_status"])
        raise  # autoretry_for schedules a retry (up to max_retries)
