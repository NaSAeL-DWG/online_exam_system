import uuid

import pytest

from app.config import get_settings


@pytest.mark.asyncio
async def test_student_can_register_and_waiting_account_can_login(client):
    suffix = uuid.uuid4().hex[:8]
    csrf_response = await client.get("/api/auth/csrf")
    assert csrf_response.status_code == 200
    csrf = csrf_response.json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}
    registration = await client.post(
        "/api/auth/register",
        headers=headers,
        json={
            "student_no": f"S{suffix}",
            "real_name": "测试学生",
            "email": f"student-{suffix}@example.com",
            "phone_number": "13800138000",
            "password": "ValidPassword!123",
        },
    )
    assert registration.status_code == 201
    assert registration.json()["user"]["status"] == "WAITING_ACTIVATE"
    assert "password_hash" not in registration.text

    login = await client.post(
        "/api/auth/login",
        headers=headers,
        json={"login_name": f"S{suffix}", "password": "ValidPassword!123"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["status"] == "WAITING_ACTIVATE"
    assert client.cookies.get("access_token")
    assert client.cookies.get("refresh_token")


@pytest.mark.asyncio
async def test_duplicate_registration_returns_stable_conflict(client):
    suffix = uuid.uuid4().hex[:8]
    csrf = (await client.get("/api/auth/csrf")).json()["csrf_token"]
    payload = {
        "student_no": f"D{suffix}",
        "real_name": "重复账号",
        "email": f"duplicate-{suffix}@example.com",
        "phone_number": "13800138001",
        "password": "ValidPassword!123",
    }
    first = await client.post("/api/auth/register", headers={"X-CSRF-Token": csrf}, json=payload)
    assert first.status_code == 201
    duplicate = await client.post(
        "/api/auth/register", headers={"X-CSRF-Token": csrf}, json=payload
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "LOGIN_NAME_EXISTS"


@pytest.mark.asyncio
async def test_write_requests_require_csrf_and_verification_is_disabled(client):
    missing_csrf = await client.post(
        "/api/auth/register",
        json={
            "student_no": f"C{uuid.uuid4().hex[:8]}",
            "real_name": "校验学生",
            "email": "csrf@example.com",
            "phone_number": "13800138002",
            "password": "ValidPassword!123",
        },
    )
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["detail"]["code"] == "CSRF_INVALID"
    csrf = (await client.get("/api/auth/csrf")).json()["csrf_token"]
    for channel in ("email", "phone"):
        verification = await client.post(
            f"/api/auth/verification/{channel}", headers={"X-CSRF-Token": csrf}
        )
        assert verification.status_code == 501
        assert verification.json() == {
            "detail": {"code": "VERIFICATION_NOT_ENABLED", "message": "验证功能尚未启用"}
        }


@pytest.mark.asyncio
async def test_refresh_rotates_credential_and_old_value_cannot_be_reused(client):
    suffix = uuid.uuid4().hex[:8]
    csrf = (await client.get("/api/auth/csrf")).json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}
    await client.post(
        "/api/auth/register",
        headers=headers,
        json={
            "student_no": f"R{suffix}",
            "real_name": "刷新学生",
            "email": f"refresh-{suffix}@example.com",
            "phone_number": "13800138003",
            "password": "ValidPassword!123",
        },
    )
    await client.post(
        "/api/auth/login",
        headers=headers,
        json={"login_name": f"R{suffix}", "password": "ValidPassword!123"},
    )
    old_refresh = client.cookies.get("refresh_token")
    refreshed = await client.post("/api/auth/refresh", headers=headers)
    assert refreshed.status_code == 200
    assert client.cookies.get("refresh_token") != old_refresh

    client.cookies.set("refresh_token", old_refresh)
    reuse = await client.post("/api/auth/refresh", headers=headers)
    assert reuse.status_code == 401
    assert reuse.json()["detail"]["code"] == "SESSION_INVALID"


@pytest.mark.asyncio
async def test_waiting_student_is_limited_to_application_flow(client):
    suffix = uuid.uuid4().hex[:8]
    csrf = (await client.get("/api/auth/csrf")).json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}
    registered = await client.post(
        "/api/auth/register",
        headers=headers,
        json={
            "student_no": f"W{suffix}",
            "real_name": "待审学生",
            "email": f"waiting-{suffix}@example.com",
            "phone_number": "13800138004",
            "password": "ValidPassword!123",
        },
    )
    await client.post(
        "/api/auth/login",
        headers=headers,
        json={"login_name": f"W{suffix}", "password": "ValidPassword!123"},
    )
    application = await client.get("/api/student/application")
    assert application.status_code == 200
    assert application.json()["application"]["id"] == registered.json()["application"]["id"]
    classes = await client.get("/api/classes")
    assert classes.status_code == 403
    assert classes.json()["detail"]["code"] == "ACCOUNT_NOT_ACTIVE"


@pytest.mark.asyncio
async def test_current_password_verification_is_rate_limited(client):
    settings = get_settings()
    csrf = (await client.get("/api/auth/csrf")).json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}
    login = await client.post(
        "/api/auth/login",
        headers=headers,
        json={"login_name": settings.admin_login_name, "password": settings.admin_password},
    )
    assert login.status_code == 200
    responses = []
    for index in range(6):
        responses.append(
            await client.put(
                "/api/auth/contacts",
                headers=headers,
                json={
                    "current_password": f"WrongPassword!{index}",
                    "email": "rate-limit@example.com",
                    "phone_number": "13800138011",
                },
            )
        )
    assert [response.status_code for response in responses[:5]] == [400] * 5
    assert responses[5].status_code == 429
    assert responses[5].json()["detail"]["code"] == "PASSWORD_VERIFY_RATE_LIMITED"
