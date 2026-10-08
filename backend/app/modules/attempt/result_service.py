from . import result_crud


async def answers(session, attempt_ids):
    """公开批量答案查询，调用方先锁考试并验证本人结果可见性。"""
    return await result_crud.answers(session, attempt_ids)


async def refreshed_attempt(session, attempt_id):
    """公开只读刷新能力：共享考试锁后清除定位阶段的身份映射旧状态，不升级作答锁。"""
    return await result_crud.refreshed_attempt(session, attempt_id)


async def refreshed_answer(session, answer_id):
    """公开单题只读刷新能力，锁后读取错题当前评分而不加载整份答案。"""
    return await result_crud.refreshed_answer(session, answer_id)


async def orders(session, attempt_id):
    """公开持久展示顺序查询，历史回看复原本次答卷顺序。"""
    return await result_crud.orders(session, attempt_id)


async def mistake_page(
    session, attempt_ids, question_ids, pagination, mastered=None, mastered_ids=None
):
    """公开错题答案分页能力；上下文与快照筛选由学习用例先确定。"""
    return await result_crud.mistake_page(
        session, attempt_ids, question_ids, pagination, mastered, mastered_ids
    )
