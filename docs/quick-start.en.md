# Quick Start Guide

[中文](quick-start.md) | **English**

This guide walks you through running the **Online Exam System**. Two deployment modes are supported:

1. **[Docker Compose Deployment](#docker-compose-deployment)** (Recommended): Launches PostgreSQL 18, Redis 8, Alembic migration, FastAPI API, ARQ Worker, and Nginx web frontend in containers without installing Python/Node/PG/Redis on your host.
2. **[Windows Quick Start](#windows-quick-start) / [Manual Native Startup](#first-time-setup-step-by-step-manual-startup)**: Runs all 5 processes natively without Docker—ideal for active local development and debugging.

> **Shell Note**: Manual setup commands below use Bash syntax (Git Bash is recommended on Windows). After completing your first-time native configuration and database migration, you can launch the entire stack with a single PowerShell command.

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

## Docker Compose Deployment

If you want a zero-hassle evaluation or containerized deployment without installing Python, Node.js, PostgreSQL, or Redis locally, ensure **Docker Engine** and the **Docker Compose plugin** are installed, then run the following 3 steps from the repository root (first build requires internet access to pull base images and dependencies).

### Step 1: Create `docker/.env`
```bash
cp docker/.env.example docker/.env
```
Edit `docker/.env` and replace all placeholder secrets and administrator info:
- **`POSTGRES_PASSWORD` / `REDIS_PASSWORD`**: Use random **alphanumeric** characters so they work directly in container connection URLs without URL-encoding issues.
- **`JWT_SECRET`**: A random secret string of at least 32 characters.
- **`ADMIN_LOGIN_NAME` / `ADMIN_PASSWORD`**: Initial administrator login name and strong password (`>= 10` characters), plus real name, email, and phone number.
- **`HTTP_PORT`**: Host port exposed by Nginx (defaults to `8080`).
- **`ENVIRONMENT` / `COOKIE_SECURE`**: Keep `development` and `false` for local HTTP testing; set to `production` and `true` behind HTTPS in production.

> **Security Note**: `docker/.env` is ignored by `.gitignore`—keep it safe and never commit it to Git.

### Step 2: Build, Start & Initialize Admin
From the repository root:
```bash
docker compose --env-file docker/.env -f docker/compose.yaml up -d --build
docker compose --env-file docker/.env -f docker/compose.yaml exec api python -m app.cli init-admin
```

**Startup Sequence**: Compose starts `postgres` (18) and `redis` (8-alpine), waits for both healthchecks to pass, runs the one-off `migrate` container (`alembic upgrade head`), and then launches `api`, `worker`, and `web` (Nginx serving static assets and proxying `/api/` to `api:18000`). The `init-admin` command is idempotent and will not overwrite an existing admin password.

### Step 3: Access & Common Compose Commands
Open `http://localhost:8080` (or your configured `HTTP_PORT`) in your browser and sign in with your administrator credentials. Useful management commands:

```bash
# Check container status and stream logs
docker compose --env-file docker/.env -f docker/compose.yaml ps
docker compose --env-file docker/.env -f docker/compose.yaml logs -f

# Stop and remove containers (named data volumes remain intact)
docker compose --env-file docker/.env -f docker/compose.yaml down
```

### Container Persistence & Production Notes
- **Named Volumes**: PostgreSQL data, Redis persistence, uploaded question images (`/data/uploads`), and server log files (`/data/logs`) are stored in named volumes `postgres_data`, `redis_data`, and `app_data`.
- **Upgrades & Password Changes**: Always back up the database and uploaded assets per **[Operations & Recovery](operations.en.md)** before upgrading an existing deployment (`up -d --build` runs pending migrations automatically). Note that **changing `POSTGRES_PASSWORD` in `docker/.env` after `postgres_data` is first created does not automatically alter the existing PostgreSQL user's password**.
- **Production TLS Boundary**: `docker/compose.yaml` and `docker/nginx.conf` do not terminate TLS directly. In production, place an HTTPS reverse proxy (e.g., host Nginx, Caddy, or cloud load balancer) in front of the `web` service, set `ENVIRONMENT=production` and `COOKIE_SECURE=true`, and restrict direct external access to PostgreSQL and Redis.

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

## Stopping Services & Release Packaging

- **Graceful Shutdown Order**: Stop Vite, the API server, and the ARQ worker (`Ctrl + C`) first, then shut down your project-dedicated Redis and PostgreSQL instances while keeping their data directories intact.
- **Windows One-Command Release Packaging**: With Python 3.13, `uv`, and Node.js 24/npm installed, run from the repository root:
  ```powershell
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build-package.ps1
  ```
  The script syntax-checks backend Python code using locked dependencies, runs `npm ci` if `frontend/node_modules` is missing, builds the production frontend bundle, and packages a clean release archive at `.local/releases/online-exam-system-*.zip` (moving any previous `frontend/dist` to `.deletedfiles/`). If `node_modules` already exists, update dependencies manually whenever `package-lock.json` changes. The script exits non-zero on failure.
- **Deploying the Release Zip**: The zip contains `frontend/dist`, `backend/app`, `backend/migrations`, `alembic.ini`, `pyproject.toml`, `uv.lock`, `.python-version`, `backend/.env.example`, and `LICENSE`—it intentionally excludes `.env` secrets, databases, uploaded assets, logs, and Python runtimes. After extracting on a target server, configure `backend/.env`, sync dependencies, run migrations, start both API and worker, and serve `frontend/dist` behind Nginx (or similar) with SPA fallback to `index.html` and a same-origin `/api` proxy—never run `npm run dev` in production.
