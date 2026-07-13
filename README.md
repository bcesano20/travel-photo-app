# Travel Photo App

A personal web app to store and share trip photos and videos in their **original quality**, without relying on Google Drive. There is a single admin (the owner) who uploads and organizes content into albums; visitors open a share link and get read-only access to a grid gallery — no accounts, no sign-up.


## Features

- Albums to organize photos/videos by trip, with cover image and date range.
- Direct-to-bucket uploads (presigned URLs) — large files never pass through the backend.
- Async thumbnail generation via a background worker, so the UI stays responsive during bulk uploads.
- Read-only share links per album, with optional password and expiration, revocable at any time.
- Media served through a CDN in its original resolution/bitrate — no re-encoding, no quality loss.

## Tech stack

- **Frontend:** Next.js, React, TypeScript, Tailwind CSS — deployed to Vercel.
- **Backend:** Django REST Framework, PostgreSQL — deployed to Railway.
- **Worker:** Celery + Redis, for thumbnail generation and EXIF/metadata extraction.
- **Storage/CDN:** Cloudflare R2 (S3-compatible) behind a Cloudflare Worker (share-link token validation) and CDN caching.

## Project structure

```
.
├── CLAUDE.md          # architecture notes and conventions for AI coding agents
├── README.md
├── .gitignore
├── backend/           # Django REST Framework API
│   ├── manage.py
│   ├── settings.py    # project config lives flat at backend/ root (no config/ subfolder)
│   ├── urls.py
│   ├── wsgi.py
│   ├── asgi.py
│   └── gallery/       # the single Django app: albums, media, share links, custom user
│       ├── models/
│       ├── serializers/
│       ├── views/
│       ├── admin.py
│       └── apps.py
└── frontend/          # Next.js app (admin panel + public gallery)
    └── ...
```

## Prerequisites

- Python 3.11+
- Node.js 20+ and npm (or pnpm)
- PostgreSQL 15+ (local install or Docker)
- Redis (local install or Docker) — required for the Celery worker
- A Cloudflare R2 bucket + API token (a dev/test bucket is fine for local work)

## Getting started

### 1. Backend (Django REST Framework)

```bash
cd backend
python -m venv travel-photo
source travel-photo/bin/activate
# Windows: travel-photo\Scripts\activate

pip install -r requirements.txt

cp .env.example .env             # then fill in the values, see below
python manage.py migrate
python manage.py createsuperuser # prompts for email, not username (custom user model)
python manage.py runserver
```

The API will be available at `http://localhost:8000`. The Django admin (`/admin`) is usable as a stopgap panel for managing albums/media before the custom frontend panel is built.

Formatting (Black + isort) is enforced in CI on every PR touching `backend/`. To check locally before pushing:

```bash
cd backend
black --check --diff .
isort --check-only --diff .
```

To auto-fix, drop `--check`/`--check-only` (and `--diff`): `black .` and `isort .`.

### 2. Worker (Celery, for thumbnail generation)

Needs Redis running locally first:

```bash
docker run -d --name redis -p 6379:6379 redis:7
```

Then, from `backend/`, in the same virtual environment:

```bash
celery -A gallery worker -l info
```

(Not yet implemented — see `CLAUDE.md` for the planned Celery setup.)

Without the worker running, uploaded media will stay stuck in `processing_status = pending` and thumbnails won't be generated — the API will still work, but the gallery grid won't have preview images.

### 3. Frontend (Next.js)

```bash
cd frontend
npm install
cp .env.example .env.local       # then fill in the values, see below
npm run dev
```

The app will be available at `http://localhost:3000`.

## Environment variables

**`backend/.env`**

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` locally, `False` in production |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Used by Celery as the broker |
| `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` | Cloudflare R2 credentials, used to generate presigned upload URLs |
| `FRONTEND_URL` | Used for CORS and building share-link URLs |

**`frontend/.env.local`**

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | Base URL of the Django API (e.g. `http://localhost:8000`) |
| `NEXT_PUBLIC_CDN_URL` | Base URL media is served from (Cloudflare CDN/Worker domain) |

## Deployment

- **Frontend** → Vercel, root directory set to `/frontend`.
- **Backend + Postgres** → Railway, root directory set to `/backend`.
- **Storage/CDN** → Cloudflare R2 + Worker, independent of the above.
