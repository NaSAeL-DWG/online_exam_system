import json
import logging
from datetime import timezone
from uuid import UUID

from arq import Retry, cron

from app.core.attempt_queue import queue_redis_settings
from app.core.config import get_settings
from app.core.database import Resources
from app.modules.attempt import service
from app.workers.recovery import recover_due_attempts
from app.workers.grading import grade_attempt_job, scan_grading_job


logger = logging.getLogger(__name__)


async def timeout_attempt_job(ctx: dict, attempt_id: str) -> bool:
    """定时及重复任务使用与 HTTP 相同的事务和 VOID 状态检查。"""

    try:
        async with ctx["resources"].session_factory() as session:
            return await service.timeout_attempt(session, UUID(attempt_id))
    except Exception as exc:
        logger.warning("截止任务待重试 attempt_id=%s error=%s", attempt_id, type(exc).__name__)
        raise Retry(defer=5) from None


async def scan_due_attempts_job(ctx: dict) -> dict:
    """周期扫描持久状态，补偿入队失败、队列丢失及 worker 停机窗口。"""

    try:
        result = await recover_due_attempts(
            ctx["resources"], limit=ctx["settings"].attempt_scan_batch_size
        )
    except Exception as exc:
        logger.warning("到期扫描待重试 error=%s", type(exc).__name__)
        raise Retry(defer=5) from None
    return result.to_dict()


async def startup(ctx: dict) -> None:
    """启动即扫描数据库；不等待下一轮 cron，也不重放学生请求。"""

    settings = get_settings()
    ctx["settings"] = settings
    ctx["resources"] = Resources(settings)
    result = await scan_due_attempts_job(ctx)
    ctx["startup_recovery"] = result
    logger.info("启动到期恢复 %s", json.dumps(result, ensure_ascii=False))
    grading_result = await scan_grading_job(ctx)
    ctx["startup_grading_recovery"] = grading_result
    logger.info("启动判分恢复 %s", json.dumps(grading_result, ensure_ascii=False))


async def shutdown(ctx: dict) -> None:
    """worker 独立关闭自己的连接，不共享 API 进程资源。"""

    await ctx["resources"].close()


class WorkerSettings:
    """ARQ 公开装配入口：截止／判分任务加每 30 秒持久数据库补偿。"""

    settings = get_settings()
    functions = [timeout_attempt_job, scan_due_attempts_job, grade_attempt_job, scan_grading_job]
    cron_jobs = [
        cron(scan_due_attempts_job, second={0, 30}, keep_result=60, max_tries=3),
        cron(scan_grading_job, second={0, 30}, keep_result=60, max_tries=3),
    ]
    redis_settings = queue_redis_settings(settings)
    queue_name = settings.arq_queue_name
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    max_tries = 3
    job_timeout = 60
    keep_result = 60
    timezone = timezone.utc
    log_results = False
