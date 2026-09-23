import asyncio
import inspect

import pytest
from fastapi import Cookie, Depends, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

from app.deps import current_identity, get_session
from test_identity_admin_api import login_admin
from test_session_security_api import cookie_values, register_and_login


@pytest.mark.asyncio
async def test_database_failure_before_refresh_keeps_original_credential_retryable(client):
    headers = await register_and_login(client, "DBF")
    old_refresh = client.cookies.get("refresh_token")
    application = client._transport.app
    client._transport.raise_app_exceptions = False

    def fail_user_read(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT") and "user_account" in statement:
            raise OperationalError(None, None, RuntimeError("测试数据库暂时不可用"))

    engine = application.state.resources.engine.sync_engine
    event.listen(engine, "before_cursor_execute", fail_user_read)
    try:
        unavailable = await client.post("/api/auth/refresh", headers=headers)
    finally:
        event.remove(engine, "before_cursor_execute", fail_user_read)
    assert unavailable.status_code in (500, 503)
    assert client.cookies.get("refresh_token") == old_refresh
    retried = await client.post("/api/auth/refresh", headers=headers)
    assert retried.status_code == 200
    assert client.cookies.get("refresh_token") != old_refresh


@pytest.mark.asyncio
@pytest.mark.parametrize("administrative_action", ["reset", "deactivate"])
async def test_stale_authenticated_password_write_cannot_override_admin_change(
    client, administrative_action
):
    headers = await register_and_login(client, "LOCK")
    user = (await client.get("/api/auth/me")).json()["user"]
    application = client._transport.app
    identity_read = asyncio.Event()
    resume_write = asyncio.Event()

    async def controlled_identity(
        request: Request,
        access_token: str | None = Cookie(default=None),
        session=Depends(get_session),
    ):
        arguments = {"request": request, "access_token": access_token}
        # 同一公共依赖插桩同时适配整改前后签名；不伪造身份或锁结果。
        if "session" in inspect.signature(current_identity).parameters:
            arguments["session"] = session
        result = await current_identity(**arguments)
        if request.url.path == "/api/auth/password":
            identity_read.set()
            await asyncio.wait_for(resume_write.wait(), 10)
        return result

    application.dependency_overrides[current_identity] = controlled_identity
    old_write = asyncio.create_task(
        client.put(
            "/api/auth/password",
            headers=headers,
            json={
                "current_password": "ValidPassword!123",
                "new_password": "StaleWriterPassword!123",
            },
        )
    )
    try:
        await asyncio.wait_for(identity_read.wait(), 10)
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://testserver"
        ) as admin:
            admin_headers = await login_admin(admin)
            if administrative_action == "reset":
                changed = await admin.post(
                    f"/api/admin/users/{user['id']}/reset-password",
                    headers=admin_headers,
                    json={"temporary_password": "AdminResetPassword!123"},
                )
                assert changed.status_code == 204
            else:
                changed = await admin.patch(
                    f"/api/admin/users/{user['id']}",
                    headers=admin_headers,
                    json={"status": "DEACTIVATED"},
                )
                assert changed.status_code == 200
        resume_write.set()
        rejected = await asyncio.wait_for(old_write, 10)
        assert rejected.status_code in (401, 403)
        assert rejected.json()["detail"]["code"] in ("SESSION_INVALID", "ACCOUNT_DEACTIVATED")
    finally:
        resume_write.set()
        application.dependency_overrides.clear()
        if not old_write.done():
            await old_write
    # 从公开登录入口验证新状态没有被旧请求覆盖。
    check = await client.post(
        "/api/auth/login",
        headers=headers,
        json={
            "login_name": user["login_name"],
            "password": "AdminResetPassword!123"
            if administrative_action == "reset"
            else "ValidPassword!123",
        },
    )
    assert check.status_code == (200 if administrative_action == "reset" else 403)


@pytest.mark.asyncio
async def test_lost_refresh_response_requires_login_after_original_token_replay(client):
    headers = await register_and_login(client, "LOST")
    original = cookie_values(client)
    application = client._transport.app
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as other:
        other.cookies.update(original)
        delivered_elsewhere = await other.post("/api/auth/refresh", headers=headers)
        assert delivered_elsewhere.status_code == 200
    # 模拟响应未交付：原客户端保留旧 Cookie，而服务端已完成最终 CAS。
    replay = await client.post("/api/auth/refresh", headers=headers)
    assert replay.status_code == 401
    assert replay.json()["detail"]["code"] == "SESSION_INVALID"
    assert (await client.get("/api/auth/me")).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["reset", "deactivate"])
async def test_refresh_rechecks_database_after_concurrent_admin_commit(client, monkeypatch, action):
    headers = await register_and_login(client, "RFC")
    user = (await client.get("/api/auth/me")).json()["user"]
    application = client._transport.app
    redis = application.state.resources.redis
    original_read = redis.hgetall
    session_read = asyncio.Event()
    resume = asyncio.Event()

    async def gated_read(*args, **kwargs):
        values = await original_read(*args, **kwargs)
        session_read.set()
        await asyncio.wait_for(resume.wait(), 10)
        return values

    monkeypatch.setattr(redis, "hgetall", gated_read)
    refreshing = asyncio.create_task(client.post("/api/auth/refresh", headers=headers))
    try:
        await asyncio.wait_for(session_read.wait(), 10)
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://testserver"
        ) as admin:
            admin_headers = await login_admin(admin)
            if action == "reset":
                changed = await admin.post(
                    f"/api/admin/users/{user['id']}/reset-password",
                    headers=admin_headers,
                    json={"temporary_password": "RefreshResetPassword!123"},
                )
                assert changed.status_code == 204
            else:
                changed = await admin.patch(
                    f"/api/admin/users/{user['id']}",
                    headers=admin_headers,
                    json={"status": "DEACTIVATED"},
                )
                assert changed.status_code == 200
        resume.set()
        response = await asyncio.wait_for(refreshing, 10)
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "SESSION_INVALID"
    finally:
        resume.set()
        if not refreshing.done():
            await refreshing
