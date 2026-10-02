from sqlalchemy import select

from .models import Exam, ExamParticipant, ExamQuestion
from .types import ExamStatus, ParticipantStatus


async def locked_student_participants(session, student_id, now):
    """按统一顺序持有考试共享锁；资格变更、交卷和取消都须先取得考试排他锁。"""
    exam_ids = (
        await session.scalars(
            select(Exam.id)
            .join(ExamParticipant, ExamParticipant.exam_id == Exam.id)
            .where(
                ExamParticipant.user_id == student_id,
                Exam.status == ExamStatus.RELEASED,
                Exam.start_at <= now,
                Exam.end_at > now,
            )
            .order_by(Exam.id)
            .with_for_update(read=True, of=Exam)
        )
    ).all()
    if not exam_ids:
        return []
    # 等待考试锁后重新读取资格，不能沿用撤销事务之前的查询结果。
    return (
        await session.execute(
            select(ExamParticipant.id, ExamParticipant.exam_id).where(
                ExamParticipant.exam_id.in_(exam_ids),
                ExamParticipant.user_id == student_id,
                ExamParticipant.status == ParticipantStatus.ASSIGNED,
            )
        )
    ).all()


async def snapshot_display_content(session, exam_ids):
    """只投影学生答题所需内容，解析与标准答案不进入资源授权过程。"""
    return (
        await session.execute(
            select(ExamQuestion.content, ExamQuestion.options).where(
                ExamQuestion.exam_id.in_(exam_ids)
            )
        )
    ).all()
