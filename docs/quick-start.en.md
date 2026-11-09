# Quick Start Guide

[中文](quick-start.md) | **English**

This guide walks you through running the **Online Exam System** locally from scratch.

The system runs **natively without Docker** and consists of 5 local components: **PostgreSQL**, **Redis**, **FastAPI Backend API**, **ARQ Background Worker**, and **Vite Frontend**.

> **Shell Note**: Manual setup commands below use Bash syntax (Git Bash is recommended on Windows). After completing your first-time configuration and database migration, you can launch the entire stack with a single PowerShell command.

---

## Windows Quick Start

Once dependencies are installed, `backend/.env` is filled in, and the database is migrated, run the following command from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-local.ps1
```

**What this script does automatically:**
1. Verifies required CLI tools and checks that the database is at the latest Alembic migration head.
2. Sequentially starts PostgreSQL, Redis, the FastAPI backend (`18000`), the ARQ worker, and the Vite frontend (`5173`).
3. Reuses any service that is already running; fails with a clear message if a port is occupied by an unrelated process.
4. Verifies PostgreSQL reads, Redis connectivity, backend health, and the frontend `/api` proxy. Once complete, open `http://127.0.0.1:5173`.

### Script Notes

- **Local Data Layout**: Designed for a Windows + WSL development setup. If PostgreSQL is not running, the script starts it using `.local/pgdata`; if Redis is not running, it launches Redis inside WSL (`Ubuntu-24.04`) with `.local/redis.conf`. Both paths must be initialized beforehand—the script never creates credentials, wipes databases, installs packages, or runs migrations automatically.
- **Custom PostgreSQL Path**: `pg_ctl.exe` is resolved from `PATH` or `D:\postgresql\bin\pg_ctl.exe` by default. Pass `-PgCtl 'C:\your\path\pg_ctl.exe'` if installed elsewhere:
  ```powershell
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-local.ps1 -PgCtl 'C:\your\path\pg_ctl.exe'
  ```
- **Where to Find Logs**: Diagnostic outputs for infrastructure and Vite are written to `.local/services/`, and process metadata is recorded in `.local/service-state.json` (both ignored by Git). Application logs for the API and worker are managed directly through the administrator **[System Logs](logging.en.md)** page (file logging is off by default). If the API or worker exits immediately on startup, run the manual commands below in the foreground to inspect startup errors.
- **Automated Terminal Keep-Alive**: Append `-KeepAlive` when invoking the script from an automation harness that reaps child process trees on exit; interactive PowerShell sessions do not need this flag.

---

## First-Time Setup: Step-by-Step Manual Startup

Follow these 5 steps the first time you clone the repository.

### Step 1: Prepare Base Services

Verified runtime versions (exact package versions are locked in `backend/uv.lock` and `frontend/package-lock.json`):

- **Python**: `3.13` + **uv** `0.10`
- **Node.js**: `24` + **npm**
- **PostgreSQL**: `18`
- **Redis**: `8` (on Windows, running Redis in WSL is recommended; ensure Windows can reach its listening address)

**Before starting the app:**
1. Create a dedicated PostgreSQL database for this project (do **not** reuse your automated test database as your daily development database) and a user with schema migration privileges.
2. Start a password-authenticated Redis instance.
3. **Sample Local Ports**: PostgreSQL `55432`, Redis `16379`, Backend API `18000`, Frontend `5173` (you can use your existing ports ifPostgreSQL/Redis are already running).

---

### Step 2: Configure Backend, Migrate Database & Start API

From the repository root, sync Python dependencies and create `backend/.env`:

```bash
cd backend
uv sync --locked --python 3.13
# Copy template only on first setup; preserve existing .env if present
test -f .env || cp .env.example .env
```

Edit `backend/.env` and replace at least the following values:

| Variable | How to Configure | Purpose |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `development` | `development` for local use, `test` for automated tests, `production` for live deployment |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:port/dbname` | Async PostgreSQL URL; **reserved characters in passwords (`@`, `:`, `/`) must be URL-encoded** |
| `REDIS_URL` | `redis://:pass@host:port/0` | Redis URL for auth sessions and (by default) the ARQ background queue |
| `JWT_SECRET` | Random secret (`>= 32` chars) | Secret key for signing tokens; **always replace the example placeholder** |
| `ADMIN_LOGIN_NAME` | e.g., `admin` | Login name for the initial system administrator |
| `ADMIN_PASSWORD` | Strong password (`>= 10` chars) | Initial administrator password |
| `ADMIN_REAL_NAME` / `EMAIL` / `PHONE_NUMBER` | Admin profile fields | Display name, email, and phone number for the administrator |
| `CORS_ORIGINS` | `http://127.0.0.1:5173` | Allowed frontend origin (must match the exact hostname used in your browser) |
| `ASSET_STORAGE_DIR` | e.g., `../.local/assets` | Persistent directory for uploaded question images (relative to `backend/` working directory) |
| `LOG_STORAGE_DIR` | Default `../.local/logs` | Directory for server `.log` files; API, worker, and CLI must share the same path |

> **Security Note**: Keep `COOKIE_SECURE=false` for local HTTP development. Production deployments must use HTTPS with `ENVIRONMENT=production` and `COOKIE_SECURE=true`. Never commit real credentials or pass passwords directly on the command line.

Next, run **database migrations → administrator initialization → API server**:

```bash
uv run alembic upgrade head
uv run python -m app.cli init-admin
uv run uvicorn app.main:app --host 127.0.0.1 --port 18000
```

- **About the Administrator Account**: There is no web sign-up page for administrators; the account is provisioned via `init-admin`. Running `init-admin` again will **not** overwrite an existing administrator's password. To reset a forgotten admin password, follow **[Operations Guide: Administrator & Session Recovery](operations.en.md#5-administrator--session-recovery)**.

---

### Step 3: Start the Background ARQ Worker

Leave the API terminal running and open a **second terminal**:

```bash
cd backend
uv run arq app.workers.attempts.WorkerSettings
```

**Why is the worker required?**
- Timeout auto-submissions, automated objective grading after submission, and balanced distribution of short-answer grading tasks all run in this worker process.
- The worker immediately recovers any pending database tasks on startup and scans every 30 seconds thereafter.
- **Configuration Alignment**: The API and worker must point to the exact same `DATABASE_URL`, `ARQ_REDIS_URL` (defaults to `REDIS_URL`), and `ARQ_QUEUE_NAME`.

---

### Step 4: Start the Frontend Dev Server

Open a **third terminal**:

```bash
cd frontend
npm ci
# If your API is not on http://127.0.0.1:18000, create .env.local and set VITE_API_TARGET
npm run dev
```

By default, Vite proxies `/api` requests to `http://127.0.0.1:18000`.

> **Important: Do Not Mix `localhost` and `127.0.0.1`!**
> Open `http://127.0.0.1:5173` and use `127.0.0.1` consistently throughout your session. Switching between `localhost` and `127.0.0.1` causes HttpOnly Cookie domain mismatches and unexpected logouts.

---

### Step 5: Verify & Start Using

1. **Health Check**:
   Visiting `http://127.0.0.1:18000/api/health` and `http://127.0.0.1:5173/api/health` should both return `{"status":"ok"}`.
2. **Walk Through Role Workflows**:
   - Log in at `http://127.0.0.1:5173` with your administrator account and create a teacher account (with a temporary password). The teacher will be prompted to set a new password on first login.
   - Students register themselves from the login page and can take exams once approved by a teacher or administrator.
   - See the **[Three-Role User Guide](user-guide.en.md)** for full workflows, or **[Repeatable Demo Data](demo.en.md)** to populate sample data automatically.

---

## Stopping Services & Production Build

- **Graceful Shutdown Order**: Stop Vite, the API server, and the ARQ worker (`Ctrl + C`) first, then shut down your project-dedicated Redis and PostgreSQL instances while keeping their data directories intact.
- **Production Frontend Build**: Run `cd frontend && npm run build`. Serve the generated `dist/` directory behind a static server (such as Nginx) configured with SPA history fallback to `index.html` and a same-origin `/api` reverse proxy—never use `npm run dev` in production.
