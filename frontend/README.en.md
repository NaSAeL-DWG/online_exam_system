# Frontend Engineering & Development Guide (`frontend/`)

[中文](README.md) | **English**

This directory contains the Vue 3 frontend application for the **Online Exam System**, built with **Vue 3.5 + Vite 8 + TypeScript 5.9 + Naive UI + Vue Router 5 + Pinia 4 + ECharts 6 + KaTeX + Playwright**, with dependencies locked in `package-lock.json`.

> **Global Documentation**: For initial startup steps, see the **[Quick Start Guide (`../docs/quick-start.en.md`)](../docs/quick-start.en.md)**; for visual hierarchy and color tokens, see the **[UI Design Specification (`../docs/ui-design.en.md`)](../docs/ui-design.en.md)**.

---

## 1. Directory Responsibilities & Architecture

The frontend is organized into **route views (`views`), domain features (`features`), shared UI primitives (`components`), and typed API clients (`api`)**, keeping complex state, concurrency locks, and validation out of monolithic `.vue` page files:

```text
frontend/src/
├── api/                  # Strongly typed HTTP clients, CSRF injection, cross-tab token refresh, localized field error mapping
├── components/           # Reusable stateless/base UI components
│   ├── ui/               # PageHeader, SurfacePanel, StatusBadge, AppSelect, LoadingSkeleton, PasswordIndicator, etc.
│   └── ...               # SafeMarkdown (DOMPurify + KaTeX), ListPager, QuestionFields, MemberPicker, etc.
├── composables/          # Shared composables (usePagedList race-safe pagination, useFormValidation, useUnsavedChanges)
├── design/ & styles/     # C3 visual system: tokens.css variables, theme.ts Naive UI mapping, global layouts & primitives
├── features/             # Domain-scoped state & complex UI modules
│   ├── attempts/         # Student exam workspace: Web Locks single-tab lease, BroadcastChannel takeover, local drafts, monotonic timer
│   ├── grading/          # Teacher grading workspace: whole-attempt reader, per-question scoring, history, rubric correction, task reassignment
│   ├── results/          # Result publication, withdrawal, and race-safe clearing of sensitive result views
│   ├── analytics/        # On-demand ECharts SVG runtime, teacher distribution bar charts, student trend line charts
│   ├── exams/            # Exam settings, source paper picker, class audience import, snapshot preview
│   ├── papers/           # Paper editor, question picker modal, ordering, and decimal score calculation
│   ├── questions/        # Question editor, dynamic answer forms for 4 question types, classification & validation
│   ├── identity/         # Account directory, student registration review, and credential validation rules
│   ├── classes/          # Teaching class directory & member management
│   ├── home/             # Role dashboard exam overview widgets
│   └── logs/             # Admin system log viewer, live follow/scroll pause, temporary DEBUG & file logging controls
├── layouts/              # AppLayout (204px white square-corner sidebar) & AuthLayout (public login/registration shell)
├── navigation/           # Role navigation groups and permission filtering
├── stores/               # Pinia auth store (current user identity; never stores credentials in localStorage)
├── views/                # 30 route-level page views orchestrating user tasks
└── router.ts             # Route definitions, auth guards, forced password change redirect, and pending-student restrictions
```

---

## 2. Core Frontend Mechanisms

### 1. C3 Visual System & Accessibility Conventions

- **Color Palette & Geometry**: The workspace canvas uses subtle cool gray `#F6F7F9` (Neutral 50), content cards and navigation bars use pure white `#FFFFFF`, and primary actions/focus borders use bright Blue 600 `#2164CE`. Sidebar navigation items use **strict `0 px` square corners with a `3 px` inner blue indicator bar**. Always reference semantic variables from `src/styles/tokens.css`.
- **Custom Select & Skeleton Sweep**: All dropdowns use `AppSelect.vue` (combobox semantics, popover shadow, searchable multi-select, and keyboard navigation). Loading states use `LoadingSkeleton.vue` (3.2s white shimmer sweep that respects `prefers-reduced-motion`).
- **Desktop + 390px Mobile Responsiveness**: Every page renders a single clear `h1`. Wide data tables scroll horizontally **inside their table container** on 390px viewports—never forcing a minimum page width that causes full-page horizontal overflow.

### 2. HttpOnly Cookie Auth, CSRF & Cross-Tab Refresh Coordination

- `src/api/client.ts` centralizes all HTTP requests; view components never call raw `fetch` or manipulate cookies.
- Mutating requests (`POST`/`PUT`/`PATCH`/`DELETE`) automatically attach the `X-CSRF-Token` header.
- When an Access Token expires and `/api/auth/refresh` is needed to rotate the single-use Refresh Token, the client serializes refresh calls using **in-tab Promise deduplication + cross-tab Web Locks**, preventing concurrent tabs from replaying a consumed token and triggering session revocation.

### 3. Timed Student Attempts: Single-Tab Write Lease & Draft Protection (`features/attempts/`)

- **Reading Details Does Not Consume Attempts**: Viewing `StudentExamDetailView` is read-only; an attempt is created only when the student clicks "Start Exam".
- **Web Locks + BroadcastChannel Single-Tab Lease (`pageLease.ts`)**:
  - Every page load generates a fresh in-memory instance ID; normal refreshes preserve the tab token in `sessionStorage` and re-acquire the browser Web Lock.
  - Duplicating a tab cannot acquire the active Web Lock and falls back to **read-only mode**.
  - Opening an active attempt on a new device or tab without the token defaults to read-only and offers an explicit **"Take Over"** button. Taking over increments `token_generation` on the server and notifies older tabs via `BroadcastChannel` to release their lock and switch to read-only.
- **Authoritative Countdown & Debounced Submission**: The countdown timer combines server `server_now`, fixed `deadline_at`, and browser monotonic time (`performance.now()`), making local clock tampering ineffective. Manual submission flushes pending debounced saves before listing unanswered questions for confirmation.

### 4. Grading Workspace, Anti-Stale Result Clearing & On-Demand Charts

- **Focused Grading & Conflict Protection**: `StaffAttemptView` uses a distraction-free `1248 px` workspace without the global sidebar. Before initial whole-paper completion, only the assigned teacher can score (`can_grade`); afterwards, other active teachers can adjust scores with a mandatory reason. On version conflicts, unsaved form inputs are preserved while prompting the teacher to reload.
- **Zero Persistent Caching for Sensitive Results**: Scores, reviews, and mistakes are never cached in global stores. Every reload clears previous state and increments a request generation counter so late-arriving responses cannot repopulate withdrawn scores.
- **On-Demand ECharts SVG**: `features/analytics/` splits the ECharts runtime from bar and line chart registrations using the crisp SVG renderer, accompanied by expandable data tables.

### 5. Uncertain Write Recovery & Unsaved Changes Guard

- **Uncertain Write Feedback**: If a connection drops after sending a password or contact update, the UI instructs the user to verify by logging in with the new password or reloading profile data rather than blindly re-submitting. Responses carrying `X-Session-Cleanup: pending` display normal completion feedback.
- **Unsaved Changes Guard (`useUnsavedChanges.ts`)**: Editing questions, papers, exams, grades, or mistake notes prompts for confirmation before route navigation, modal dismissal, or browser reload—except when a session expires or result permissions are revoked, where immediate security cleanup takes precedence.

---

## 3. Local Development, Build & E2E Testing Commands

Run all commands inside `frontend/` (Node.js 24):

```bash
# 1. Install locked dependencies
npm ci

# 2. Start local dev server (http://127.0.0.1:5173, proxying /api to http://127.0.0.1:18000)
npm run dev

# 3. Type-check with vue-tsc and build production bundle
npm run build

# 4. Check or format code with Prettier
npm run format:check
npm run format

# 5. Run Playwright real-browser E2E tests (requires running backend & ../.local/e2e.env)
set -a
source ../.local/e2e.env
set +a
npm run test:e2e -- tests/e2e/student-attempt.spec.ts --workers=1
```

> **Tip**: To customize the backend API proxy target, copy `.env.example` to `.env.local` and set `VITE_API_TARGET`. Always access `http://127.0.0.1:5173` consistently without mixing `localhost`. See the **[Testing & Verification Guide (`../docs/testing.en.md`)](../docs/testing.en.md)** for full details.
