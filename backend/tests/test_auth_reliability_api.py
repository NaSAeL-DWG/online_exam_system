import json
import subprocess
import sys
from pathlib import Path

import pytest
from redis.exceptions import ConnectionError
from sqlalchemy import event
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from httpx import ASGITransport, AsyncClient

from app.modules.auth.models import SessionCleanup
from app.modules.identity.models import AuditEvent
from test_identity_admin_api import login_admin

from test_session_security_api import register_and_login


@pytest.mark.asyncio
async def test_password_commit_succeeds_when_redis_cleanup_fails(client, monkeypatch):
    headers = await register_and_login(client, "OUT")
    application = client._transport.app
    original_eval = application.state.resources.redis.eval
    old_refresh = client.cookies.get("refresh_token")
    login_name = (await client.get("/api/auth/me")).json()["user"]["login_name"]
    committed = False

    def after_commit(_):
        nonlocal committed
        committed = True

    async def unavailable_after_commit(*args, **kwargs):
        if committed:
            raise ConnectionError("测试注入：提交后 Redis 清理不可用")
        return await original_eval(*args, **kwargs)

    event.listen(Session, "after_commit", after_commit)
    monkeypatch.setattr(application.state.resources.redis, "eval", unavailable_after_commit)
    try:
        changed = await client.put(
            "/api/auth/password",
            headers=headers,
            json={
                "current_password": "ValidPassword!123",
                "new_password": "ChangedPassword!123",
            },
        )
    finally:
        event.remove(Session, "after_commit", after_commit)
        monkeypatch.setattr(application.state.resources.redis, "eval", original_eval)
    assert changed.status_code == 204
    assert changed.headers["X-Session-Cleanup"] == "pending"
    old_session = await client.get("/api/auth/me")
    assert old_session.status_code == 401
    # 清理尚未发生时旧 Redis 行仍存在，拒绝访问由数据库版本保证。
    old_sid = old_refresh.split(".")[0]
    assert await application.state.resources.redis.exists(f"session:{old_sid}") == 1
    login = await client.post(
        "/api/auth/login",
        headers=headers,
        json={
            "login_name": login_name,
            "password": "ChangedPassword!123",
        },
    )
    assert login.status_code == 200
    new_refresh = client.cookies.get("refresh_token")
    completed = subprocess.run(
        [sys.executable, "-m", "app.cli", "retry-session-cleanups"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["completed"] >= 1
    assert await application.state.resources.redis.exists(f"session:{old_sid}") == 0
    assert (await client.get("/api/auth/me")).status_code == 200
    assert client.cookies.get("refresh_token") == new_refresh


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["contacts", "reset", "deactivate"])
async def test_committed_changes_have_durable_retry_without_duplicate_audit(
    client, monkeypatch, operation
):
    from uuid import UUID

    headers = await register_and_login(client, "DUR")
    user = (await client.get("/api/auth/me")).json()["user"]
    user_id = UUID(user["id"])
    application = client._transport.app
    resources = application.state.resources
    redis = resources.redis
    action = {
        "contacts": "CONTACTS_CHANGED",
        "reset": "PASSWORD_RESET",
        "deactivate": "USER_UPDATED",
    }[operation]

    async def audit_count():
        async with resources.session_factory() as session:
            return await session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.entity_id == user_id, AuditEvent.action == action)
            )

    before = await audit_count()
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as admin:
        admin_headers = await login_admin(admin)
        committed = False
        original_command = redis.execute_command

        def after_commit(_):
            nonlocal committed
            committed = True

        async def unavailable_after_commit(*args, **kwargs):
            if committed:
                raise ConnectionError("测试注入：提交后的缓存清理失败")
            return await original_command(*args, **kwargs)

        event.listen(Session, "after_commit", after_commit)
        monkeypatch.setattr(redis, "execute_command", unavailable_after_commit)
        try:
            if operation == "contacts":
                response = await client.put(
                    "/api/auth/contacts",
                    headers=headers,
                    json={
                        "current_password": "ValidPassword!123",
                        "email": "committed@example.com",
                        "phone_number": "13800138099",
                    },
                )
            elif operation == "reset":
                response = await admin.post(
                    f"/api/admin/users/{user_id}/reset-password",
                    headers=admin_headers,
                    json={"temporary_password": "CommittedReset!123"},
                )
            else:
                response = await admin.patch(
                    f"/api/admin/users/{user_id}",
                    headers=admin_headers,
                    json={"status": "DEACTIVATED"},
                )
        finally:
            event.remove(Session, "after_commit", after_commit)
            monkeypatch.setattr(redis, "execute_command", original_command)
    assert response.status_code == (204 if operation == "reset" else 200)
    assert response.headers["X-Session-Cleanup"] == "pending"
    assert await audit_count() == before + 1
    async with resources.session_factory() as session:
        task = await session.scalar(select(SessionCleanup).where(SessionCleanup.user_id == user_id))
        assert task.attempts == 1
        assert task.last_error == "ConnectionError"
        assert task.completed_at is None
    if operation == "contacts":
        current = await client.get("/api/auth/me")
        assert current.status_code == 200
        assert current.json()["user"]["email"] == "committed@example.com"
    else:
        assert (await client.get("/api/auth/me")).status_code == 401
    for _ in range(2):
        retry = subprocess.run(
            [sys.executable, "-m", "app.cli", "retry-session-cleanups"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert retry.returncode == 0, retry.stderr
        assert json.loads(retry.stdout)["pending"] == 0
    assert await audit_count() == before + 1
    async with resources.session_factory() as session:
        task = await session.scalar(select(SessionCleanup).where(SessionCleanup.user_id == user_id))
        assert task.attempts == 2
        assert task.last_error is None
        assert task.completed_at is not None
