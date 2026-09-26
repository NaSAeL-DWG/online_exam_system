from app.core.clock import utc_now
from . import crud


async def has_started(session, participant_ids):
    """包含 VOID 历史；调用方须先锁考试，再检查真实持久记录。"""
    return await crud.has_any(session, participant_ids)


async def void_participant_attempts(session, participant_ids, reason):
    """参与资格撤销用例中的可组合写入，不提交调用方事务。"""
    await crud.void_all(session, participant_ids, reason, utc_now())
    # TODO(迭代4)：grading_task 落地时在同一事务作废相关任务。


async def participant_attempt_counts(session, participant_ids):
    """公开管理查询返回已用次数与废弃次数；恢复资格不更改历史。"""
    return await crud.counts(session, participant_ids)
