"""
Thin wrapper around boto3 for talking to Cloudflare R2 (S3-compatible API).
Nothing here touches Django models directly — it only knows about bytes,
keys, and URLs, so it's easy to swap providers later if needed.
"""

import uuid
from pathlib import Path

import boto3
from botocore.client import Config
from django.conf import settings

PRESIGNED_UPLOAD_EXPIRES_IN = 60 * 15  # 15 minutes — enough for a slow upload to start


def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def build_storage_key(album_id: int, original_filename: str) -> str:
    """
    Generates a unique, collision-proof key for the bucket. We never trust
    the client-provided filename as the actual key — only as display text
    (stored separately in Media.original_filename).
    """
    ext = Path(original_filename).suffix.lower()
    return f"albums/{album_id}/{uuid.uuid4().hex}{ext}"


def build_thumbnail_key(storage_key: str) -> str:
    return storage_key.rsplit(".", 1)[0] + "-thumb.jpg"


def generate_presigned_upload_url(storage_key: str, content_type: str) -> str:
    """
    Returns a URL the frontend can PUT the raw file bytes to, directly from
    the browser. The backend never receives the file itself.
    """
    client = get_r2_client()
    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.R2_BUCKET_NAME,
            "Key": storage_key,
            "ContentType": content_type,
        },
        ExpiresIn=PRESIGNED_UPLOAD_EXPIRES_IN,
    )


def download_object(storage_key: str) -> bytes:
    """Used by the thumbnail worker to read the original file's bytes."""
    client = get_r2_client()
    response = client.get_object(Bucket=settings.R2_BUCKET_NAME, Key=storage_key)
    return response["Body"].read()


def upload_bytes(storage_key: str, data: bytes, content_type: str) -> None:
    """Used by the thumbnail worker to write the generated thumbnail back."""
    client = get_r2_client()
    client.put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=storage_key,
        Body=data,
        ContentType=content_type,
    )


def delete_object(storage_key: str) -> None:
    """Used when purging a soft-deleted Media/Album for good."""
    if not storage_key:
        return
    client = get_r2_client()
    client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=storage_key)