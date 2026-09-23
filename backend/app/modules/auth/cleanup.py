import logging

from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from app.core.clock import utc_now
from . import crud, session_store

logger = logging.getLogger(__name__)


def schedule(session, user_id, *, revoke_before_version=None, clear_password_rate=False):
    """可组合操作：仅入持久任务，事务归调用方所有。"""
    return crud.add_cleanup(session, user_id, revoke_before_version, clear_password_rate)


async def deliver(session_factory, redis, task_id):
    """业务提交后尽力清理；失败任务保留供 CLI 重试，绝不重写业务审计。"""
    try:
        async with session_factory() as session:
            async with session.begin():
                task = await crud.lock_cleanup(session, task_id)
                if task is None or task.completed_at is not None:
                    return True
                task.attempts += 1
                task.last_attempt_at = utc_now()
                try:
                    if task.revoke_before_version is not None:
                        await session_store.revoke_before_version(
                            redis, task.user_id, task.revoke_before_version
                        )
                    if task.clear_password_rate:
                        await session_store.clear_password_rate(redis, task.user_id)
                except RedisError as exc:
                    # 只保存错误类型，异常消息可能含连接凭据。
                    task.last_error = type(exc).__name__
                    logger.warning(
                        "session_cleanup_pending task_id=%s error=%s", task.id, task.last_error
                    )
                    return False
                task.completed_at = utc_now()
                task.last_error = None
        return True
    except SQLAlchemyError as exc:
        # 清理效果幂等；标记提交失败仍可从原任务恢复。
        logger.error(
            "session_cleanup_retry_required task_id=%s error=%s", task_id, type(exc).__name__
        )
        return False


async def retry_pending(session_factory, redis, limit=100):
    async with session_factory() as session:
        task_ids = await crud.pending_cleanup_ids(session, limit)
    completed = 0
    for task_id in task_ids:
        completed += int(await deliver(session_factory, redis, task_id))
    async with session_factory() as session:
        pending, failed = await crud.cleanup_counts(session)
    return {
        "attempted": len(task_ids),
        "completed": completed,
        "pending": pending,
        "failed": failed,
    }
