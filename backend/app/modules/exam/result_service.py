from . import result_crud


async def student_contexts(session, student_id, exam_id=None, q=""):
    """公开学生结果上下文查询；调用方拥有事务，查询实时持有考试共享锁。"""
    return await result_crud.student_contexts(session, student_id, exam_id, q)


async def questions_for_exams(session, exam_ids):
    """公开批量快照读取能力，学习反馈不读取实时题库。"""
    return await result_crud.questions_for_exams(session, exam_ids)


async def student_context_page(session, student_id, pagination):
    """公开学生历史分页能力，事务内只锁定当前页上下文。"""
    return await result_crud.student_context_page(session, student_id, pagination)


async def mistake_question_ids(session, exam_ids, subject, kind, knowledge_tag, q, title_exam_ids):
    """公开错题候选ID筛选能力，学习模块不访问考试内部查询或表。"""
    return await result_crud.mistake_question_ids(
        session, exam_ids, subject, kind, knowledge_tag, q, title_exam_ids
    )


async def question_summaries_by_ids(session, ids):
    """公开本页快照摘要投影，错题列表不加载评分依据。"""
    return await result_crud.question_summaries_by_ids(session, ids)


async def learning_question_metadata(session, exam_ids):
    """公开学习统计元数据查询，不向分析模块传递题干和评分依据。"""
    return await result_crud.learning_question_metadata(session, exam_ids)


async def question_rate_snapshots(session, exam_id):
    """公开教师逐题统计摘要查询。"""
    return await result_crud.question_rate_snapshots(session, exam_id)
