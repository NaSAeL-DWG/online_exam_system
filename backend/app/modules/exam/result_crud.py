from sqlalchemy import select, func, or_

from .models import Exam, ExamParticipant, ExamQuestion
from .types import ExamStatus


async def student_contexts(session, student_id, exam_id=None, q=""):
    """共享锁与结果撤回、取消、评分写入串行；等待锁后重新读取状态和资格。"""
    statement = (
        select(Exam.id)
        .join(ExamParticipant, ExamParticipant.exam_id == Exam.id)
        .where(ExamParticipant.user_id == student_id, Exam.status != ExamStatus.DRAFT)
    )
    if exam_id is not None:
        statement = statement.where(Exam.id == exam_id)
    if q.strip():
        statement = statement.where(Exam.title.ilike(f"%{q.strip()}%"))
    ids = list(
        await session.scalars(statement.order_by(Exam.id).with_for_update(read=True, of=Exam))
    )
    if not ids:
        return []
    return await read_contexts(session, student_id, ids)


async def read_contexts(session, student_id, ids):
    return (
        await session.execute(
            select(Exam, ExamParticipant)
            .join(ExamParticipant, ExamParticipant.exam_id == Exam.id)
            .where(
                Exam.id.in_(ids),
                ExamParticipant.user_id == student_id,
                Exam.status != ExamStatus.DRAFT,
            )
            .order_by(Exam.end_at.desc(), Exam.id)
            .execution_options(populate_existing=True)
        )
    ).all()


async def student_context_page(session, student_id, pagination):
    """先在数据库分页考试ID，再仅锁定本页并批量读取摘要，避免载入全部历史。"""
    statement = (
        select(Exam.id)
        .join(ExamParticipant, ExamParticipant.exam_id == Exam.id)
        .where(ExamParticipant.user_id == student_id, Exam.status != ExamStatus.DRAFT)
    )
    if pagination.q.strip():
        statement = statement.where(Exam.title.ilike(f"%{pagination.q.strip()}%"))
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    ids = list(
        await session.scalars(
            statement.order_by(Exam.end_at.desc(), Exam.id)
            .offset((pagination.page - 1) * pagination.page_size)
            .limit(pagination.page_size)
        )
    )
    if not ids:
        return [], total
    # 多考试读取统一按UUID取得锁，不沿用页面展示顺序取得业务锁。
    await session.execute(
        select(Exam.id).where(Exam.id.in_(ids)).order_by(Exam.id).with_for_update(read=True)
    )
    return await read_contexts(session, student_id, ids), total


async def questions_for_exams(session, exam_ids):
    return (
        await session.scalars(
            select(ExamQuestion)
            .where(ExamQuestion.exam_id.in_(exam_ids))
            .order_by(ExamQuestion.exam_id, ExamQuestion.order_no)
        )
    ).all()


async def mistake_question_ids(session, exam_ids, subject, kind, knowledge_tag, q, title_exam_ids):
    """只投影候选ID，分类和题干筛选在数据库执行，分页前不加载历史评分依据。"""
    statement = select(ExamQuestion.id).where(ExamQuestion.exam_id.in_(exam_ids))
    if subject is not None:
        statement = statement.where(ExamQuestion.subject == subject)
    if kind is not None:
        statement = statement.where(ExamQuestion.type == kind)
    if knowledge_tag is not None:
        statement = statement.where(ExamQuestion.knowledge_tags.contains([knowledge_tag]))
    if q.strip():
        statement = statement.where(
            or_(
                ExamQuestion.content.ilike(f"%{q.strip()}%"),
                ExamQuestion.exam_id.in_(title_exam_ids),
            )
        )
    return list(await session.scalars(statement))


async def question_summaries_by_ids(session, ids):
    """错题列表只加载本页题干与分类，不加载选项、标准答案和解析。"""
    return (
        await session.execute(
            select(
                ExamQuestion.id,
                ExamQuestion.exam_id,
                ExamQuestion.type,
                ExamQuestion.subject,
                ExamQuestion.knowledge_tags,
                ExamQuestion.content,
                ExamQuestion.score,
            ).where(ExamQuestion.id.in_(ids))
        )
    ).all()


async def learning_question_metadata(session, exam_ids):
    """学习汇总只读取题型、满分、知识点与修订，不载入题干或评分依据正文。"""
    return (
        await session.execute(
            select(
                ExamQuestion.id,
                ExamQuestion.exam_id,
                ExamQuestion.type,
                ExamQuestion.score,
                ExamQuestion.knowledge_tags,
                ExamQuestion.grading_revision,
            ).where(ExamQuestion.exam_id.in_(exam_ids))
        )
    ).all()


async def question_rate_snapshots(session, exam_id):
    """逐题统计只读取摘要和分母，评分依据与选项不参与汇总。"""
    return (
        await session.execute(
            select(
                ExamQuestion.id,
                ExamQuestion.order_no,
                ExamQuestion.type,
                ExamQuestion.subject,
                ExamQuestion.content,
                ExamQuestion.score,
            )
            .where(ExamQuestion.exam_id == exam_id)
            .order_by(ExamQuestion.order_no)
        )
    ).all()
