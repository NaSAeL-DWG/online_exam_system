"""通过公开 HTTP/CLI 验证系统日志的独立验收。"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import socket
import sys
from uuid import uuid4
from urllib.parse import urlsplit

import pytest
from httpx import ASGITransport, AsyncClient

BACKEND = Path(__file__).resolve().parents[1]
EVIDENCE = BACKEND.parent / ".local" / "logging" / "acceptance"
RUN_FILES = EVIDENCE / "files" / uuid4().hex


class PrivateEnvironment(dict):
    def __repr__(self):
        return "<私有进程环境>"


@pytest.fixture(autouse=True)
def isolate_acceptance_files(monkeypatch):
    monkeypatch.setenv("LOG_STORAGE_DIR", str(RUN_FILES))


@pytest.fixture
async def client(database_url, redis_url, isolate_acceptance_files):
    """显式配置公开应用入口，避免与其他测试组合时复用缓存目录。"""
    from app.config import Settings
    from app.main import create_app

    application = create_app(Settings())
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://testserver"
        ) as http_client:
            yield http_client


async def emit_logs(*arguments):
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.cli",
        "logging-check",
        *map(str, arguments),
        cwd=BACKEND,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    assert process.returncode == 0, stderr.decode("utf-8", errors="replace")
    return json.loads(stdout)


async def runtime_identifiers(client, **query):
    identifiers = []
    while True:
        response = await client.get(
            "/api/admin/logs/runtime", params={**query, "level": "DEBUG", "page_size": 100}
        )
        assert response.status_code == 200
        body = response.json()
        identifiers.extend(row["id"] for row in body["items"])
        if not body["has_more"]:
            break
        assert body["next_before"]
        query["before"] = body["next_before"]
    assert len(set(identifiers)) == len(identifiers)
    return identifiers


async def wait_for_runtime_request(client, response):
    correlation_id = response.headers["X-Request-ID"]
    for _ in range(50):
        observed = await client.get(
            "/api/admin/logs/runtime",
            params={"correlation_id": correlation_id, "level": "DEBUG"},
        )
        if observed.json()["items"]:
            return
        await asyncio.sleep(0.1)
    pytest.fail("设置响应对应的运行记录未在5秒内可见")


@asynccontextmanager
async def independent_api(directory, clock_file=None, environment_override=None):
    """启动独立网络 API；时钟偏移只用于明确标注的时间边界模拟。"""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    environment = os.environ.copy()
    environment["LOG_STORAGE_DIR"] = str(directory)
    environment.update(environment_override or {})
    arguments = [sys.executable, "-m", "uvicorn", "app.main:app"]
    if clock_file is not None:
        environment["ACCEPTANCE_CLOCK_FILE"] = str(clock_file)
        launcher = (
            "import os\n"
            "from pathlib import Path\n"
            "from datetime import datetime, timedelta, timezone\n"
            "import app.core.clock as clock\n"
            "clock.utc_now = lambda: datetime.now(timezone.utc) + timedelta("
            "seconds=float(Path(os.environ['ACCEPTANCE_CLOCK_FILE']).read_text() or '0'))\n"
            "import uvicorn\n"
            f"uvicorn.run('app.main:app', host='127.0.0.1', port={port})\n"
        )
        arguments = [sys.executable, "-c", launcher]
    else:
        arguments += ["--host", "127.0.0.1", "--port", str(port)]
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with (EVIDENCE / f"api-{port}.txt").open("wb") as output:
        process = await asyncio.create_subprocess_exec(
            *arguments, cwd=BACKEND, env=environment, stdout=output, stderr=output
        )
        try:
            async with AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=10) as remote:
                for _ in range(100):
                    try:
                        health = await remote.get("/api/health")
                        if health.status_code == 200:
                            break
                    except Exception:
                        pass
                    if process.returncode is not None:
                        pytest.fail("独立API启动失败，见隔离证据目录")
                    await asyncio.sleep(0.1)
                else:
                    pytest.fail("独立API未在10秒内就绪")
                yield remote
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=10)
                except TimeoutError:
                    process.kill()
                    await process.wait()


async def admin_session(client):
    return await login_session(client, os.environ["ADMIN_LOGIN_NAME"], os.environ["ADMIN_PASSWORD"])


async def login_session(client, login_name, password):
    token = (await client.get("/api/auth/csrf")).json()["csrf_token"]
    headers = {"X-CSRF-Token": token}
    logged_in = await client.post(
        "/api/auth/login",
        headers=headers,
        json={
            "login_name": login_name,
            "password": password,
        },
    )
    assert logged_in.status_code == 200
    return headers


@pytest.mark.asyncio
async def test_logging_settings_requires_admin_and_never_caches_denial(client):
    response = await client.get("/api/admin/logs/settings")

    assert response.status_code == 401
    assert response.headers.get("cache-control") == "no-store"


@pytest.mark.asyncio
async def test_logging_export_requires_csrf_even_for_authenticated_admin(client):
    await admin_session(client)
    response = await client.post("/api/admin/logs/runtime/export")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "CSRF_INVALID"
    assert response.headers.get("cache-control") == "no-store"


@pytest.mark.asyncio
async def test_audit_list_and_download_hide_free_text_review_reason(client):
    suffix = uuid4().hex[:12]
    token = (await client.get("/api/auth/csrf")).json()["csrf_token"]
    registered = await client.post(
        "/api/auth/register",
        headers={"X-CSRF-Token": token},
        json={
            "student_no": f"L{suffix}",
            "real_name": "日志验收学生",
            "email": f"log-private-{suffix}@example.com",
            "phone_number": "13800991234",
            "password": "AcceptanceSecret!123",
        },
    )
    assert registered.status_code == 201
    review_id = registered.json()["application"]["id"]
    client.cookies.clear()
    headers = await admin_session(client)
    secret_reason = f"答案解析-secret-{suffix}; phone=13800991234"
    reviewed = await client.post(
        f"/api/staff/reviews/{review_id}/decision",
        headers=headers,
        json={"decision": "REJECTED", "reason": secret_reason},
    )
    assert reviewed.status_code == 200

    query = {"entity_id": review_id, "action": "REGISTRATION_REVIEW_DECIDED"}
    listed = await client.get("/api/admin/logs/audit", params=query)
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1
    downloaded = await client.post("/api/admin/logs/audit/export", params=query, headers=headers)
    assert downloaded.status_code == 200

    # 业务接口允许原始审核意见；日志视图和下载只允许安全摘要。
    for output in (listed.text, downloaded.text):
        assert secret_reason not in output
        assert f"secret-{suffix}" not in output
        assert "13800991234" not in output
        assert f"log-private-{suffix}@example.com" not in output
        assert "AcceptanceSecret!123" not in output
        assert "before_data" not in output
        assert "after_data" not in output
    assert downloaded.headers.get("cache-control") == "no-store"
    assert ".log" in downloaded.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_activated_teacher_cannot_read_download_or_modify_any_log_view(client):
    suffix = uuid4().hex[:12]
    headers = await admin_session(client)
    teacher_no = f"LT{suffix}"
    created = await client.post(
        "/api/admin/teachers",
        headers=headers,
        json={
            "teacher_no": teacher_no,
            "real_name": "日志权限验收教师",
            "email": f"log-teacher-{suffix}@example.com",
            "phone_number": "13800991235",
            "temporary_password": "TemporarySecret!123",
        },
    )
    assert created.status_code == 201
    client.cookies.clear()
    headers = await login_session(client, teacher_no, "TemporarySecret!123")
    changed = await client.put(
        "/api/auth/password",
        headers=headers,
        json={"current_password": "TemporarySecret!123", "new_password": "TeacherSecret!123"},
    )
    assert changed.status_code == 204
    client.cookies.clear()
    headers = await login_session(client, teacher_no, "TeacherSecret!123")
    me = await client.get("/api/auth/me")
    assert me.json()["user"]["status"] == "ACTIVATED"
    assert me.json()["user"]["must_change_password"] is False

    requests = [
        ("GET", "/settings", None),
        ("GET", "/runtime", None),
        ("GET", "/audit", None),
        ("POST", "/runtime/export", None),
        ("POST", "/audit/export", None),
        ("PATCH", "/settings", {"file_enabled": True}),
        ("PUT", "/debug/auth", {"enabled": True}),
    ]
    for method, path, payload in requests:
        response = await client.request(
            method, f"/api/admin/logs{path}", headers=headers, json=payload
        )
        assert response.status_code == 403, (method, path)
        assert response.headers.get("cache-control") == "no-store", (method, path)


@pytest.mark.asyncio
async def test_runtime_levels_are_cumulative_and_debug_is_temporary(client):
    headers = await admin_session(client)
    marker = f"levels-{uuid4().hex}"
    module = "acceptance"
    started = datetime.now(timezone.utc)
    enabled = await client.put(
        f"/api/admin/logs/debug/{module}", headers=headers, json={"enabled": True}
    )
    assert enabled.status_code == 200
    expiry = next(
        entry["expires_at"]
        for entry in enabled.json()["debug_modules"]
        if entry["module"] == module
    )
    assert started + timedelta(minutes=14, seconds=59) < datetime.fromisoformat(expiry)
    assert datetime.fromisoformat(expiry) < started + timedelta(minutes=15, seconds=3)
    try:
        for level in ("DEBUG", "INFO", "WARNING", "ERROR"):
            await emit_logs(
                "--module",
                module,
                "--task",
                "levels",
                "--level",
                level,
                "--correlation-id",
                marker,
            )
        expected = {
            "INFO": {"INFO"},
            "WARNING": {"INFO", "WARNING"},
            "ERROR": {"INFO", "WARNING", "ERROR"},
            "DEBUG": {"DEBUG", "INFO", "WARNING", "ERROR"},
        }
        for level, collected in expected.items():
            response = await client.get(
                "/api/admin/logs/runtime",
                params={
                    "correlation_id": marker,
                    "level": level,
                    "module": module,
                    "task": "levels",
                },
            )
            assert response.status_code == 200
            assert {row["level"] for row in response.json()["items"]} == collected
            assert len(response.json()["items"]) == len(collected)
    finally:
        stopped = await client.put(
            f"/api/admin/logs/debug/{module}", headers=headers, json={"enabled": False}
        )
        assert stopped.status_code == 200

    await emit_logs("--module", module, "--level", "DEBUG", "--correlation-id", marker)
    response = await client.get(
        "/api/admin/logs/runtime", params={"correlation_id": marker, "level": "DEBUG"}
    )
    assert len(response.json()["items"]) == 4


@pytest.mark.asyncio
async def test_runtime_export_accepts_ten_thousand_and_explicitly_rejects_one_more(client):
    headers = await admin_session(client)
    marker = f"export-{uuid4().hex}"
    await emit_logs("--count", 10000, "--correlation-id", marker)
    query = {"correlation_id": marker, "before": "1", "page_size": 1}
    accepted = await client.post("/api/admin/logs/runtime/export", params=query, headers=headers)
    assert accepted.status_code == 200
    assert len(accepted.content.decode("utf-8").splitlines()) == 10000
    assert "charset=utf-8" in accepted.headers.get("content-type", "").lower()
    assert ".log" in accepted.headers.get("content-disposition", "")

    await emit_logs("--correlation-id", marker)
    rejected = await client.post("/api/admin/logs/runtime/export", params=query, headers=headers)
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "LOG_EXPORT_LIMIT"
    assert rejected.headers.get("cache-control") == "no-store"


@pytest.mark.asyncio
async def test_file_disabled_keeps_twenty_thousand_without_seven_day_expiry(client):
    headers = await admin_session(client)
    settings = await client.patch(
        "/api/admin/logs/settings", headers=headers, json={"file_enabled": False}
    )
    assert settings.json()["runtime_limit"] == 20000
    assert settings.json()["retention_days"] is None
    audit = await client.get("/api/admin/logs/audit", params={"action": "LOG_FILE_SETTINGS"})
    audit_witness = audit.json()["items"][0]["id"]

    aged_marker = f"disabled-aged-{uuid4().hex}"
    old_time = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    await emit_logs("--timestamp", old_time, "--correlation-id", aged_marker)
    assert len(await runtime_identifiers(client, correlation_id=aged_marker)) == 1

    marker = f"disabled-cap-{uuid4().hex}"
    await emit_logs("--count", 20001, "--correlation-id", marker)
    assert len(await runtime_identifiers(client, correlation_id=marker)) == 20000
    audit = await client.get("/api/admin/logs/audit", params={"action": "LOG_FILE_SETTINGS"})
    assert audit_witness in {row["id"] for row in audit.json()["items"]}


@pytest.mark.asyncio
async def test_file_enabled_enforces_age_and_hundred_thousand_then_shrinks_on_disable(client):
    headers = await admin_session(client)
    enabled = await client.patch(
        "/api/admin/logs/settings", headers=headers, json={"file_enabled": True}
    )
    assert enabled.status_code == 200
    assert enabled.json()["runtime_limit"] == 100000
    assert enabled.json()["retention_days"] == 7
    try:
        old_marker = f"enabled-aged-{uuid4().hex}"
        old_time = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        await emit_logs("--timestamp", old_time, "--correlation-id", old_marker)
        assert await runtime_identifiers(client, correlation_id=old_marker) == []

        recent_marker = f"enabled-recent-{uuid4().hex}"
        recent_time = (datetime.now(timezone.utc) - timedelta(days=6)).isoformat()
        await emit_logs("--timestamp", recent_time, "--correlation-id", recent_marker)
        assert len(await runtime_identifiers(client, correlation_id=recent_marker)) == 1

        marker = f"enabled-cap-{uuid4().hex}"
        await emit_logs("--count", 100001, "--correlation-id", marker)
        assert len(await runtime_identifiers(client, correlation_id=marker)) == 100000
        files_before = {path.name for path in RUN_FILES.glob("runtime.log*")}
        assert files_before
        disabled = await client.patch(
            "/api/admin/logs/settings", headers=headers, json={"file_enabled": False}
        )
        assert disabled.status_code == 200
        # 关闭设置本身也会产生运行记录，总配额应覆盖所有模块。
        await wait_for_runtime_request(client, disabled)
        assert len(await runtime_identifiers(client)) == 20000
        assert {path.name for path in RUN_FILES.glob("runtime.log*")} == files_before
    finally:
        disabled = await client.patch(
            "/api/admin/logs/settings", headers=headers, json={"file_enabled": False}
        )
        assert disabled.status_code == 200


@pytest.mark.asyncio
async def test_incremental_backlog_and_literal_search_do_not_drop_same_time_records(client):
    await admin_session(client)
    marker = f"cursor-{uuid4().hex}"
    instant = datetime.now(timezone.utc).isoformat()
    arguments = (
        "--module",
        "acceptance",
        "--task",
        "pagination",
        "--correlation-id",
        marker,
        "--timestamp",
        instant,
    )
    await emit_logs(*arguments)
    first = await client.get("/api/admin/logs/runtime", params={"correlation_id": marker})
    anchor_id = first.json()["items"][0]["id"]
    cursor = first.json()["latest_cursor"]
    await emit_logs(*arguments, "--count", 221)

    observed = []
    while True:
        page = await client.get(
            "/api/admin/logs/runtime",
            params={"correlation_id": marker, "after": cursor, "page_size": 37},
        )
        assert page.status_code == 200
        body = page.json()
        assert len(body["items"]) <= 37
        observed.extend(row["id"] for row in body["items"])
        cursor = body["latest_cursor"] or cursor
        if not body["has_more"]:
            break
    assert len(observed) == len(set(observed)) == 221
    history = await runtime_identifiers(client, correlation_id=marker)
    assert set(history) == {anchor_id, *observed}
    empty = await client.get(
        "/api/admin/logs/runtime", params={"correlation_id": marker, "after": cursor}
    )
    assert empty.json()["items"] == []
    assert empty.json()["latest_cursor"] is None

    for keyword in ("%", "_", "\\"):
        response = await client.get(
            "/api/admin/logs/runtime", params={"correlation_id": marker, "q": keyword}
        )
        assert response.json()["items"] == []
    assert len(await runtime_identifiers(client, correlation_id=marker, q="X")) == 222
    assert (
        len(await runtime_identifiers(client, correlation_id=marker, start=instant, end=instant))
        == 222
    )


@pytest.mark.asyncio
async def test_four_real_writers_rotate_five_bounded_utf8_files_without_corruption(client):
    headers = await admin_session(client)
    enabled = await client.patch(
        "/api/admin/logs/settings", headers=headers, json={"file_enabled": True}
    )
    assert enabled.status_code == 200
    try:
        reports = await asyncio.gather(
            *(
                emit_logs("--module", f"rotation{index}", "--count", 4500, "--message-size", 4096)
                for index in range(4)
            )
        )
        assert all(report["emitted"] == 4500 and report["dropped"] == 0 for report in reports)
        paths = [RUN_FILES / f"runtime.log.{index}" for index in range(4, 0, -1)]
        paths.append(RUN_FILES / "runtime.log")
        assert {path.name for path in RUN_FILES.glob("runtime.log*")} == {
            path.name for path in paths
        }
        sequence = {f"rotation{index}": [] for index in range(4)}
        sizes = {}
        for path in paths:
            sizes[path.name] = path.stat().st_size
            assert sizes[path.name] <= 10485760
            for line in path.read_text(encoding="utf-8").splitlines():
                assert re.fullmatch(
                    r"\S+ (?:DEBUG|INFO|WARNING|ERROR): \[[A-Za-z0-9_.-]+\]"
                    r"\([A-Za-z0-9_.-]+\): .*",
                    line,
                )
                match = re.search(r"\[(rotation[0-3])\]\(diagnostic\): 运行日志诊断 (\d+) x+", line)
                if match:
                    sequence[match[1]].append(int(match[2]))
        for values in sequence.values():
            assert values
            assert values == list(range(values[0], 4501))
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        (EVIDENCE / "rotation-summary.json").write_text(
            json.dumps(
                {
                    "files": sizes,
                    "producer_ranges": {
                        module: {"first": values[0], "last": values[-1], "retained": len(values)}
                        for module, values in sequence.items()
                    },
                    "directory": str(RUN_FILES),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    finally:
        disabled = await client.patch(
            "/api/admin/logs/settings", headers=headers, json={"file_enabled": False}
        )
        assert disabled.status_code == 200


@pytest.mark.asyncio
async def test_real_file_path_failure_keeps_registration_and_online_logs_available(client):
    headers = await admin_session(client)
    blocked_path = EVIDENCE / f"blocked-directory-{uuid4().hex}"
    blocked_path.parent.mkdir(parents=True, exist_ok=True)
    blocked_path.write_text("此处是文件，不能创建日志目录", encoding="utf-8")
    enabled = await client.patch(
        "/api/admin/logs/settings", headers=headers, json={"file_enabled": True}
    )
    assert enabled.status_code == 200
    try:
        async with independent_api(blocked_path) as remote:
            suffix = uuid4().hex[:12]
            token = (await remote.get("/api/auth/csrf")).json()["csrf_token"]
            response = await remote.post(
                "/api/auth/register",
                headers={"X-CSRF-Token": token},
                json={
                    "student_no": f"LF{suffix}",
                    "real_name": "文件故障验收学生",
                    "email": f"log-fault-{suffix}@example.com",
                    "phone_number": "13800991236",
                    "password": "FileFailureSecret!123",
                },
            )
            assert response.status_code == 201
            await login_session(remote, f"LF{suffix}", "FileFailureSecret!123")
            await wait_for_runtime_request(client, response)
            for _ in range(50):
                errors = await client.get(
                    "/api/admin/logs/runtime",
                    params={"module": "logging", "task": "file_writer", "level": "ERROR"},
                )
                if errors.json()["items"]:
                    break
                await asyncio.sleep(0.1)
            assert errors.status_code == 200
            assert any(row["level"] == "ERROR" for row in errors.json()["items"])
            assert "FileFailureSecret!123" not in errors.text
            assert str(blocked_path) not in errors.text
    finally:
        disabled = await client.patch(
            "/api/admin/logs/settings", headers=headers, json={"file_enabled": False}
        )
        assert disabled.status_code == 200


@pytest.mark.asyncio
async def test_debug_lease_syncs_to_existing_api_and_expires_with_injected_clock(client):
    headers = await admin_session(client)
    clock_file = EVIDENCE / f"clock-offset-{uuid4().hex}.txt"
    clock_file.parent.mkdir(parents=True, exist_ok=True)
    clock_file.write_text("0", encoding="utf-8")
    try:
        async with independent_api(RUN_FILES, clock_file=clock_file) as remote:
            await admin_session(remote)
            started = asyncio.get_running_loop().time()
            enabled = await client.put(
                "/api/admin/logs/debug/auth", headers=headers, json={"enabled": True}
            )
            assert enabled.status_code == 200
            visible = False
            while asyncio.get_running_loop().time() - started < 1.5:
                diagnostic = await remote.get("/api/auth/csrf")
                await asyncio.sleep(0.1)
                observed = await client.get(
                    "/api/admin/logs/runtime",
                    params={
                        "correlation_id": diagnostic.headers["X-Request-ID"],
                        "level": "DEBUG",
                    },
                )
                if observed.json()["items"]:
                    visible = True
                    break
            assert visible
            synchronized_in = asyncio.get_running_loop().time() - started

            # 只对独立进程的应用时钟注入偏移；没有真实等待15分钟。
            clock_file.write_text("840", encoding="utf-8")
            before_expiry = await remote.get("/api/auth/csrf")
            await wait_for_runtime_request(client, before_expiry)
            clock_file.write_text("960", encoding="utf-8")
            settings = await remote.get("/api/admin/logs/settings")
            assert settings.status_code == 200
            assert all(entry["module"] != "auth" for entry in settings.json()["debug_modules"])
            after_expiry = await remote.get("/api/auth/csrf")
            await asyncio.sleep(0.4)
            observed = await client.get(
                "/api/admin/logs/runtime",
                params={"correlation_id": after_expiry.headers["X-Request-ID"], "level": "DEBUG"},
            )
            assert observed.json()["items"] == []
            (EVIDENCE / "debug-clock-summary.json").write_text(
                json.dumps(
                    {
                        "clock_injection": "独立API应用时钟，不代表真实等待15分钟",
                        "observed_sync_seconds_including_flush": round(synchronized_in, 3),
                        "minute_14_collected": True,
                        "minute_16_collected": False,
                        "expired_module_absent_from_settings": True,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
    finally:
        disabled = await client.put(
            "/api/admin/logs/debug/auth", headers=headers, json={"enabled": False}
        )
        assert disabled.status_code == 200


@pytest.mark.asyncio
async def test_real_runtime_insert_denial_does_not_rollback_registration_and_recovers(client):
    import asyncpg

    headers = await admin_session(client)
    disabled = await client.patch(
        "/api/admin/logs/settings", headers=headers, json={"file_enabled": False}
    )
    assert disabled.status_code == 200
    role = f"log_acceptance_{uuid4().hex}"
    password = uuid4().hex
    original_url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    parsed = urlsplit(os.environ["DATABASE_URL"])
    restricted_url = parsed._replace(
        netloc=f"{role}:{password}@{parsed.netloc.rsplit('@', 1)[-1]}"
    ).geturl()
    connection = await asyncpg.connect(original_url, command_timeout=10)
    created = False
    try:
        # SQL 仅用于准备专库外部权限故障，不查询数据库作为行为断言。
        await connection.execute(f"CREATE ROLE \"{role}\" LOGIN PASSWORD '{password}'")
        created = True
        await connection.execute(f'GRANT USAGE ON SCHEMA public TO "{role}"')
        await connection.execute(
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{role}"'
        )
        await connection.execute(
            f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{role}"'
        )
        await connection.execute(f'REVOKE INSERT ON TABLE runtime_log FROM "{role}"')
        async with independent_api(
            RUN_FILES, environment_override=PrivateEnvironment(DATABASE_URL=restricted_url)
        ) as remote:
            suffix = uuid4().hex[:12]
            token = (await remote.get("/api/auth/csrf")).json()["csrf_token"]
            remote_headers = {"X-CSRF-Token": token}
            response = await remote.post(
                "/api/auth/register",
                headers=remote_headers,
                json={
                    "student_no": f"LD{suffix}",
                    "real_name": "日志存储故障验收学生",
                    "email": f"log-db-{suffix}@example.com",
                    "phone_number": "13800991237",
                    "password": "DatabaseFailureSecret!123",
                },
            )
            assert response.status_code == 201
            await login_session(remote, f"LD{suffix}", "DatabaseFailureSecret!123")
            me = await remote.get("/api/auth/me")
            assert me.status_code == 200
            assert me.json()["user"]["id"] == response.json()["user"]["id"]
            await asyncio.sleep(0.4)
            missing = await client.get(
                "/api/admin/logs/runtime",
                params={"correlation_id": response.headers["X-Request-ID"], "level": "DEBUG"},
            )
            assert missing.json()["items"] == []

            await connection.execute(f'GRANT INSERT ON TABLE runtime_log TO "{role}"')
            recovered = await remote.post(
                "/api/auth/login",
                headers=remote_headers,
                json={"login_name": f"LD{suffix}", "password": "DatabaseFailureSecret!123"},
            )
            assert recovered.status_code == 200
            await wait_for_runtime_request(client, recovered)
            warnings = await client.get(
                "/api/admin/logs/runtime",
                params={"module": "logging", "task": "collector", "level": "WARNING"},
            )
            assert any(item["level"] == "WARNING" for item in warnings.json()["items"])
            assert "DatabaseFailureSecret!123" not in warnings.text
            assert password not in warnings.text
    finally:
        if created:
            await connection.execute(f'DROP OWNED BY "{role}"')
            await connection.execute(f'DROP ROLE "{role}"')
        await connection.close()
