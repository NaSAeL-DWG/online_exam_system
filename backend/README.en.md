# Backend Engineering & Maintenance Guide (`backend/`)

[中文](README.md) | **English**

This directory contains the FastAPI backend service, ARQ async worker, CLI maintenance tools, Alembic database migrations, and real-storage HTTP integration tests for the **Online Exam System**.

> **Global Documentation**: For initial environment setup and startup order, see the **[Quick Start Guide (`../docs/quick-start.en.md`)](../docs/quick-start.en.md)**; for cross-stack engineering rules, see **[Architecture & Development Guide (`../docs/development.en.md`)](../docs/development.en.md)**.

---

## 1. Directory Layout & Domain Modules

The backend is structured as a **domain-modular three-tier monolith** under `app/modules/`:

```text
backend/
├── app/
│   ├── core/                 # Shared infrastructure (config, DB lifecycle, clock, error codes, localized validation, runtime log buffer)
│   ├── modules/              # 12 domain modules (each containing router / service / crud / models / schemas)
│   │   ├── auth/             # Login, HttpOnly cookies, single-use Refresh Token CAS rotation, CSRF, session cleanup compensation
│   │   ├── identity/         # Admin/Teacher/Student accounts, registration review, password reset, security audit records
│   │   ├── teaching_class/   # Teaching class management, multi-teacher assignment, student membership
│   │   ├── asset/            # Question image upload, persistent storage, authenticated asset streaming
│   │   ├── question/         # Shared question bank (4 types), multi-criteria filtering, archiving/closing
│   │   ├── paper/            # Shared paper assembly, question ordering, decimal point aggregation
│   │   ├── exam/             # Exam creation, deep-copied Exam Snapshots, participant eligibility, release/cancel, result publication
│   │   ├── attempt/          # Timed student attempts, fixed deadlines, single-tab Page Lease, per-question autosave, submission
│   │   ├── grading/          # Automated objective grading, balanced whole-attempt task assignment, audited re-scoring, rubric correction
│   │   ├── results/          # Student result history, Final Result calculation (last valid submission), protected snapshot review
│   │   ├── mistake/          # Automated mistake collection, filtering, personal notes, and mastery status
│   │   ├── analytics/        # Teacher exam statistics and student score-rate trends & knowledge breakdowns
│   │   └── logging/          # Admin runtime log query, cumulative level filtering, 15-min temporary DEBUG, file rotation & export
│   ├── workers/              # ARQ async worker & pure-PostgreSQL recovery commands (attempts / grading / recovery)
│   ├── demo/                 # Repeatable demo dataset generator via public HTTP APIs (python -m app.demo)
│   ├── cli.py                # Operations CLI (init-admin / reset-admin / retry-session-cleanups / logging-check)
│   └── main.py               # FastAPI application entrypoint and middleware registration
├── migrations/               # Alembic database migrations (0001 ~ 0018)
├── scripts/                  # 100-student concurrency benchmark (verify_concurrency.py) & startup script tests
└── tests/                    # Real PostgreSQL / Redis HTTP integration test suite
```

### Three-Tier Layering Rules
1. **Strict `router → service → crud` Boundaries**:
   - `router` handles HTTP parameters, auth dependencies, CSRF, and cookies—never direct ORM queries or transaction commits.
   - `service` enforces resource permissions, state transitions, audit logging, and **top-level database transactions (one write use case = one `commit`)**. Lower-level composable helpers must never commit behind the caller's back.
   - `crud` encapsulates SQLAlchemy/SQLModel queries, row locks (`with_for_update`), pagination, and `flush`—never business authorization.
2. **Read/Write Sessions & Row-Lock Refresh**:
   - Auth dependencies use a separate read-only session to return an immutable snapshot of user profile and `auth_version`.
   - Write use cases open a fresh transaction session, lock target rows with `populate_existing`, and verify live status and version before mutating state.
3. **Pagination & Decimal Precision**:
   - List endpoints accept `page` (default 1), `page_size` (default 20, max 100), and optional `q`, returning `{ items, total, page, page_size }`.
   - Avoid N+1 queries: teaching class lists aggregate student counts and batch-load teachers; full student lists are loaded only on class detail views.
   - All scores and ratios are transmitted as decimal strings in JSON and computed using `Decimal`.

---

## 2. Core Technical Mechanisms

### 1. Auth Security, Single-Use Refresh Tokens & Session Cleanup Compensation
- **Atomic Refresh Token Rotation (CAS)**: Refreshing a session reads Redis state, locks the user row in PostgreSQL to verify active status and `auth_version`, and executes an atomic Redis Lua CAS script. Replaying a consumed Refresh Token immediately revokes the entire session. Database outages during refresh return `503 DATABASE_UNAVAILABLE` (allowing retry with the existing token), while Redis outages return `503 AUTH_SERVICE_UNAVAILABLE` (fail-closed).
- **Async Session Cleanup Compensation (`0002_session_cleanup`)**: When a password change, reset, or account deactivation commits in PostgreSQL (`auth_version` increments immediately to block old tokens), a transient Redis failure during session deletion still returns HTTP `200`/`204` with header `X-Session-Cleanup: pending` so clients do not replay the write. Once Redis recovers, run:
  ```bash
  uv run python -m app.cli retry-session-cleanups --limit 100
  ```
  *(Note: The Lua script only deletes sessions below the recorded revocation version upper bound, preserving any new session created after a password reset.)*

### 2. Timed Attempts, Grading & Queue Failure Recovery
- **Attempts & Page Lease (`attempt`)**: The server computes a fixed `deadline_at` (`min(personal_duration, exam_end_time)`). `page_token` and `active_token_generation` ensure only one browser tab holds write permission for an attempt at a time.
- **Grading & Task Assignment (`grading`)**: Submitting an attempt enqueues a revision-tagged ARQ job. Once the exam ends and all valid attempts have finished submission and objective grading, non-empty short-answer attempts are evenly distributed as whole-attempt tasks to designated active teachers. Correcting a single question's rubric only re-grades that question while preserving other scores and initial grading completion records.
- **Pure-PostgreSQL Fallback Recovery**: If Redis is unavailable, saved answers in PostgreSQL are never lost. The resident worker scans pending database records every 30 seconds, or operators can run pure-PostgreSQL recovery commands directly:
  ```bash
  # Start resident ARQ worker
  uv run arq app.workers.attempts.WorkerSettings

  # Manual recovery when Redis queue is down (requires PostgreSQL only)
  uv run python -m app.workers recover-attempts --limit 100
  uv run python -m app.workers recover-grading --limit 100
  ```

### 3. Result Publication, Mistakes & Learning Analytics
- **Result Publication & Withdrawal (`exam/publication.py` & `results`)**: Results can be published under an exam row lock only after all valid attempts and manual grading tasks are complete. Each student's **Final Result** strictly uses their **last valid submission** (remaining empty/pending if that attempt is still being graded). Withdrawing results, revoking eligibility, cancelling an exam, or disabling review immediately blocks access to attempt reviews, protected images, and analytics.
- **Mistakes & Analytics (`mistake` & `analytics`)**: Questions without full marks in published, review-enabled valid attempts automatically populate the mistake notebook (personal notes and mastery flags are stored in `0015_mistake_annotations`). Analytics query live database state without fabricating denominators for public exams.

---

## 3. Common Development, Migration & Testing Commands

Run all commands inside `backend/` (Python 3.13 dependencies locked via `uv.lock`):

```bash
# 1. Sync locked dependencies
uv sync --locked --python 3.13

# 2. Upgrade database schema & check model drift
uv run alembic upgrade head
uv run alembic check

# 3. Initialize or reset system administrator (reads ADMIN_* from backend/.env)
uv run python -m app.cli init-admin
uv run python -m app.cli reset-admin

# 4. Start local development API server
uv run uvicorn app.main:app --host 127.0.0.1 --port 18000

# 5. Run static lint & formatting checks
uv run ruff check app tests migrations
uv run ruff format --check app tests migrations

# 6. Run real PostgreSQL / Redis integration tests (configure ../.local/backend-test.env first)
set -a
source ../.local/backend-test.env
set +a
uv run python -m pytest -q --tb=short
```

> **Tip**: Run targeted `tests/test_*_api.py` files matching your changes rather than the entire suite on every edit. `--tb=short` prevents pytest tracebacks from printing local fixture connection strings. See the **[Testing & Verification Guide (`../docs/testing.en.md`)](../docs/testing.en.md)** for details.
