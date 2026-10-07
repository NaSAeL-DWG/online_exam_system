import logging
from uuid import UUID

from arq import Retry

from app.workers.recovery import recover_grading


logger = logging.getLogger(__name__)


async def grade_attempt_job(ctx: dict, attempt_id: str, grading_revision: int) -> bool:
    """复用公开判分用例，重复、旧修订和 VOID 任务由数据库状态拒绝。"""

    from app.modules.grading import service

    try:
        async with ctx["resources"].session_factory() as session:
            return await service.grade_attempt(session, UUID(attempt_id), grading_revision)
    except Exception as exc:
        logger.warning("判分任务待重试 attempt_id=%s error=%s", attempt_id, type(exc).__name__)
        raise Retry(defer=5) from None


async def scan_grading_job(ctx: dict) -> dict:
    """数据库扫描补偿入队失败、队列丢失与 worker 停机期间的评分工作。"""

    try:
        result = await recover_grading(
            ctx["resources"], limit=ctx["settings"].attempt_scan_batch_size
        )
    except Exception as exc:
        logger.warning("判分扫描待重试 error=%s", type(exc).__name__)
        raise Retry(defer=5) from None
    return result.to_dict()
