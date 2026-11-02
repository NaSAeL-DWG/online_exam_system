import asyncio
import os
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from test_classes_api import admin_login


@pytest.mark.asyncio
async def test_admin_can_read_default_settings_and_empty_runtime_without_cache(client):
    denied = await client.get("/api/admin/logs/settings")
    assert denied.status_code == 401
    await admin_login(client)
    response = await client.get("/api/admin/logs/settings")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["file_enabled"] is False
    assert response.json()["runtime_limit"] == 20000
    logs = await client.get("/api/admin/logs/runtime")
    assert logs.status_code == 200
    assert set(logs.json()) == {"items", "next_before", "latest_cursor", "has_more"}


@pytest.mark.asyncio
async def test_file_debug_settings_and_export_are_csrf_protected_and_audited(client):
    headers = await admin_login(client)
    denied = await client.patch("/api/admin/logs/settings", json={"file_enabled": True})
    assert denied.status_code == 403
    assert denied.headers["cache-control"] == "no-store"
    enabled = await client.patch(
        "/api/admin/logs/settings", headers=headers, json={"file_enabled": True}
    )
    assert enabled.status_code == 200
    assert enabled.json()["retention_days"] == 7
    debug = await client.put("/api/admin/logs/debug/auth", headers=headers, json={"enabled": True})
    assert debug.status_code == 200
    assert debug.json()["debug_modules"][0]["module"] == "auth"
    audit = await client.get("/api/admin/logs/audit", params={"action": "LOG_FILE_SETTINGS"})
    assert audit.status_code == 200
    assert audit.json()["items"][0]["summary"]
    assert "before_data" not in audit.text and "after_data" not in audit.text
    download = await client.post(
        "/api/admin/logs/audit/export", headers=headers, params={"action": "LOG_FILE_SETTINGS"}
    )
    assert download.status_code == 200
    assert "attachment" in download.headers["content-disposition"]
    assert "LOG_FILE_SETTINGS" in download.text
    await client.put("/api/admin/logs/debug/auth", headers=headers, json={"enabled": False})
    await client.patch("/api/admin/logs/settings", headers=headers, json={"file_enabled": False})


@pytest.mark.asyncio
async def test_cli_standard_logging_persists_and_incremental_pages_do_not_skip_backlog(client):
    await admin_login(client)
    marker = uuid.uuid4().hex
    result = await asyncio.to_thread(
        subprocess.run,
        [
            sys.executable,
            "-m",
            "app.cli",
            "logging-check",
            "--module",
            "auth",
            "--correlation-id",
            marker,
            "--count",
            "205",
        ],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, result.stderr
    first = await client.get(
        "/api/admin/logs/runtime", params={"correlation_id": marker, "page_size": 1}
    )
    assert first.status_code == 200
    oldest = first.json()["items"][0]
    # 从历史页定位最旧游标，再分三批增量追回204条，不允许跨过中间积压。
    history = await client.get(
        "/api/admin/logs/runtime",
        params={"correlation_id": marker, "before": oldest["cursor"], "page_size": 100},
    )
    history = await client.get(
        "/api/admin/logs/runtime",
        params={
            "correlation_id": marker,
            "before": history.json()["next_before"],
            "page_size": 100,
        },
    )
    history = await client.get(
        "/api/admin/logs/runtime",
        params={
            "correlation_id": marker,
            "before": history.json()["next_before"],
            "page_size": 100,
        },
    )
    cursor = history.json()["next_before"]
    seen = set()
    for expected_count in (100, 100, 4):
        update = (
            await client.get(
                "/api/admin/logs/runtime",
                params={"correlation_id": marker, "after": cursor, "page_size": 100},
            )
        ).json()
        assert len(update["items"]) == expected_count
        seen.update(item["id"] for item in update["items"])
        cursor = update["latest_cursor"]
    assert len(seen) == 204
    assert oldest["id"] in seen


@pytest.mark.asyncio
async def test_audit_incremental_query_includes_transaction_that_commits_late(client):
    """在真实 PostgreSQL 边界暂缓提交；最终断言仅通过公开 HTTP 观察审计。"""
    headers = await admin_login(client)
    marker = "late_" + uuid.uuid4().hex
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    key = 78431903
    registration = None
    async with engine.connect() as connection:
        await connection.execute(
            text(f"""
            CREATE FUNCTION logging_test_delay() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.action = 'REGISTRATION_SUBMITTED' AND NEW.after_data->>'student_no' = '{marker}' THEN
                    PERFORM pg_advisory_xact_lock({key});
                END IF;
                RETURN NEW;
            END $$
        """)
        )
        await connection.execute(
            text(
                "CREATE TRIGGER logging_test_delay BEFORE INSERT ON audit_event FOR EACH ROW EXECUTE FUNCTION logging_test_delay()"
            )
        )
        await connection.commit()
        await connection.execute(text(f"SELECT pg_advisory_lock({key})"))
        try:
            registration = asyncio.create_task(
                client.post(
                    "/api/auth/register",
                    headers=headers,
                    json={
                        "student_no": marker,
                        "real_name": "延迟提交学生",
                        "email": f"{marker}@example.com",
                        "phone_number": "13800138000",
                        "password": "StudentPassword!123",
                    },
                )
            )
            for _ in range(100):
                blocked = await connection.scalar(
                    text(
                        f"SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND NOT granted AND objid={key}"
                    )
                )
                if blocked:
                    break
                await asyncio.sleep(0.02)
            assert blocked, "测试注册未到达数据库同步屏障"
            created = await client.put(
                "/api/admin/logs/debug/late_marker", headers=headers, json={"enabled": False}
            )
            assert created.status_code == 200
            cursor = (await client.get("/api/admin/logs/audit")).json()["latest_cursor"]
            await connection.execute(text(f"SELECT pg_advisory_unlock({key})"))
            registered = await registration
            assert registered.status_code == 201
            after = await client.get(
                "/api/admin/logs/audit",
                params={"after": cursor, "action": "REGISTRATION_SUBMITTED"},
            )
            assert registered.json()["application"]["id"] in {
                entry["entity_id"] for entry in after.json()["items"]
            }
        finally:
            await connection.execute(text(f"SELECT pg_advisory_unlock({key})"))
            if registration:
                await registration
            await connection.execute(text("DROP TRIGGER logging_test_delay ON audit_event"))
            await connection.execute(text("DROP FUNCTION logging_test_delay()"))
            await connection.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_blocked_log_writer_does_not_hold_business_transaction(client):
    """外部数据库锁阻塞日志写入，业务仍可提交；解除后通过HTTP读到积压记录。"""
    headers = await admin_login(client)
    marker = "independent_" + uuid.uuid4().hex
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    async with engine.connect() as connection:
        await connection.execute(text("SELECT id FROM log_settings WHERE id=1 FOR UPDATE"))
        try:
            async with asyncio.timeout(3):
                response = await client.post(
                    "/api/auth/register",
                    headers=headers,
                    json={
                        "student_no": marker,
                        "real_name": "独立事务学生",
                        "email": f"{marker}@example.com",
                        "phone_number": "13800138000",
                        "password": "StudentPassword!123",
                    },
                )
                assert response.status_code == 201
                users = await client.get("/api/admin/users", params={"q": marker})
                assert users.status_code == 200
                assert users.json()["total"] == 1
            correlation_id = response.headers["x-request-id"]
            await asyncio.sleep(0.2)
            waiting = await client.get(
                "/api/admin/logs/runtime", params={"correlation_id": correlation_id}
            )
            assert waiting.json()["items"] == []
        finally:
            await connection.rollback()
        for _ in range(100):
            visible = await client.get(
                "/api/admin/logs/runtime", params={"correlation_id": correlation_id}
            )
            if visible.json()["items"]:
                break
            await asyncio.sleep(0.02)
        assert visible.json()["items"][0]["task"] == "register"
    await engine.dispose()
