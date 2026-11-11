# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A personal web app to store and share trip photos/videos, replacing Google Drive. Media is served in its **original quality** (no compression/re-encoding on delivery). There is exactly **one admin user** (the owner) who uploads, organizes into albums, and shares albums via link. Visitors who open a share link get **read-only** access to a grid gallery — no accounts, no registration.

## Repository layout (monorepo)

This is a single repo with two independently deployable parts:

```
/frontend   Next.js (React + TypeScript) — deployed to Vercel, root directory = /frontend
/backend    Django REST Framework + PostgreSQL — deployed to Railway, root directory = /backend
```

Each platform is configured to build only from its subfolder. Keep this separation clean — the frontend never talks directly to the storage bucket's admin credentials, and the backend never serves media bytes itself (see architecture below).

## Core architecture decisions (load-bearing — do not casually deviate)

- **Uploads never pass through Django.** The backend issues a presigned URL; the browser (or an upload script for bulk imports) uploads the file directly to the object storage bucket (Cloudflare R2, S3-compatible API). Large video uploads use multipart upload. Do not add endpoints that stream file bytes through the Django app.
- **The backend is not in the hot path of media delivery.** Actual photo/video bytes are served to visitors by a Cloudflare CDN / Cloudflare Worker sitting in front of the bucket, not proxied through Railway. The backend's job is metadata (albums, media records, share-link tokens), not bandwidth.
- **The storage bucket is always private.** No public bucket access. A Cloudflare Worker validates the share-link token (and password/expiration, if set) before forwarding a request to the bucket.
- **Single admin, no public registration.** Auth is for the owner only. `CustomUser` authenticates by email (`USERNAME_FIELD = "email"`). There is no signup flow for visitors.
- **Sharing is token-based**, not account-based. See `ShareLink`: a random unguessable token (`secrets.token_urlsafe`), optional hashed password, optional expiration, and an `is_active` flag to revoke without deleting the album.
- **Soft delete on `Album` and `Media`** via `deleted_at`. Prefer marking as deleted over hard-deleting; actual bucket purge happens later (not yet implemented — flag this as a TODO when building the delete flow).
- **Thumbnails are generated asynchronously** by a Celery + Redis worker (`backend/gallery/tasks.py`, `backend/celery_app.py`), not synchronously in the request/response cycle. `Media.processing_status` tracks pending/ready/error so the frontend knows when a thumbnail is ready.
- **Current stopgap for media URLs:** the Cloudflare Worker/CDN layer is not built yet, so the backend signs short-lived (15 min) presigned R2 download URLs (`generate_presigned_download_url`). These URLs change on every request, so browsers cannot cache the images. The planned fix is stable CDN URLs from the Worker (long `Cache-Control` on thumbnails); do not build more features that depend on presigned download URLs being stable.

## Performance conventions (load-bearing — keep these when changing the backend/frontend)

The history, reasoning and local measurements for each of these live in `/performance/` (numbered notes). **When you make a performance change, add or update a note there.**

- **Never build a boto3 client per call.** `get_r2_client()` is `@lru_cache`d: one client per process. A request can sign hundreds of URLs (2 per media item), and constructing a client each time was the biggest cost.
- **No N+1 queries in serializers.** Anything a serializer reads per row must be loaded by the view's queryset: `select_related("cover")` for the cover, and `Album.objects.with_media_count()` (custom `AlbumQuerySet`) for the count of non-deleted media. Serializers read the annotated `media_count` and only fall back to a query when it is missing. Check query counts when adding fields to list/detail serializers.
- **Soft delete must survive optimizations.** Any annotate/prefetch over `media` or `children` has to filter `deleted_at__isnull=True`. Note a plain `.filter()` ignores a prefetch cache, so prefetched data is read from `to_attr` attributes (`active_media`, `active_children`).
- **Two album detail serializers, on purpose:**
  - `AlbumAdminDetailSerializer` — used by `AlbumViewSet` for every action except `list` (including create/update responses). Sub-albums (`children`) are `AlbumChildSerializer`: cover + `media_count`, **no `media`**.
  - `AlbumDetailSerializer` — used only by the public share-link view. Sub-albums keep their full `media`, because the public lightbox needs them. `public_album_api.py` loads the tree in a fixed number of queries with `Prefetch(..., to_attr=...)`.
  - The frontend mirrors this split: `AlbumAdminDetail*` / `AlbumChild*` types for the admin panel, `AlbumDetail*` for the public gallery.
- **Sub-albums are one level only**, so a sub-album never has children: serializers skip that query (`parent_id is not None` → `[]`).
- **Settings come from the environment.** `DEBUG` defaults to `False` and `SECRET_KEY` has no default (Django refuses to start without it). Never hardcode either. Keep `GZipMiddleware` enabled (album JSON compresses ~10x) and DB connection reuse (`CONN_MAX_AGE`, `CONN_HEALTH_CHECKS`).

## Data model (backend/gallery/models/)

- `Album` — a trip/collection. Has `name`, `slug` (auto-generated, unique), `description`, `start_date`/`end_date`, `cover` (FK to a `Media` used as cover image), `parent` (self FK for sub-albums, **one level deep only**, enforced in the serializer), soft-delete via `deleted_at`. Its manager is `AlbumQuerySet.as_manager()`, which adds `with_media_count()`; a manager like this needs no migration.
- `Media` — **unified model for both photos and videos** (deliberate choice over separate `Photo`/`Video` tables, since almost all fields are shared). `type` distinguishes `"photo"` / `"video"`. Key fields: `storage_key` (the real bucket key — required to locate the file; `original_filename` is just display text), `thumbnail_key`, `width`/`height`, `duration` (nullable, video-only, stored in seconds not `DurationField`), `taken_at` (EXIF capture date, distinct from `created_at` upload date — this is what albums should sort by for chronological trip order), `order` for manual ordering, `processing_status`.
- `ShareLink` — share link for an `Album`. Token auto-generated on save if empty. Password is hashed via `set_password()`/`check_password()` helper methods (mirrors Django's `make_password`/`check_password`), never stored in plaintext.
- `CustomUser` — extends `AbstractUser`, email-based login.

## Naming convention

**Code is in English, user-facing content is in Spanish** — these are two different layers, don't mix them up:

- All backend model/field names, function/variable names, folder names, and code comments are in **English** (`name`, `size`, `created_at`, `deleted_at`, `taken_at`, `ShareLink`, etc.). Keep this consistent across new models, serializers, API field names, and frontend code (components, hooks, variables, comments) — this applies to both `/backend` and `/frontend`.
- **User-facing content is in Spanish.** This means actual data the owner creates and visitors see: album names/titles, descriptions, UI copy/labels rendered on screen, error messages shown to the user, button text, etc. This is *data and UI text*, not code — e.g. an `Album.name` value like `"Viaje a Bariloche"` is completely normal and expected; the field is called `name` (English), but what the owner types into it is Spanish.

## Deployment targets

- **Frontend:** Vercel, Hobby (free) tier — non-commercial only. Media assets are expected to load from the Cloudflare CDN domain directly, not through Vercel's own bandwidth.
- **Backend:** Railway, Hobby plan ($5/mo included usage) — Postgres add-on lives in the same project. Note: Railway's serverless "sleep after 10 min idle" feature can apply to the Django service to save cost, but will *not* apply to Postgres (active DB connections keep it from sleeping).
- **Storage/CDN:** Cloudflare R2 (S3-compatible) + Cloudflare Worker for token validation + CDN caching at the edge.
- **Required backend environment variables** (set them on **both** the Django service and the Celery worker service, which load the same settings): `SECRET_KEY` (required, generate a new one, never reuse a value that was ever committed), `DEBUG=False`, `ALLOWED_HOSTS` (the backend's public domain), `DATABASE_URL`, `REDIS_URL`, `FRONTEND_URL`, and the `R2_*` credentials. Optional: `DB_CONN_MAX_AGE` (default 60; `0` disables connection reuse). Deploy the new variables **before** merging code that requires them.

@../.claude/react-ts-teaching.md
@../.claude/django-drf-teaching.md
