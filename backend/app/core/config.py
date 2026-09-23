from functools import lru_cache

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置，敏感值只从环境或本地 .env 读取。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"]
    database_url: str
    redis_url: str
    jwt_secret: str = Field(min_length=32)
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    access_minutes: int = 10
    session_idle_seconds: int = 2 * 60 * 60
    session_absolute_seconds: int = 12 * 60 * 60
    password_min_length: int = 10
    cors_origins: str = "http://localhost:5173"
    admin_login_name: str | None = None
    admin_password: str | None = Field(default=None, min_length=10, max_length=256)
    admin_real_name: str | None = None
    admin_email: str | None = None
    admin_phone_number: str | None = None

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.environment == "production" and not self.cookie_secure:
            raise ValueError("生产环境必须启用 Secure Cookie")
        return self


@lru_cache
def get_settings() -> Settings:
    """返回进程级配置快照。"""

    return Settings()
