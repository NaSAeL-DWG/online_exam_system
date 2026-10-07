import asyncio
from uuid import UUID

from arq.connections import ArqRedis

from app.core.config import Settings, get_settings


async def enqueue_attempt_grading(
    attempt_id: UUID,
    grading_revision: int,
    *,
    settings: Settings | None = None,
) -> None:
    """业务提交后投递目标修订的判分任务，失败由持久扫描补偿。"""

    settings = settings or get_settings()
    redis = ArqRedis.from_url(
        settings.arq_redis_url or settings.redis_url,
        socket_connect_timeout=settings.arq_enqueue_timeout_seconds,
        socket_timeout=settings.arq_enqueue_timeout_seconds,
    )
    redis.default_queue_name = settings.arq_queue_name
    try:
        # 旧修订任务允许迟到，由业务用例重新核对目标修订和有效状态。
        async with asyncio.timeout(settings.arq_enqueue_timeout_seconds):
            await redis.enqueue_job(
                "grade_attempt_job",
                str(attempt_id),
                grading_revision,
                _job_id=f"attempt-grade:{attempt_id}:{grading_revision}",
            )
    finally:
        await redis.aclose()
