# System Logs & Security Audit Guide

[中文](logging.md) | **English**

Active system administrators can open **"System Logs"** (`/admin/logs`) from the sidebar to inspect **Runtime Logs** and **Security Audit Logs** across the platform.

> **Permission Boundary**: Teachers, students, and unauthenticated users cannot view, download, or configure system logs. All filtering, settings, and export endpoints enforce administrator authorization on the backend.

---

## 1. Viewing & Filtering Logs (Cumulative Level Rules)

Switch between two tabs at the top of the page:
- **Runtime Logs**: Filter by time range, module, task name, keyword, and request/task correlation ID.
- **Security Audit Logs**: Filter by actor, action type, entity type, and entity ID to track logins, password resets, exam releases, score changes, and result publications/withdrawals.

Runtime logs follow a unified, human-readable line format:

```text
2026-11-02T14:23:08.126+08:00 INFO: [exam](发布考试): 考试发布成功
```

### Important: Cumulative Level Filtering Rule
Unlike traditional log viewers that filter by "selected severity and above", this project uses an **additive/cumulative level rule** so normal business context stays visible when troubleshooting warnings or errors:

| Selected Level | Levels Actually Displayed | Typical Use Case |
| :--- | :--- | :--- |
| **`INFO`** | **`INFO` only** | Inspect normal business workflow milestones |
| **`WARNING`** | **`INFO` + `WARNING`** | View normal milestones alongside warning conditions |
| **`ERROR`** | **`INFO` + `WARNING` + `ERROR`** | Troubleshoot errors while keeping surrounding `INFO`/`WARNING` context |
| **`DEBUG`** | **All collected levels (including `DEBUG`)** | Deep-dive into internal diagnostics (use with the 15-minute temporary DEBUG toggle below) |

### Live Follow & Browsing Experience
- **Auto-Refresh & Scroll Pause**: Live polling (every 3 seconds) and auto-scrolling are enabled by default. Scrolling up to read older entries automatically pauses auto-follow so new lines don't jump your viewport; click **"Jump to Latest"** to resume following.
- **Bounded Memory & Race Protection**: Historical logs paginate cleanly while capping in-memory DOM rows so leaving the tab open for hours never exhausts browser memory. When switching filters rapidly, late responses from older requests are discarded.
- **Timezone Formatting**: The table displays timestamps in your browser's local timezone; expanding a log row or downloading `.log` files preserves the server's original timezone-aware ISO timestamp (e.g., `+08:00`).

---

## 2. Enabling 15-Minute Temporary DEBUG Collection

To keep routine read queries, log-page polling, and empty worker scans from flooding the database, the system collects only `INFO`, `WARNING`, and `ERROR` logs by default. Selecting `DEBUG` in the filter dropdown only widens the query view—if `DEBUG` collection wasn't active when an event occurred, no `DEBUG` rows exist.

**When you need deep diagnostic detail for a specific module:**
1. Open the settings panel on the System Logs page, select the target module(s), and enable **"Temporary DEBUG Collection"**.
2. All API and worker processes connected to the same database immediately begin recording `DEBUG` events for those modules.
3. **Automatic 15-Minute Expiration**: To prevent forgotten debug toggles from filling up storage, temporary DEBUG collection **automatically expires after 15 minutes** (or can be turned off manually at any time).

---

## 3. Online Retention & Server File Logging

Administrators can toggle **"Server File Logging"** on or off (persisted in PostgreSQL across restarts):

| Server File Logging | Online Runtime Logs in PostgreSQL | Local `.log` Files on Server |
| :--- | :--- | :--- |
| **Off (Default)** | Retains the latest **20,000 entries** (no 7-day time pruning) | **No new files created or appended** |
| **On** | Retains up to **100,000 entries** and at most **7 days** | Writes to `LOG_STORAGE_DIR`: max **10 MiB** per file, up to **5 rotated files** |

### Storage & Rotation Details
- **What happens when switching File Logging back off?** Even with file logging disabled, the most recent 20,000 runtime logs remain persisted in PostgreSQL across restarts. Switching from On to Off prunes online database records back to the latest 20,000 entries while leaving existing `.log` files on disk untouched (re-enabling file logging later does not re-import pruned historical rows into PostgreSQL).
- **Audit Logs Are Never Pruned by Log Retention Rules**: Security audit records (`Audit Logs`) are stored in a separate table and are **never deleted** by the 20,000 / 100,000 row or 7-day runtime log pruning rules.
- **Shared Directory Configuration**: `LOG_STORAGE_DIR` in `backend/.env` (default `../.local/logs`) must point to the same writable directory across API, worker, and CLI processes. Database locks coordinate multi-process file writes on a single host (multi-host deployments require a shared filesystem).

---

## 4. Exporting Logs & Security Redaction Boundaries

### 1. Downloading `.log` Exports
Clicking **"Download Logs"** exports the current view (Runtime Logs or Security Audits) under the active filter criteria as a UTF-8 `.log` file (available regardless of whether server file logging is enabled).
- **10,000-Row Export Cap**: Each export returns up to 10,000 records. If your current filter matches more than 10,000 rows, the API prompts you to narrow your time range or filters—**never silently truncating the file or exporting only the current page**.
- Toggling file logging, changing temporary DEBUG settings, and downloading log exports are themselves recorded in the security audit log.

### 2. Strict Redaction Boundaries
To protect user privacy and exam integrity:
- **Never Logged**: Plaintext passwords, JWT/session tokens, cookies, database connection URLs, full HTTP request bodies, student answers, or unpublished reference answers and explanations.
- **Exception Safety**: Unhandled exception tracebacks never dump local frame variables into log records.
- **Redacted Audit Summaries**: The admin audit view displays safe summaries without exposing private contact details, student answers, or raw before/after payload snapshots.

---

## 5. Developer Maintenance & Self-Check

1. **Verifying the Logging Pipeline**
   Run the built-in diagnostic command from `backend/`:
   ```bash
   uv run python -m app.cli logging-check --module cli --count 1
   ```
   This emits a fixed safe diagnostic entry that you can immediately verify under the `cli` module filter in `/admin/logs` (avoid running large `--count` values in production so you don't evict useful history).
2. **Adding New Log Points in Code**
   - Runtime log persistence uses an independent transaction and a bounded per-process queue (max 5,000 entries, flushed in batches of up to 200). If a storage outage overflows the queue, dropped diagnostic counts are reported in the next successful batch—**logging failures never block or roll back business operations**.
   - Always supply stable `module` and `task` names plus correlation IDs, and log only operation outcomes and entity IDs—never raw user form inputs.
