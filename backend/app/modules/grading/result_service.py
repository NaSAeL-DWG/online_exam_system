from . import crud


async def tasks_for_attempts(session, attempt_ids):
    """公开统计任务查询，按有效作答范围读取，调用方持有考试锁。"""
    return await crud.tasks_for_attempts(session, attempt_ids)
