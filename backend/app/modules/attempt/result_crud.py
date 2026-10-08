from sqlalchemy import select, func

from .models import ExamAttempt, StudentAnswer, AttemptQuestionOrder
from .types import GradingStatus


async def answers(session, attempt_ids):
    return (
        await session.scalars(
            select(StudentAnswer)
            .where(StudentAnswer.attempt_id.in_(attempt_ids))
            .order_by(StudentAnswer.attempt_id, StudentAnswer.id)
            .execution_options(populate_existing=True)
        )
    ).all()


async def refreshed_attempt(session, attempt_id):
    return await session.get(ExamAttempt, attempt_id, populate_existing=True)


async def refreshed_answer(session, answer_id):
    return await session.get(StudentAnswer, answer_id, populate_existing=True)


async def orders(session, attempt_id):
    return (
        await session.scalars(
            select(AttemptQuestionOrder)
            .where(AttemptQuestionOrder.attempt_id == attempt_id)
            .order_by(AttemptQuestionOrder.display_order)
        )
    ).all()


async def mistake_page(session, attempt_ids, question_ids, pagination, mastered, mastered_ids):
    statement = select(StudentAnswer).where(
        StudentAnswer.attempt_id.in_(attempt_ids),
        StudentAnswer.exam_question_id.in_(question_ids),
        StudentAnswer.grading_status == GradingStatus.GRADED,
        StudentAnswer.is_correct.is_(False),
        StudentAnswer.score.is_not(None),
    )
    if mastered is True:
        statement = statement.where(StudentAnswer.id.in_(mastered_ids))
    elif mastered is False:
        statement = statement.where(StudentAnswer.id.not_in(mastered_ids))
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = (
        await session.scalars(
            statement.order_by(StudentAnswer.created_at.desc(), StudentAnswer.id)
            .offset((pagination.page - 1) * pagination.page_size)
            .limit(pagination.page_size)
        )
    ).all()
    return rows, total
