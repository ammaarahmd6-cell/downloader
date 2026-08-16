# MediaDL — Production-Grade Media Downloader

A full-stack media downloader built with FastAPI, Celery, Next.js, and yt-dlp.

## Features

- **URL Analysis** — Paste any URL from YouTube, Vimeo, SoundCloud, and 1000+ other sites
- **Format Selection** — Choose from all available video/audio quality options
- **Background Processing** — Jobs run in Celery workers, non-blocking API
- **Real-time Progress** — Live progress updates with speed and ETA
- **Secure File Serving** — Path traversal protection, expiring download links
- **SSRF Protection** — Private IP blocking, scheme validation
- **Rate Limiting** — Configurable per-endpoint rate limits
- **Auto Cleanup** — Expired files and stale jobs cleaned automatically
- **Dark/Light Theme** — Fully responsive, accessible UI
- **Docker Ready** — One-command production deployment

## Architecture

```
Frontend (Next.js 15)
       ↓
Backend (FastAPI)  →  PostgreSQL / SQLite
       ↓
     Redis
       ↓
  Celery Worker
       ↓
  yt-dlp + FFmpeg
       ↓
  File Storage
```

## Requirements

- Python 3.12+
- Node.js 20+
- FFmpeg
- Redis (or fakeredis for dev)
- PostgreSQL (or SQLite for dev)

## Quick Start (Local Development)

### 1. Clone and set up backend

```bash
cd backend
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

### 2. Configure environment

Edit `backend/.env`:
- Set `DATABASE_URL` (SQLite default works out of the box)
- Set `USE_FAKE_REDIS=true` to skip Redis installation for dev
- Set `FFMPEG_PATH` if ffmpeg is not on PATH

### 3. Start the backend

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Start the Celery worker (new terminal)

```bash
cd backend
.venv\Scripts\activate  # or source .venv/bin/activate
celery -A app.workers.celery_app worker -P solo -l info
```

> **Note**: `-P solo` is required on Windows. On Linux use default `-c 2`.

### 5. Set up and start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./mediadl.db` | Database connection string |
| `USE_FAKE_REDIS` | `true` | Use in-memory Redis for dev |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis URL (if not fake) |
| `FFMPEG_PATH` | `ffmpeg` | Path to ffmpeg binary |
| `MAX_CONCURRENT_JOBS` | `3` | Max simultaneous jobs |
| `FILE_RETENTION_SECONDS` | `3600` | How long to keep completed files |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | CORS allowed origins |
| `FRONTEND_URL` | `http://localhost:3000` | Frontend URL |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `GET` | `/ready` | Readiness check (DB, Redis, FFmpeg) |
| `POST` | `/api/info` | Analyze a media URL |
| `POST` | `/api/download` | Create download job |
| `GET` | `/api/jobs/{id}` | Job status & progress |
| `GET` | `/api/jobs/{id}/file` | Download completed file |
| `POST` | `/api/jobs/{id}/cancel` | Cancel a job |
| `GET` | `/api/admin/stats` | Admin statistics |
| `GET` | `/docs` | OpenAPI documentation |

## Docker Deployment

```bash
# Set environment variables
export SECRET_KEY=your-long-random-secret
export POSTGRES_PASSWORD=your-db-password

docker compose up --build
```

The stack includes: PostgreSQL, Redis, FastAPI backend, Celery worker, Next.js frontend.

## Testing

```bash
cd backend
.venv\Scripts\activate
pytest tests/ -v
```

## Linting

```bash
# Backend
cd backend && .venv\Scripts\ruff.exe check .

# Frontend
cd frontend && npm run lint
```

## Security Notes

- User-supplied URLs are validated against SSRF attack vectors
- Private IP ranges (10.x, 192.168.x, 172.16.x, 127.x, 169.254.x) are blocked
- All filenames are sanitized before filesystem use
- File serving uses path traversal protection
- FFmpeg is called with argument arrays (no shell injection)
- Rate limiting on analysis and download endpoints

## Legal / Acceptable Use

MediaDL is intended for downloading content you have the **legal right** to access:
- Your own uploaded content
- Content under Creative Commons or other open licenses  
- Content where the platform explicitly permits downloading

Do **not** use this tool to:
- Circumvent DRM or access controls
- Download private or paywalled content without authorization
- Violate any platform's Terms of Service
- Infringe on copyright

## Troubleshooting

**FFmpeg not found**: Set `FFMPEG_PATH` to the full path of the ffmpeg binary in your `.env` file.

**Celery won't start on Windows**: Use `-P solo` flag: `celery -A app.workers.celery_app worker -P solo`

**Database errors**: Delete `mediadl.db` and restart — the app will recreate it.

**CORS errors**: Add your frontend URL to `ALLOWED_ORIGINS` in `.env`.
