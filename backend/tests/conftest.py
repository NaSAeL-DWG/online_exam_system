import os
import subprocess
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session")
def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.fail("集成测试要求 TEST_DATABASE_URL 指向真实 PostgreSQL")
    return value


@pytest.fixture(scope="session")
def redis_url() -> str:
    value = os.getenv("TEST_REDIS_URL")
    if not value:
        pytest.fail("集成测试要求 TEST_REDIS_URL 指向真实 Redis")
    return value


@pytest.fixture(scope="session", autouse=True)
def prepare_integration_environment(database_url: str, redis_url: str):
    """仅使用两个测试连接变量准备迁移与固定测试管理员。"""

    environment = os.environ.copy()
    environment.update(
        {
            "ENVIRONMENT": "test",
            "DATABASE_URL": database_url,
            "REDIS_URL": redis_url,
            "JWT_SECRET": "test-secret-must-be-at-least-32-bytes-long",
            "COOKIE_SECURE": "false",
            "ADMIN_LOGIN_NAME": "integration-admin",
            "ADMIN_PASSWORD": "IntegrationAdmin!123",
            "ADMIN_REAL_NAME": "集成测试管理员",
            "ADMIN_EMAIL": "integration-admin@example.com",
            "ADMIN_PHONE_NUMBER": "13800000000",
        }
    )
    os.environ.update(environment)
    backend_dir = Path(__file__).resolve().parents[1]
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=environment,
        check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "app.cli", "prepare-test-admin"],
        cwd=backend_dir,
        env=environment,
        check=True,
    )


@pytest.fixture
async def client(database_url: str, redis_url: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("REDIS_URL", redis_url)
    monkeypatch.setenv("JWT_SECRET", "test-secret-must-be-at-least-32-bytes-long")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    from app.main import create_app

    application = create_app()
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://testserver"
        ) as http_client:
            yield http_client
