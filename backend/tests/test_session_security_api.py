import asyncio
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings


async def register_and_login(client, prefix: str = "K"):
    suffix = uuid.uuid4().hex[:8]
    login_name = f"{prefix}{suffix}"
    password = "ValidPassword!123"
    csrf = (await client.get("/api/auth/csrf")).json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}
    registration = await client.post(
        "/api/auth/register",
        headers=headers,
        json={
            "student_no": login_name,
            "real_name": "会话学生",
            "email": f"session-{suffix}@example.com",
            "phone_number": "13800138040",
            "password": password,
        },
    )
    assert registration.status_code == 201
    login = await client.post(
        "/api/auth/login",
        headers=headers,
        json={"login_name": login_name, "password": password},
    )
    assert login.status_code == 200
    return headers


def cookie_values(client):
    return {cookie.name: cookie.value for cookie in client.cookies.jar}


def make_settings(**overrides):
    values = {
        "environment": "test",
        "database_url": os.environ["TEST_DATABASE_URL"],
        "redis_url": os.environ["TEST_REDIS_URL"],
        "jwt_secret": "test-secret-must-be-at-least-32-bytes-long",
        "cookie_secure": False,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.asyncio
async def test_concurrent_refresh_allows_only_one_rotation(client):
    headers = await register_and_login(client, "F")
    cookies = cookie_values(client)
    application = client._transport.app
    async with (
        AsyncClient(
            transport=ASGITransport(app=application), base_url="http://testserver"
        ) as first,
        AsyncClient(
            transport=ASGITransport(app=application), base_url="http://testserver"
        ) as second,
    ):
        first.cookies.update(cookies)
        second.cookies.update(cookies)
        results = await asyncio.gather(
            first.post("/api/auth/refresh", headers=headers),
            second.post("/api/auth/refresh", headers=headers),
        )
    assert sorted(response.status_code for response in results) == [200, 401]
    failed = next(response for response in results if response.status_code == 401)
    assert failed.json()["detail"]["code"] == "SESSION_INVALID"


@pytest.mark.asyncio
async def test_authentication_fails_closed_when_redis_is_unavailable(client):
    from app.main import create_app

    await register_and_login(client, "E")
    cookies = cookie_values(client)
    unavailable = create_app(make_settings(redis_url="redis://127.0.0.1:1/15"))
    async with unavailable.router.lifespan_context(unavailable):
        async with AsyncClient(
            transport=ASGITransport(app=unavailable), base_url="http://testserver"
        ) as unavailable_client:
            unavailable_client.cookies.update(cookies)
            response = await unavailable_client.get("/api/auth/me")
    assert response.status_code == 503, response.text
    assert response.json()["detail"]["code"] == "AUTH_SERVICE_UNAVAILABLE"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("idle_seconds", "absolute_seconds", "prefix"), [(1, 10, "I"), (10, 1, "B")]
)
async def test_session_honors_idle_and_absolute_expiry(idle_seconds, absolute_seconds, prefix):
    from app.main import create_app

    application = create_app(
        make_settings(
            session_idle_seconds=idle_seconds,
            session_absolute_seconds=absolute_seconds,
        )
    )
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://testserver"
        ) as client:
            await register_and_login(client, prefix)
            await asyncio.sleep(1.2)
            response = await client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "SESSION_INVALID"
