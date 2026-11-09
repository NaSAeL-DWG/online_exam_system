# Testing & Verification Guide

[中文](testing.md) | **English**

This project practices **Test-Driven Development (TDD)** and **real-environment verification**.

Our testing philosophy follows two core rules:
1. **Red → Green → Refactor**: Whenever adding or changing public behavior, write a failing test first, then implement the minimal code required to make it pass.
2. **Real Storage & Real Browser Boundaries**: Aside from a small number of pure mathematical unit tests (such as multiple-choice set scoring and `Decimal` rounding), **all core tests run against real PostgreSQL, real Redis, and real Chromium browsers**—never substituting SQLite in-memory databases for PostgreSQL row-level locks (`FOR UPDATE`), JSONB, unique constraints, and timezone behavior.

---

## 1. Backend Testing & Static Checks

### 1. Prepare Isolated Test PostgreSQL & Redis Instances
> **Warning: Automated tests run migrations, create accounts and exam records, and simulate Redis failures/cleanups. Never point test environment variables at your daily development or production database!**

Create a dedicated empty PostgreSQL test database (e.g., `exam_test`) and choose a dedicated Redis DB index (e.g., `15`). Save the credentials in a Git-ignored `.local/backend-test.env` file:

```bash
# .local/backend-test.env example
TEST_DATABASE_URL="postgresql+asyncpg://user:pass@127.0.0.1:55432/exam_test"
TEST_REDIS_URL="redis://:pass@127.0.0.1:16379/15"
```

### 2. Run Targeted Pytest Suites
Rather than running the entire test suite on every minor edit, **select the test files corresponding to the modules you changed**:

```bash
cd backend
uv sync --locked --python 3.13

# Load private test environment variables without printing secrets
set -a
source ../.local/backend-test.env
set +a

# Example: run results and analytics integration tests
uv run python -m pytest -q tests/test_results_api.py tests/test_analytics_api.py
```

**Test Categories:**
- Changes to **student attempts (`attempt`) or grading (`grading`)** should run the corresponding concurrency, permission, or standalone worker recovery tests.
- Most `test_*_api.py` suites exercise the in-process ASGI entrypoint against real PostgreSQL and Redis; tests with `recovery` in their name spawn independent API/worker subprocesses to verify crash and queue-outage recovery.

### 3. Static Linting & Migration Drift Checks
Before committing backend changes, run Ruff and Alembic checks:

```bash
uv run ruff check app tests
uv run alembic check
```

> **Note**: `alembic check` compares SQLModel metadata against the current database schema—ensure your target dev/test database has been upgraded to `head` (`uv run alembic upgrade head`) first. To test full migration round-trips (`upgrade → downgrade → upgrade`), always use a **freshly created, disposable empty database** as documented in **[Operations Guide: Database Upgrades & Rollbacks](operations.en.md#2-database-upgrades--rollbacks)**.

---

## 2. Frontend Build Checks & Playwright Browser E2E Tests

### 1. Start Target Services & Prepare Credentials
Playwright E2E tests run against a live test/dev API server, ARQ worker, PostgreSQL database, and Redis instance (creating uniquely prefixed accounts, papers, exams, and attempts via public APIs—**never run E2E tests against production**).

Configure your test administrator credentials in `.local/e2e.env`:

```bash
# .local/e2e.env example
E2E_ADMIN_LOGIN="admin"
E2E_ADMIN_PASSWORD="your-test-admin-password"
```

### 2. Run E2E Specs & Build Verification

```bash
cd frontend
npm ci
npx playwright install chromium

# Load E2E credentials
set -a
source ../.local/e2e.env
set +a

# Run the spec matching your change scope (results workspace shown as example)
npm run test:e2e -- tests/e2e/results-workspace.spec.ts

# Run TypeScript typecheck, production Vite bundle build, and Prettier check
npm run build
npm run format:check
```

**Playwright Execution Tips:**
- By default, Playwright accesses `http://127.0.0.1:5173` and starts or reuses Vite. Set `PLAYWRIGHT_EXTERNAL_SERVER=1` if you already started an external server, or override the URL with `PLAYWRIGHT_BASE_URL` (the target server must include the same-origin `/api` proxy).
- **What to Assert**: Browser tests assert user-observable behaviors—autosave and multi-tab takeover, unanswered-question confirmation on submit, result publication and immediate withdrawal hiding, role navigation guards, and network error recovery—rather than brittle assertions on internal component variables.
- **Desktop + 390px Visual Inspection**: For layout changes, verify both desktop (`1440px` / `1280px`) and mobile (`390px`) widths, asserting zero full-page horizontal overflow and visually inspecting captured screenshots.

---

## 3. Targeted Acceptance Commands (System Logging Example)

When modifying system logging, security auditing, or architectural boundaries, run:

```bash
# 1. Backend logging API & architecture contract tests (in backend/ with .local/backend-test.env loaded)
uv run python -m pytest -q tests/test_logging_api.py tests/test_architecture_contract_api.py

# 2. High-volume logging retention & file rotation acceptance suite
uv run python -m pytest -q tests/test_logging_acceptance_api.py

# 3. Frontend administrator log viewer E2E test (in frontend/ with .local/e2e.env loaded)
npm run test:e2e -- tests/e2e/system-logs.spec.ts
```

> **Environment Note for `test_logging_acceptance_api.py`**:
> This suite generates over 100,000 runtime log records to verify capacity pruning and spawns 4 concurrent processes writing ~74 MiB of logs to test `10 MiB × 5` file rotation. To simulate database write-permission failures without breaking business transactions, the test database user must have permission to create and drop temporary database roles (this is a requirement only for this isolated acceptance test, not for production application deployments).

---

## 4. Test Evidence & Artifact Hygiene

1. **Record Verifiable Evidence**: Document the exact commands run, environment versions, failure causes, post-fix results, and any unverified boundaries. Do not sum overlapping subset runs to inflate pass counts; 100-student load testing follows its own dedicated protocol in the **[100-Student Concurrency Report](performance.en.md)**.
2. **Keep Artifacts Out of Git**: HTML reports, screenshots, Playwright traces, and `.local/*.env` credential files must stay in `.local/` or Git-ignored tool output directories. Scrub any sensitive inputs from failure logs before sharing summaries.
