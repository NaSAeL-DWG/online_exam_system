# Operations & Fault Recovery Guide

[中文](operations.md) | **English**

This guide covers daily operations for the **Online Exam System**: **process topology and startup/shutdown order, safe database upgrades and rollbacks, backups and restores, pure-PostgreSQL recovery when Redis or the worker is down, and administrator password recovery**.

---

## 1. Process Topology & Startup/Shutdown Order

All authoritative business facts are persisted in **PostgreSQL**, while **Redis** stores authentication sessions and the ARQ background task queue. The application runs as three separate processes: **FastAPI Backend API**, **ARQ Background Worker**, and **Frontend**.

### Fault-Tolerance Principles
- **Worker Outages or Queue Delivery Failures Never Lose Saved Answers**: Student answers are saved directly in PostgreSQL. When the worker restarts—or when you run manual recovery commands—it scans pending database records to complete timeout submissions, objective grading, and manual task assignment.
- **Fail-Closed Authentication on Redis Outages**: If the Redis session store becomes unavailable, the API safely rejects protected requests (`503 AUTH_SERVICE_UNAVAILABLE`) rather than degrading into unauthenticated access.

### Standard Startup & Shutdown Order
- **Startup Order**: `PostgreSQL & Redis` → `Alembic Database Migration` → `Backend API & ARQ Worker` → `Frontend`
- **Shutdown Order**: `Stop incoming traffic & Frontend` → `Gracefully stop API & Worker (Ctrl+C or process manager)` → `Shut down project-dedicated Redis & PostgreSQL`
- **Configuration Consistency**: The API and worker must share the exact same `DATABASE_URL`, `ARQ_REDIS_URL` (defaults to `REDIS_URL`), and `ARQ_QUEUE_NAME`.
- **Health Check Scope**: `/api/health` returning `ok` only indicates the API process is alive. Confirm full readiness by testing login, business reads, and worker logs.

---

## 2. Database Upgrades & Rollbacks

Alembic migrations currently span `0001` through `0018` (check `alembic heads` for the latest revision).
> Specifically: `0016` adds runtime logs and global log settings, `0017` adds stable read sequence numbers for committed audits, and `0018` adds a partial index for pending audits to avoid full-history scans.

### 1. Common Migration Commands
Run inside `backend/` using the active environment's `DATABASE_URL`:

```bash
uv run alembic current       # Show current database revision
uv run alembic heads         # Show latest target revision in codebase
uv run alembic history       # Show full migration history
uv run alembic upgrade head  # Upgrade database to latest revision
uv run alembic check         # Verify ORM models match database schema
```

### 2. Four-Step Production Upgrade Checklist
Before upgrading a database containing live data:
1. Record the current Git commit SHA and `alembic current` revision.
2. Stop incoming writes and stop the background ARQ worker.
3. **Back up the PostgreSQL database and the `ASSET_STORAGE_DIR` image directory**.
4. Test `alembic upgrade head` on a restored copy of the backup first, then upgrade the live database. (The app never auto-creates or wipes tables on startup, and you must **never** use `alembic stamp` to fake a migration.)

### 3. Rollback (`downgrade`) Warnings
**Downgrading a database schema is NOT a lossless undo!** A `downgrade` migration may drop tables, columns, indexes, and the data stored inside them (for example, downgrading below `0016` drops runtime logs while preserving business audit records).

- **Never run `downgrade base` on a database containing data you need to keep**.
- If an upgrade causes issues in production, **prefer restoring your pre-upgrade backup into a new database and switching back to the matching code commit**; only run `downgrade` in place after reading the exact `downgrade()` function and confirming no required data will be lost.
- To verify migration round-trips (`upgrade → downgrade → upgrade`) during testing, **always point `DATABASE_URL` at a freshly created, disposable empty database**:
  ```bash
  uv run alembic upgrade head
  uv run alembic downgrade 0014
  uv run alembic upgrade head
  uv run alembic check
  ```

---

## 3. Backups & Restoration

### 1. What Must Be Backed Up Together?
A complete backup must include:
1. **Full PostgreSQL database dump**.
2. **Complete `ASSET_STORAGE_DIR` image directory** (historical exam snapshots may reference older uploaded images—never delete image files merely because active question bank items no longer reference them).
3. **A secure copy of `.env` configuration**, plus the corresponding **Git commit SHA and Alembic revision**.
> Backups contain personal profiles, student answers, and credentials—restrict file permissions and never commit backups to Git.

### 2. Recommended `pg_dump` / `pg_restore` Workflow
Use native PostgreSQL tools to create `custom`-format dumps. Supply credentials via `PGSERVICE` or `.pgpass` rather than embedding passwords in command-line arguments (note that `postgresql+asyncpg://` in `backend/.env` is an SQLAlchemy async driver URL, not a libpq URL for `pg_dump`):

```bash
# 1. Create compressed custom dump (assuming PGSERVICE is configured for source DB)
pg_dump --format=custom --file=exam-backup.dump

# 2. Restore into a newly created empty database (service=exam_restore avoids overwriting source DB)
pg_restore --dbname='service=exam_restore' --no-owner --no-privileges exam-backup.dump
```

After restoring the database, restore the `ASSET_STORAGE_DIR` directory, verify code and migration versions, and test actual application logins and exam reads—do not merely check that the `.dump` file exists.

- **About Redis Persistence**: Redis persistence is optional because PostgreSQL holds all durable business state—if the queue is lost, the worker recovers from PostgreSQL; if sessions are lost, users simply sign in again. When restoring a production backup for a rehearsal drill, always use an isolated Redis instance, port, and asset directory copy.

---

## 4. Resident Worker & Manual Queue Recovery

### 1. Running the Resident Worker
```bash
cd backend
uv run arq app.workers.attempts.WorkerSettings
```
On startup, the worker immediately recovers pending database items and scans every 30 seconds thereafter (default batch size `100`, configurable via `ATTEMPT_SCAN_BATCH_SIZE` between `1` and `1000`). Submission, grading, and task assignment verify live status, eligibility, and revision numbers idempotently—retries never revive voided attempts or overwrite newer grading rubrics.

### 2. Pure-PostgreSQL Emergency Recovery (When Redis Queue Is Down)
If Redis is temporarily unavailable at the end of an exam, you can bypass Redis and run **pure-PostgreSQL recovery commands** directly inside `backend/`:

```bash
# Step 1: Auto-submit expired attempts in batches
uv run python -m app.workers recover-attempts --limit 100

# Step 2: Grade submitted objective questions and assign manual grading tasks
uv run python -m app.workers recover-grading --limit 100
```

- Inspect the `failed` count in the JSON output; if non-zero, troubleshoot and retry. Repeat until all pending batches are processed.
- **Boundary Notes**: Recovery auto-submission uses only answers saved to the server before the deadline. If an exam has no active designated grading teachers available, re-running the worker cannot assign tasks—an administrator must reassign the tasks in the web UI.

---

## 5. Administrator & Session Recovery

### 1. Resetting a Forgotten Administrator Password
Teachers and students have their passwords reset to temporary passwords by an administrator in the web UI after manual identity verification.

If **the system administrator forgets their own password**:
1. Update `ADMIN_PASSWORD` to a new strong password in your protected `backend/.env` file and verify `ADMIN_LOGIN_NAME` (never pass passwords as CLI arguments).
2. Run from `backend/`:
   ```bash
   cd backend
   uv run python -m app.cli reset-admin
   ```
3. This updates the password hash, increments `auth_version`, and revokes all existing admin sessions. Restart any processes that read `.env` if other settings changed.

### 2. Retrying Pending Session Cleanups (`X-Session-Cleanup: pending`)
If a password change or account deactivation commits in PostgreSQL while Redis is momentarily unreachable, the HTTP response may include `X-Session-Cleanup: pending`. The business change is already active (and `auth_version` blocks old tokens), so do not repeat the request. Once Redis is back online, flush pending session cleanups with:

```bash
cd backend
uv run python -m app.cli retry-session-cleanups --limit 100
```
Check `attempted`, `completed`, `pending`, and `failed` in the output, and re-run if `pending > 0`.

---

## 6. Troubleshooting FAQ

Administrators can inspect runtime diagnostics and security audits on the **[System Logs](logging.en.md)** page. If the application fails to start before the log page is reachable, run the API or worker in the foreground to read console errors.

| Symptom | What to Check & How to Fix |
| :--- | :--- |
| **Stuck on login page / API unreachable** | 1. Verify API, Vite proxy, and Redis are running;<br>2. **Confirm you are not mixing `localhost` and `127.0.0.1`** in the browser URL;<br>3. In production, verify HTTPS matches `COOKIE_SECURE=true`. |
| **Student can log in but cannot open workspace** | Check whether the student is still **Pending Review**, deactivated, or required to **change a temporary password** on first login. |
| **Expired attempt stays "In Progress / Pending"** | Confirm the ARQ worker is running and shares the same `REDIS_URL` / `ARQ_QUEUE_NAME` as the API; or run `recover-attempts` and `recover-grading` manually. |
| **Grading task stuck in "Unassigned"** | The designated grading teacher may be deactivated or unavailable. Have an administrator open Exam Details → "Grading Progress & Results" and click **"Reassign Task"**. |
| **Student submitted but sees no score** | Check: 1. Has the exam window ended? 2. Are all historical valid attempts fully graded? 3. Has the teacher clicked **"Publish Results"** (or are results currently withdrawn for correction)? |
| **Student sees total score but cannot review questions** | Check the exam's **Allow Review** setting; when disabled, only the published total score is shown. |
| **Page reports a "Version Conflict"** | Another user modified the same record while you were editing. Reload the current record, compare changes, and submit again—do not blindly replay stale requests. |

---

## 7. Production Deployment Boundaries

1. **Transport & Auth Security**: Enforce **HTTPS**, set `ENVIRONMENT=production` and `COOKIE_SECURE=true`, use a unique random `JWT_SECRET` (`>= 32` characters), and restrict `CORS_ORIGINS` to your real frontend origin. Never bypass CSRF checks on login or mutating endpoints.
2. **Storage & Asset Isolation**: Never expose PostgreSQL, Redis, or `ASSET_STORAGE_DIR` directly to the public internet; question images must be served through authenticated API endpoints. Configure your static web server (e.g., Nginx) with SPA fallback to `index.html` and proxy `/api` to the backend.
3. **Capacity Verification**: Benchmark figures in the **[100-Student Concurrency Report](performance.en.md)** apply only to the documented local hardware and workload. Always re-run load verification on your target production environment before major exams.
