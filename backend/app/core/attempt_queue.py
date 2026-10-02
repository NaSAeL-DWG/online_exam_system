import asyncio
from datetime import datetime
from uuid import UUID

from arq.connections import ArqRedis, RedisSettings

from app.core.config import Settings, get_settings


def queue_redis_settings(settings: Settings) -> RedisSettings:
    """独立 worker 与 API 使用同一队列地址，默认复用认证 Redis。"""

    return RedisSettings.from_dsn(settings.arq_redis_url or settings.redis_url)


async def enqueue_attempt_timeout(
    attempt_id: UUID,
    deadline_at: datetime,
    *,
    settings: Settings | None = None,
) -> None:
    """在业务提交后投递截止任务；异常由业务用例按已提交语义处理。"""

    settings = settings or get_settings()
    redis = ArqRedis.from_url(
        settings.arq_redis_url or settings.redis_url,
        socket_connect_timeout=settings.arq_enqueue_timeout_seconds,
        socket_timeout=settings.arq_enqueue_timeout_seconds,
    )
    redis.default_queue_name = settings.arq_queue_name
    try:
        # 队列只加速收尾；固定任务 ID 防止恢复已有作答时重复投递。
        async with asyncio.timeout(settings.arq_enqueue_timeout_seconds):
            await redis.enqueue_job(
                "timeout_attempt_job",
                str(attempt_id),
                _job_id=f"attempt-timeout:{attempt_id}",
                _defer_until=deadline_at,
            )
    finally:
        await redis.aclose()
