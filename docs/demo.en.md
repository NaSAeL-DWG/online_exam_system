# Repeatable Demo Data Guide

[中文](demo.md) | **English**

If you want to showcase the system or explore a rich local environment covering diverse exam states, scores, mistakes, and grading tasks, you don't need to register a dozen accounts by hand—simply run the built-in `app.demo` module.

**How it works cleanly:**
- It drives the system exclusively through **public HTTP APIs** (real registration, approval, question authoring, paper assembly, exam release, timed answering, submission, grading, and result publication)—**never bypassing permissions, mutating database timestamps directly, or using hidden backdoor endpoints**.
- All created records are scoped to an isolated **Namespace** prefix, preserving any existing data in your database and supporting safe resumption after interruptions.

---

## 1. Prerequisites & Execution

Before running the demo generator, complete the **[Quick Start Guide](quick-start.en.md)** to migrate the database, initialize the administrator, and start both the **FastAPI Backend API** and the **ARQ Worker**.

### Step 1: Prepare Private Environment Variables

Create a Git-ignored `.local/demo.env` file with the following three variables:

| Variable | Description |
| :--- | :--- |
| `DEMO_ADMIN_LOGIN` | Existing administrator login name (falls back to `ADMIN_LOGIN_NAME` if omitted) |
| `DEMO_ADMIN_PASSWORD` | Administrator password (falls back to `ADMIN_PASSWORD` if omitted) |
| `DEMO_PASSWORD` | **Required**: Shared password (`>= 10` characters) assigned to all generated demo teachers and students in this namespace |

> **Security Note**: Quote special characters properly in Bash-sourceable format, and never pass real passwords directly as CLI arguments.

### Step 2: Run the Demo Generator

From the repository root (in Git Bash / Bash):

```bash
cd backend
set -a
source ../.local/demo.env
set +a

uv run python -m app.demo \
  --base-url http://127.0.0.1:18000 \
  --namespace demo-v1 \
  --manifest ../.local/demo-v1.json \
  --window-seconds 120
```

**What to expect during execution:**
- Because the script runs real timed exams through public HTTP APIs, it **waits for short real-time exam windows to expire** before triggering post-exam grading and result publication. Expect the command to take a few minutes.
- `--window-seconds` controls the short exam duration (120 seconds by default, minimum 30 seconds; increase on slower machines).
- If you only want to provision teachers, students, and teaching classes first, append `--stage identities`; you can run the full stage later using the same `--namespace` and `--manifest`.

---

## 2. Generated Scenarios & Recommended Walkthrough

When finished, the command prints the namespace mapping and generated account logins (`t1`–`t3` for teachers, `s1`–`s6` for students) without printing passwords or answer keys. Sign in using `DEMO_PASSWORD`.

### Built-In Demo Scenarios

| Generated Objects | What Feature It Demonstrates |
| :--- | :--- |
| **3 Teachers, 6 Students, 2 Classes** | Multi-teacher class collaboration, students in multiple classes, absence tracking, and eligibility revocation |
| **4 Question Types + 100-Point Paper** | Shared question bank, Markdown/LaTeX formulas, paper reuse, and isolated exam snapshots |
| **Published Restricted Exam** | Multiple attempts where a **lower second attempt score becomes the Final Result** (last valid submission rule) |
| **Published Public Exam** | Public exam statistics without a fixed roster denominator, plus student paper review & mistake collection |
| **Published Exam with Review Disabled** | Permission boundary: students can see their total score, but cannot open question details, keys, or mistakes |
| **Exam with Latest Attempt Pending Grading** | Strict score state: Final Result shows "Pending Grading" rather than falling back to an earlier graded attempt |
| **Exam Under Result Correction** | Results withdrawn by the teacher—student scores, mistakes, and analytics are immediately hidden |
| **Revoked Eligibility & Cancelled Exam** | Voided attempts retained for audit history but excluded from normal statistics |
| **Active, Upcoming & Draft Exams** | Ready for live interactive testing: start an attempt, autosave, submit, or edit and release a draft exam |

### Recommended Live Demo Order

1. **Sign in as a Teacher (`t1`)**: Inspect the teacher dashboard pending grading banner → browse the Question Bank and Papers → open a published exam to view score distribution charts → open a pending grading task to demonstrate live short-answer scoring.
2. **Sign in as a Student (`s1`)**: View the student dashboard countdown card and dual-column overview → open **Exam History** to compare review-enabled, review-disabled, and pending-grading states → open **My Mistakes** to add a study note and mark an item as mastered → check **Learning Analytics** → finally, start the **Active Exam** to demonstrate live autosave and submission.
3. **Sign in as Administrator**: Check global grading progress, demonstrate task reassignment, and open **System Logs** to show real-time runtime logs and security audit entries from the actions above.

---

## 3. Resuming & Starting Fresh Runs

- **Idempotent Resume**: `.local/demo-v1.json` records progress and object IDs. Re-running with the same `--namespace` and `--manifest` resumes from where it left off without resetting existing scores, passwords, or manual notes.
- **Creating Fresh Live Exams**: Because active exams expire as real time passes, re-running an existing namespace will not infinitely extend expired exams. To generate a fresh set of live exams, simply specify a new namespace (e.g., `--namespace demo-v2` with `--manifest ../.local/demo-v2.json`).
- **Environment Isolation**: There is no destructive namespace-wipe endpoint. Run `app.demo` only against development or dedicated demo databases—never against a production database.
