# Documentation Hub

[中文](README.md) | **English**

Welcome to the official documentation hub for the **Online Exam System** ([GitHub Repository](https://github.com/NaSAeL-DWG/online_exam_system)).

To help you find what you need in seconds, all documentation is organized by **your role and task** into three clear sections with a quick reading roadmap.

---

## Quick Reading Roadmap (By Role)

- **New to the project and want to run it locally**
  1. Follow the **[Quick Start Guide (`quick-start.en.md`)](quick-start.en.md)** to configure your environment and start the backend API, ARQ worker, and frontend.
  2. Want a rich set of accounts and exams without manual clicking? Run **[Repeatable Demo Data (`demo.en.md`)](demo.en.md)** to populate teachers, students, and exams across 9 states in a few minutes.
  3. Open your browser and follow the **[Three-Role User Guide (`user-guide.en.md`)](user-guide.en.md)** to experience question authoring, timed attempts, grading, and result review.
- **Ready to read code, fix bugs, or build features**
  1. Spend 5 minutes reading the **[Domain Terminology Dictionary (`../CONTEXT.en.md`)](../CONTEXT.en.md)** to distinguish "Question, Paper, Exam Snapshot, Attempt, and Final Result".
  2. Read **[Architecture & Development Guide (`development.en.md`)](development.en.md)** and the subproject guides (**[Backend Guide (`../backend/README.en.md`)](../backend/README.en.md)** · **[Frontend Guide (`../frontend/README.en.md`)](../frontend/README.en.md)**).
  3. When modifying UI components or pages, follow the **[UI Design Specification (`ui-design.en.md`)](ui-design.en.md)** to maintain C3 visual and accessibility consistency.
  4. Verify your changes with the **[Testing & Verification Guide (`testing.en.md`)](testing.en.md)** using real PostgreSQL/Redis Pytest tests and Playwright browser E2E tests.
- **Responsible for deployment, backups, and troubleshooting**
  1. Check **[Operations & Recovery Guide (`operations.en.md`)](operations.en.md)** for startup/shutdown order, Alembic migrations/rollbacks, `pg_dump` backups, admin password resets, and pure-PostgreSQL worker recovery commands.
  2. Check **[System Logs & Security Audit (`logging.en.md`)](logging.en.md)** to filter runtime logs, enable 15-minute temporary DEBUG collection, and manage server log file rotation.

---

## 1. Getting Started & User Guides

For first-time evaluators, presenters, and daily users (students, teachers, and administrators).

| Document | Summary | Key Topics Covered |
| :--- | :--- | :--- |
| **[Quick Start Guide (`quick-start.en.md`)](quick-start.en.md)** | Run the project locally from scratch | Runtime versions, required `backend/.env` variables, 3-process startup order, Windows `start-local.ps1` one-command launcher |
| **[Three-Role User Guide (`user-guide.en.md`)](user-guide.en.md)** | Complete manual for Students, Teachers, and Admins | Student registration & timed attempt rules, multi-tab takeover, teacher question bank/paper/snapshot workflow, whole-attempt grading, publishing/withdrawing results, admin task reassignment |
| **[Repeatable Demo Data (`demo.en.md`)](demo.en.md)** | Populate realistic end-to-end sample data | Run `python -m app.demo` via public HTTP APIs to create 3 teachers, 6 students, 2 classes, and exams across 9 business states |
| **[Domain Terminology (`../CONTEXT.en.md`)](../CONTEXT.en.md)** | Shared ubiquitous language across the project | Clear definitions of 14 core terms: Question, Paper, Exam, Exam Snapshot, Exam Participant, Attempt, Grading Task, Attempt Score, Final Result, Void Attempt, etc. |

---

## 2. Architecture, UI Specs & Quality Verification

For engineers working on backend/frontend code, UI layouts, automated tests, and capacity benchmarking.

| Document | Summary | Key Topics Covered |
| :--- | :--- | :--- |
| **[Architecture & Development (`development.en.md`)](development.en.md)** | Layering rules and coding standards | Backend `router → service → crud` boundaries, single-transaction use cases, row-lock refresh, Cookie+CSRF auth, localized validation errors, 5-step development workflow |
| **[Backend Engineering Guide (`../backend/README.en.md`)](../backend/README.en.md)** | `backend/` modules and internals | 12 domain modules, atomic Refresh Token CAS rotation, async session cleanup compensation, ARQ grading & pure-PostgreSQL recovery |
| **[Frontend Engineering Guide (`../frontend/README.en.md`)](../frontend/README.en.md)** | `frontend/` architecture and state | `views` vs. `features` separation, Web Locks single-tab write lease, zero-cache race-safe result views, on-demand ECharts SVG |
| **[UI Design Specification (`ui-design.en.md`)](ui-design.en.md)** | C3 theme palette and visual hierarchy | 5-tier visual priority, 50-shade C3 HEX color tables, `#F6F7F9` light-gray canvas + `#FFFFFF` white panels + square sidebar rules, UI acceptance criteria |
| **[Testing & Verification (`testing.en.md`)](testing.en.md)** | How to run backend and browser E2E tests | TDD workflow, real PostgreSQL/Redis Pytest commands, Playwright E2E configuration, and logging acceptance commands |
| **[100-Student Concurrency Report (`performance.en.md`)](performance.en.md)** | Real load benchmark under 100 concurrent students | Zero-error results and reproduction commands across 3 rounds of 100 students (2,000 answers/round) covering steady-state, peak worker recovery, and timeout auto-submission |

> **Live OpenAPI Documentation**: Once the backend API is running, visit `http://127.0.0.1:18000/docs` (Swagger UI) or fetch `http://127.0.0.1:18000/openapi.json` to inspect exact endpoint paths, parameters, and response schemas.

---

## 3. Operations & Log Auditing

For administrators and operators managing database upgrades, backups, fault recovery, and log inspection.

| Document | Summary | Key Topics Covered |
| :--- | :--- | :--- |
| **[Operations & Recovery (`operations.en.md`)](operations.en.md)** | Upgrades, backups, and fault recovery handbook | Service startup/shutdown order, Alembic migration & rollback safety, `pg_dump` backup/restore, pure-PostgreSQL recovery when Redis is down, admin password reset, FAQ table |
| **[System Logs & Security Audit (`logging.en.md`)](logging.en.md)** | Admin log viewer and retention guide | Runtime logs vs. security audits, **cumulative log level filtering rules**, 15-minute temporary DEBUG toggle, online retention & file rotation limits, redaction boundaries |

---

> **Local Technical Archives (`tech-docs/`)**: Requirement interviews, early iteration plans, raw verification evidence, and historical UI prototype review logs are archived locally under `tech-docs/` (ignored by `.gitignore` and not required to run the project); `docs/` contains only the curated, production-ready documentation shipped with the repository.
