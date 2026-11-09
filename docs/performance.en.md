# 100-Student Concurrency Benchmark & Reproduction Guide

[中文](performance.md) | **English**

To verify system stability and data consistency under realistic classroom exam peaks, we executed **three end-to-end HTTP concurrency rounds with 100 simultaneous students per round (20 objective questions per paper, generating 2,000 answer writes per round)** on a local single-machine environment.

> **Executive Summary**: Across all three rounds (covering staggered steady-state answering, 100-student simultaneous peak answering with worker outage recovery, and 100-student timeout auto-submission), all **13,600 exam business HTTP requests succeeded (100% success rate, zero 5xx errors, zero transport failures)**, and every student's submission state, saved answers, and final score matched 100%.
> *Note: These results represent the documented local hardware and short-duration objective-question workload; they are not a blanket guarantee for wide-area network or multi-hour production capacity.*

---

## 1. Benchmark Hardware & Software Environment

| Dimension | Measured Configuration |
| :--- | :--- |
| **OS / CPU / RAM** | Windows 11 · Intel Core i7-14650HX (24 logical cores) · ~15.61 GiB RAM |
| **Backend Runtime** | Python 3.13.14 · FastAPI 0.117.1 · Uvicorn 0.36.0 |
| **Data Stores** | PostgreSQL 18.3 · Redis 8.8 |
| **Process Topology** | 1 FastAPI application process + 1 standalone ARQ worker process |
| **DB Connection Pool** | SQLAlchemy pool size `5`, max overflow `10` per process; PostgreSQL `max_connections=100` |
| **Isolated Targets** | Database `exam_test_iteration6_load` · Redis DB `13` · API port `18001` · dedicated queue per round |
| **Cumulative Dataset** | 417 accounts, 12 exams, 416 attempts, 8,064 saved answers (~18.46 MiB database size) |

**Preparation & Rate-Limit Verification:**
- Every simulated student had an independent account, HttpOnly Cookie session, exam attempt, and single-tab Page Lease token.
- Account provisioning and login were timed separately (at most 5 concurrent logins at a time, **keeping authentication rate limiting enabled**). Sending 12 consecutive login requests from the same IP for a non-existent user consistently returned 10 `401` responses followed by 2 `429 Too Many Requests` responses in every round.

---

## 2. Three-Round 100-Student Benchmark Results

In each round, 100 students executed the full workflow: **list exams → read exam details → start exam → activate page lease → save all 20 answers one by one → re-read attempt state**. To verify grading accuracy deterministically, **50 students submitted all-correct answers (expected score: 50) and 50 submitted all-wrong answers (expected score: 0)**.

| Scenario | Business Requests | Answering Window | Latency (p50 / p95 / p99) | Post-Run Consistency & Grading Verification |
| :--- | :---: | :---: | :---: | :--- |
| **Round 1: Staggered Steady State**<br>5s staggered entry, 0.75–1.25s think time per question, resident worker running, manual submit | **4,600 / 4,600**<br>(100%) | 45.147 s | 318 ms / 764 ms / 1,025 ms | All 100 manual submissions, saved answers, and 50/0 scores matched 100% |
| **Round 2: Simultaneous Peak + Worker Recovery**<br>100 students start at the same second with zero think time; worker paused during exam, started after all 100 submit | **4,600 / 4,600**<br>(100%) | 33.123 s | 687 ms / 1,222 ms / 1,549 ms | Before worker start: 100 submitted / 0 graded (zero data loss);<br>After worker start: all 100 graded within **6.530 s** with 100% score accuracy |
| **Round 3: Peak Saves + Timeout Auto-Submit**<br>100 students save 20 answers with zero think time without clicking submit; worker started after real 60s deadline expires | **4,400 / 4,400**<br>(100%) | 31.594 s | 692 ms / 1,243 ms / 1,568 ms | After worker start: all 100 attempts auto-submitted as `TIMEOUT` and graded within **5.552 s**, with `effective_submitted_at == deadline` |

### Key Takeaways
1. **Latency Profile**: Peak in-flight concurrency reached 100 requests. In Round 1 (steady state with realistic think time), overall p95 latency was **763.7 ms** (under 1 second), while row-locking write endpoints (`start` and `activate`) recorded p95 latencies of `1,033.2 ms` and `1,015.2 ms` respectively.
2. **Recovery Window**: The `6.530 s` and `5.552 s` recovery windows in Rounds 2 and 3 include pre-recovery staff HTTP checks, worker process startup, and final HTTP verification—pure worker execution time is even shorter.
3. **Resource Footprint**: Peak RSS memory for the API process tree was **~131.56 MiB** and **~92.05 MiB** for the worker, with API single-core CPU peaking at `106.513%`.

---

## 3. How to Reproduce the Benchmark Locally

The full benchmark harness lives in `backend/scripts/verify_concurrency.py`.

### 1. Prerequisites
1. Sync locked backend dependencies (`uv sync --locked --python 3.13`) and ensure local PostgreSQL and Redis are running.
2. Prepare `.local/backend-test.env` with `TEST_DATABASE_URL` and `TEST_REDIS_URL` (the database user must have privileges to create isolated test databases and run migrations; see **[Testing & Verification Guide](testing.en.md)**).

### 2. Run the Benchmark Commands Sequentially
Run the commands one by one from `backend/` (do not run browser E2E tests or other heavy workloads concurrently):

```bash
cd backend

# 0. Pre-flight environment check
uv run python scripts/verify_concurrency.py --source-env ../.local/backend-test.env --check-only

# 1. Round 1: 100 students, steady mode, resident worker running
uv run python scripts/verify_concurrency.py --source-env ../.local/backend-test.env \
  --students 100 --questions 20 --mode steady --worker-policy running

# 2. Round 2: 100 students, peak mode, worker paused then recovered
uv run python scripts/verify_concurrency.py --source-env ../.local/backend-test.env \
  --students 100 --questions 20 --mode peak --worker-policy recover

# 3. Round 3: 100 students, peak saves, timeout auto-submission after 60s deadline
uv run python scripts/verify_concurrency.py --source-env ../.local/backend-test.env \
  --students 100 --questions 20 --mode peak --worker-policy recover \
  --submission timeout --deadline-seconds 60
```

### 3. Safety Guarantees & Output Artifacts
- **Strict Isolation**: The script only accepts localhost targets, a dedicated database (`exam_test_iteration6_load`), and port `18001`. It spawns and stops its own API and worker processes and never touches your development database.
- **Artifact Location**: Each run writes `summary.json`, per-request latencies, and resource samples under Git-ignored `.local/iteration6/load/`.

---

## 4. Scope Limitations

This benchmark covers short-duration localhost HTTP answering, per-question autosave, manual/timeout submission, and worker recovery. It does not simulate 100 simultaneous logins at the exact same millisecond, wide-area network latency, multi-hour open connections, large image payloads, or concurrent manual short-answer grading. Re-run capacity verification on your target production hardware before live high-stakes exams.
