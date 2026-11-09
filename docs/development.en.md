# Architecture & Development Guide

[中文](development.md) | **English**

This guide explains the engineering rules of the **Online Exam System** in plain language: **how the repository is structured, how the backend three-tier architecture works, how auth and sensitive data are protected, how the frontend is organized, and the standard workflow for making changes**.

Before writing code, read the **[Domain Terminology Dictionary (`../CONTEXT.en.md`)](../CONTEXT.en.md)** and **[Three-Role User Guide (`user-guide.en.md`)](user-guide.en.md)**, and keep three core domain invariants in mind:
1. **Papers are reusable templates, while Exams deep-copy an isolated "Exam Snapshot" upon creation**—edits never cross-contaminate.
2. **Attempts are saved independently, and a student's Final Result is strictly their "last valid submission"** (if the latest submission is still being graded, the final result is "Pending Grading"—never fall back to an older score).
3. **"Releasing an Exam" (letting students take it) and "Publishing Results" (letting students view scores) are two separate operations**.

---

## 1. Repository Layout Overview

The system combines a **domain-modular three-tier FastAPI monolith** with a **separated Vue 3 frontend**:

```text
backend/app/
  core/                    Configuration, DB connection lifecycle, unified error codes & localized validation errors
  modules/<domain>/        Domain modules, each containing router / service / crud / models / schemas
  cli.py                   Operations CLI entrypoint (admin init/reset, session cleanup retry, log self-check)
  workers/                 ARQ async worker entrypoint (timeout submission, objective grading, task assignment & recovery)
backend/migrations/        Alembic schema migrations (0001 ~ 0018)
backend/tests/             Real PostgreSQL / Redis HTTP integration tests & pure scoring unit tests

frontend/src/
  api/                     Typed HTTP clients, automatic CSRF injection, cross-tab token refresh, field error mapping
  features/                Domain-scoped state, complex sub-views & composables (attempt lease, grading workspace, charts)
  views/                   Route-level page views & task orchestration
  components/              Shared stateless UI primitives (PageHeader, SurfacePanel, AppSelect, LoadingSkeleton, etc.)
  styles/ & design/        C3 design tokens (tokens.css), Naive UI theme config (theme.ts), and global layout CSS
  router.ts & navigation/  Route definitions, role guards, and sidebar navigation groups
```

---

## 2. Backend Architecture Rules

### 1. Strict Three-Tier Boundaries (`router → service → crud`)

Every backend domain module enforces a strict separation of responsibilities:

| Layer | Responsibilities | Strictly Forbidden |
| :--- | :--- | :--- |
| **Router (`router`)** | Parse HTTP parameters, attach auth/role dependencies, verify CSRF, return response schemas, set/clear cookies | **Never** query ORM models directly; **never** `commit` transactions |
| **Service (`service`)** | Validate resource permissions, control state transitions, record security audits, orchestrate cross-module calls, **own top-level database transactions** | **Never** depend on FastAPI `Request`/`Response`; **never** build raw ORM queries directly |
| **CRUD (`crud`)** | Build SQLAlchemy/SQLModel queries, pagination, aggregations, row locks (`with_for_update`), and `flush` | **Never** make authorization decisions; **never** call `commit` inside CRUD |

- **Shared Public Use Cases**: HTTP routers, CLI commands, and ARQ workers all invoke the same public `service` functions rather than duplicating business logic.
- **Cross-Module Collaboration via Public Interfaces**: Modules interact only through public `service` or read-query functions—**never import another module's internal tables or CRUD functions directly**.
- **No Boilerplate Abstraction**: Keep code direct and readable—do not create empty interface classes for every function or a generic `BaseService`.

### 2. Transaction & Row-Locking Discipline

- **One Write Use Case = One Top-Level Transaction**: Only the outermost `service` use case commits the transaction (`commit`). Composable helper functions may call `flush`, but **must never commit early**, ensuring business state mutations and audit logs succeed or roll back atomically.
- **Refresh Entities After Row Locking**: Acquiring a row lock with `with_for_update` does not automatically refresh an ORM instance that was already loaded into the current session. Always use `populate_existing` or explicitly refresh the locked entity before checking its live status and version number.
- **Scoped Loading (No N+1 or Over-Fetching)**: List endpoints load only summary columns and counts, while detail endpoints load full children (for example, exam lists must never eager-load all historical attempts and answers). Prefer SQLAlchemy expressions and ORM; raw SQL is restricted to Alembic migrations or justified PostgreSQL-specific features.

### 3. Error Handling & Async Fault Compensation

- **Stable Business Error Codes**: Domain errors raise custom exceptions with stable machine-readable `code` strings, which the HTTP layer maps to HTTP status codes.
- **Never Masquerade Post-Commit Queue Hiccups as Write Failures**:
  - Once a database transaction commits (e.g., a student submits an attempt), a transient failure enqueuing the ARQ job must **not** return a 500 error that tricks the user into re-submitting. Persistent database markers and periodic worker scans automatically compensate.
  - Likewise, if Redis session deletion fails after a password change or account deactivation commits, the API returns success with `X-Session-Cleanup: pending` while the incremented `auth_version` in PostgreSQL immediately blocks old sessions.

### 4. Dual-Track Runtime Logs & Security Audits

- **Runtime Logs**: Collected via standard Python `logging` into a bounded in-memory queue (up to 5,000 entries per process) and persisted asynchronously in **independent database transactions**. Logging failures never roll back business transactions.
- **Security Audit Logs**: Account changes, exam releases, score adjustments, and result publications commit **atomically within the business transaction** and are exposed to administrators via redacted read interfaces.
- **Cumulative Log Level Filtering**: The log viewer uses a project-specific cumulative level filter (see **[System Logs Guide](logging.en.md)**) rather than standard minimum-severity filtering.

---

## 3. API Contracts, Auth Security & Sensitive Data Boundaries

1. **API Conventions & Decimal Precision**
   - Inspect live contracts at `/docs` or `/openapi.json` when the backend is running.
   - Paginated lists accept `page` (default 1), `page_size` (default 20, max 100), and optional `q`, returning `{ items, total, page, page_size }`.
   - **All point values, scores, and ratios are serialized as decimal strings in JSON and calculated with `Decimal`**, eliminating floating-point rounding bugs.
2. **HttpOnly Cookie + CSRF + Single-Use Refresh Tokens**
   - Session tokens live in `HttpOnly` cookies; frontend JavaScript never reads tokens or stores credentials in `localStorage`.
   - Clients fetch `/api/auth/csrf` on startup and send `X-CSRF-Token` on all mutating requests (`POST`/`PUT`/`PATCH`/`DELETE`), which the server matches against the CSRF cookie.
   - Refresh Tokens rotate atomically on every use (CAS); the frontend coordinates concurrent tabs via Web Locks.
3. **Zero Sensitive Data Leaks**
   - **Never log plaintext passwords, tokens, cookies, student answers, or unpublished answer keys**.
   - Every student result, review, mistake, or analytics read verifies identity, eligibility, publication state, and review permissions on the backend—**hiding a frontend button is never a substitute for backend authorization**.
   - Result responses and protected question images set `Cache-Control: private, no-store`. If results are withdrawn, late-arriving responses from older requests are discarded so withdrawn scores never reappear on screen.
   - Question images must be served through authenticated API endpoints—never expose the upload directory as public static files.

---

## 4. Frontend Responsibilities, Visual Standards & Form UX

### 1. Architecture & C3 Visual Reuse
- **`views/` Orchestrate Tasks, `features/` Own Domain State, `api/` Owns Types**: Keep complex attempt leases, grading workflows, and chart loaders inside `src/features/` rather than bloating page views.
- **Reuse C3 Design Tokens**: Colors and radii live in `src/styles/tokens.css` and `src/design/theme.ts` (`#F6F7F9` light-gray canvas, `#FFFFFF` white panels, `#2164CE` primary blue, `0 px` square sidebar items). Reuse `PageHeader`, `SurfacePanel`, `AppSelect`, and `LoadingSkeleton` across pages.

### 2. Visual Hierarchy & Responsiveness
- **Task-First Hierarchy**: Each page has one clear `h1` title and one primary action per task area.
- **Distinct States**: Clearly distinguish loading, empty, error, and permission-disabled states. If a write succeeds but the subsequent list refresh fails, inform the user accurately so they do not double-submit. Destructive actions must state the target object, consequences, and whether the action is reversible.
- **Desktop-First + 390px Mobile Support**: Check all layouts, modals, and action bars at both desktop (`1440px`/`1280px`) and mobile (`390px`) widths. Wide tables scroll horizontally inside their container without causing full-page horizontal overflow. All inputs and buttons require accessible labels and visible keyboard focus. Load ECharts modules on demand and provide expandable data tables with explicit statistical definitions.

### 3. Localized Inline Validation & Unsaved Changes Protection
- **End-to-End Localized Field Errors**: The frontend validates known constraints inline, binds `aria-invalid` / `aria-describedby`, and focuses the first invalid field. Backend 422 errors are translated by `core/validation_errors.py` into clear Chinese reasons (preserving dot-separated `fields` paths) and mapped by `api/fieldProblems.ts`—never exposing raw Pydantic English diagnostics to end users.
- **Unsaved Edit Guard**: Question, paper, exam, grading, and mistake note editors warn before route navigation, modal closing, or browser reload when unsaved edits exist—**except when a session expires or result permissions are revoked, where immediate logout or state clearing takes priority**.

---

## 5. Standard Development & Commit Workflow

Follow this 5-step loop for every feature or bugfix:

1. **Write a Failing Test First (TDD)**: Add a failing test at the public HTTP API or real-browser E2E boundary that reproduces the bug or specifies the new behavior.
2. **Implement Minimal Complete Behavior**: Write clean, well-commented code (Chinese docstrings on backend endpoint functions and explanatory comments on concurrency locks, transactions, and visibility rules) to make the test pass.
3. **Self-Review & Targeted Regression**: Check layering boundaries, authorization, and desktop/390px responsiveness; run the relevant test files and build checks (see **[Testing & Verification Guide](testing.en.md)**).
4. **Update Documentation**: Sync any affected user, operations, or architecture docs in `docs/` (both Chinese and English versions).
5. **Commit & Push Cleanly**: Use Conventional Commits (`feat(exam): ...`, `fix(ui): ...`, `docs: ...`). Inspect `git status` and `git diff` before committing to ensure **no `.env` secrets, `.local/` artifacts, databases, or temporary screenshots are committed**.
