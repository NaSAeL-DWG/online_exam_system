<div align="center">

# Online Exam System · 在线限时考试系统

[中文](README.md) | **English**

**A lightweight, rigorous, full-lifecycle online timed exam platform for educational institutions**

[![GitHub Repo](https://img.shields.io/badge/GitHub-NaSAeL--DWG%2Fonline__exam__system-181717?logo=github)](https://github.com/NaSAeL-DWG/online_exam_system)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://github.com/NaSAeL-DWG/online_exam_system/blob/main/LICENSE)
[![Python 3.13](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.117-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue 3.5](https://img.shields.io/badge/Vue-3.5-4FC08D?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![TypeScript 5.9](https://img.shields.io/badge/TypeScript-5.9-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![PostgreSQL 18](https://img.shields.io/badge/PostgreSQL-18-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis 8](https://img.shields.io/badge/Redis-8-DC382D?logo=redis&logoColor=white)](https://redis.io/)

[Quick Start](docs/quick-start.en.md) · [User Guide](docs/user-guide.en.md) · [Documentation Hub](docs/README.en.md) · [Architecture & Dev](docs/development.en.md) · [Report Issues](https://github.com/NaSAeL-DWG/online_exam_system/issues)

</div>

---

## Overview

**Online Exam System** ([NaSAeL-DWG/online_exam_system](https://github.com/NaSAeL-DWG/online_exam_system)) is a web-based online examination platform built for a single educational institution. Designed around three core roles—**Students, Teachers, and Administrators**—it covers the complete teaching and assessment lifecycle: shared question banks, paper assembly, exam publishing, timed attempts, automated objective grading, manual subjective grading, result publication, mistake review, and learning analytics.

The project follows three core engineering principles: **rigorous data integrity, clear exam boundaries, and lightweight native execution without Docker**. Creating an exam immediately deep-copies a standalone snapshot, countdown timers are anchored to the server's authoritative clock, and background auto-submission and grading are backed by PostgreSQL persistence—ensuring every exam is fair, reliable, and auditable.

---

## Key Features

- **Three-Role Collaboration with Clear Boundaries**
  - **Student Workspace**: Self-service registration, upcoming & active exam overview, distraction-free timed exam workspace, attempt history, question-by-question answer review, mistake notebook with mastery tracking, and personal learning analytics.
  - **Teacher Workspace**: Review student registrations, manage assigned teaching classes, collaborate on shared question banks and papers, publish public or restricted exams, grade assigned short-answer papers, correct answer keys with automatic re-grading, and publish or withdraw final results.
  - **Administrator Workspace**: Provision and manage teacher accounts, create teaching classes and assign teachers, manage student eligibility and password resets, monitor global grading progress, reassign stalled grading tasks, and inspect real-time runtime logs and security audits.
- **Standalone Exam Snapshots Isolated from Question Bank Edits**
  - Supports four question types: Single Choice, Multiple Choice, True/False, and Short Answer. Stems and explanations support Markdown, LaTeX math formulas (KaTeX), and authenticated image assets.
  - Creating an exam from a paper immediately deep-copies an isolated **Exam Snapshot**. Subsequent edits to the source question bank or paper never affect existing or ongoing exams.
- **Reliable Timed Attempts & Single-Tab Write Lease**
  - **Authoritative Server Countdown**: Deadlines take the earlier of the student's personal duration or the exam's closing time. Disconnecting, closing the browser, or changing the local system clock never pauses or extends the timer.
  - **Single-Tab Write Protection (Page Lease)**: Only one active browser tab can save answers for an attempt at a time. Switching devices or opening a new tab prompts an explicit one-click takeover while turning the old tab read-only.
  - **Async Auto-Submission & Database Fallback**: An ARQ worker handles timeout auto-submission, instant objective grading, and balanced manual grading assignment. Even if Redis experiences transient hiccups, periodic PostgreSQL scans automatically recover pending tasks.
- **Strict Grading & Final Score Rules**
  - **Whole-Paper First Grading + Audited Score Adjustments**: Short-answer questions are distributed by whole attempt to designated teachers. After initial grading is completed, other active teachers can adjust scores with a mandatory reason, preserving an immutable grading history.
  - **"Last Valid Submission" Rule**: When multiple attempts are allowed, a student's **Final Result** strictly equals their last valid submission (never the highest historical score). If the latest attempt is still awaiting manual grading, the final result remains "Pending Grading" rather than falling back to an older score.
  - **Releasing an Exam ≠ Publishing Results**: Students can only view scores after all valid attempts are graded and a teacher explicitly clicks **Publish Results**. If an answer key needs correction afterwards, teachers can withdraw results, update the rubric to trigger re-grading, and republish.

---

## Tech Stack

| Layer | Technologies | Highlights |
| :--- | :--- | :--- |
| **Frontend** | Vue 3.5 + TypeScript 5.9 + Vite 8 | Composition API, strictly typed API contracts |
| **UI & Visualization** | Naive UI + ECharts 6 + KaTeX + Markdown-it | Custom C3 design system (`#F6F7F9` light-gray canvas + `#FFFFFF` white panels), on-demand SVG charts, math rendering |
| **State & Routing** | Pinia 4 + Vue Router 5 | Role-based route guards, cross-tab token refresh coordination via Web Locks |
| **Backend Framework** | Python 3.13 + FastAPI + Uvicorn | Async HTTP API, OpenAPI schema generation, localized validation diagnostics |
| **Database & ORM** | PostgreSQL 18 + SQLModel + Alembic | Strict transaction boundaries, row-level locking (`FOR UPDATE`), 18 versioned migrations |
| **Session & Queue** | Redis 8 + ARQ + Argon2 + PyJWT | HttpOnly Cookie + double-submit CSRF, single-use Refresh Token CAS rotation, async grading worker |
| **Testing & Quality** | Pytest + Playwright + Ruff + Prettier | Real PostgreSQL/Redis HTTP integration tests, Chromium E2E suite, 100-student concurrency benchmark |

---

## Repository Structure

```text
online_exam_system/
├── backend/                  # FastAPI backend service (see backend/README.en.md)
│   ├── app/
│   │   ├── core/             # Config, database lifecycle, security, unified validation error mapping
│   │   ├── modules/          # 12 domain modules (auth/identity/teaching_class/question/paper/exam/attempt/grading/results/mistake/analytics/logging)
│   │   ├── workers/          # ARQ async worker (timeout submission, objective grading, task assignment, recovery CLI)
│   │   └── cli.py            # Operations CLI (init-admin, reset-admin, retry-session-cleanups, logging-check)
│   ├── migrations/           # Alembic database migrations (0001 ~ 0018)
│   ├── scripts/              # 100-student concurrency benchmark & startup verification scripts
│   └── tests/                # Real PostgreSQL/Redis HTTP integration test suite
├── frontend/                 # Vue 3 frontend application (see frontend/README.en.md)
│   ├── src/
│   │   ├── api/              # Typed HTTP client, CSRF injection, cross-tab refresh coordination
│   │   ├── components/       # Shared UI primitives (PageHeader, SurfacePanel, AppSelect, LoadingSkeleton, etc.)
│   │   ├── design/ & styles/ # C3 color tokens and global layout styles
│   │   ├── features/         # Domain-scoped state & complex UI workflows (attempt lease, grading workspace, charts)
│   │   └── views/            # 30 route-level views across student, teacher, admin, and public flows
│   └── tests/e2e/            # Playwright real-browser end-to-end test suite
├── docs/                     # Official user, developer, and operations documentation (tracked in Git)
├── CONTEXT.md / CONTEXT.en.md# Domain terminology dictionary (Paper vs. Exam vs. Snapshot vs. Attempt vs. Final Result)
└── start-local.ps1           # Windows one-command startup script (launches PG/Redis/API/Worker/Vite with health checks)
```

---

## Quick Start

This project runs **natively without Docker**, using local PostgreSQL, Redis, FastAPI, ARQ Worker, and Vite processes.

### Prerequisites

- **Python**: `3.13.x` (managed via `uv`)
- **Node.js**: `24.x` (managed via `npm`)
- **PostgreSQL**: `18.x` (dedicated application database)
- **Redis**: `8.x` (WSL Redis is recommended on Windows)

### Option 1: Windows One-Command Startup (Recommended After Initial Setup)

Once dependencies are installed, `backend/.env` is configured, and database migrations have run, start the entire stack from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-local.ps1
```

The script sequentially starts or reuses PostgreSQL, WSL Redis, the FastAPI backend (`18000`), the ARQ worker, and the Vite frontend (`5173`), then verifies database, Redis, API, and proxy readiness. Open `http://127.0.0.1:5173` when ready.

### Option 2: Step-by-Step Manual Startup (First-Time Setup)

1. **Clone the repository**
   ```bash
   git clone https://github.com/NaSAeL-DWG/online_exam_system.git
   cd online_exam_system
   ```

2. **Configure backend, run migrations, initialize admin, and start API**
   ```bash
   cd backend
   uv sync --locked --python 3.13
   test -f .env || cp .env.example .env
   # Edit backend/.env with your DATABASE_URL, REDIS_URL, JWT_SECRET, and ADMIN_* credentials
   uv run alembic upgrade head
   uv run python -m app.cli init-admin
   uv run uvicorn app.main:app --host 127.0.0.1 --port 18000
   ```

3. **Start the background ARQ worker** (in a new terminal)
   ```bash
   cd backend
   uv run arq app.workers.attempts.WorkerSettings
   ```

4. **Start the frontend dev server** (in a new terminal)
   ```bash
   cd frontend
   npm ci
   npm run dev
   ```

5. **Open the application**
   - Frontend UI: `http://127.0.0.1:5173` (stick to `127.0.0.1` consistently—do not mix with `localhost` to avoid HttpOnly Cookie origin mismatches)
   - Backend OpenAPI Docs (Swagger UI): `http://127.0.0.1:18000/docs`

> For detailed `.env` variable explanations, troubleshooting, and production build instructions, see the **[Quick Start Guide](docs/quick-start.en.md)**.

---

## Documentation Hub

Start from the **[Documentation Hub (`docs/README.en.md`)](docs/README.en.md)** to navigate by role or task:

| Scenario | Recommended Guide | What You Will Learn |
| :--- | :--- | :--- |
| **First-time local setup** | [Quick Start (`docs/quick-start.en.md`)](docs/quick-start.en.md) | Environment setup, `.env` variables, 3-process startup order, Windows `start-local.ps1` script |
| **Explore with rich sample data** | [Demo Data (`docs/demo.en.md`)](docs/demo.en.md) | Populate 3 teachers, 6 students, 2 classes, and 9 exam states via real HTTP APIs |
| **Learn role workflows** | [User Guide (`docs/user-guide.en.md`)](docs/user-guide.en.md) | Student timed attempts & review, teacher paper assembly & grading, admin account & task management |
| **Understand domain concepts** | [Domain Context (`CONTEXT.en.md`)](CONTEXT.en.md) | Clear definitions of Question, Paper, Exam, Exam Snapshot, Attempt, and Final Result |
| **Develop & extend code** | [Architecture & Dev (`docs/development.en.md`)](docs/development.en.md) · [Backend (`backend/README.en.md`)](backend/README.en.md) · [Frontend (`frontend/README.en.md`)](frontend/README.en.md) | 3-tier boundaries, transaction & locking rules, auth security, frontend state, and development workflow |
| **Run tests & verification** | [Testing Guide (`docs/testing.en.md`)](docs/testing.en.md) | Real PostgreSQL/Redis Pytest integration tests, Playwright E2E suite, and logging acceptance commands |
| **Operate servers & inspect logs** | [Operations (`docs/operations.en.md`)](docs/operations.en.md) · [System Logs (`docs/logging.en.md`)](docs/logging.en.md) | Database upgrades/rollbacks, backups, Redis-down pure-PG recovery commands, cumulative log filtering |
| **Check benchmarks & UI specs** | [Concurrency Report (`docs/performance.en.md`)](docs/performance.en.md) · [UI Design Spec (`docs/ui-design.en.md`)](docs/ui-design.en.md) | 100-student concurrent HTTP load test report, C3 color palette, and 30-page layout standards |

---

## Scope & Security Notes

- **Version Scope**: Focused on high-reliability core exam workflows for a single institution. Multi-tenancy, sandboxed code execution, random question drawing, bulk Excel import/export, webcam proctoring, and external SMS/email OTP delivery are intentionally out of scope for v1 (password resets use administrator identity verification and temporary passwords).
- **Sensitive Data Isolation**: No default weak passwords or real secrets are stored in this repository. Runtime `.env` files, uploaded images, local database directories, log files, and test artifacts live in Git-ignored paths (such as `.local/`).

---

## License

Released under the [GNU General Public License v3.0 (GPL-3.0)](LICENSE).
