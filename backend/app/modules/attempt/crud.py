from sqlalchemy import func, select, update

from .models import AttemptQuestionOrder, ExamAttempt, StudentAnswer
from .types import AttemptStatus


async def has_any(session, participant_ids):
    return (
        await session.scalar(
            select(ExamAttempt.id)
            .where(ExamAttempt.exam_participant_id.in_(participant_ids))
            .limit(1)
        )
        is not None
    )


async def void_all(session, participant_ids, reason, now):
    await session.execute(
        update(ExamAttempt)
        .where(
            ExamAttempt.exam_participant_id.in_(participant_ids),
            ExamAttempt.status != AttemptStatus.VOID,
        )
        .values(
            status=AttemptStatus.VOID,
            voided_at=now,
            void_reason=reason,
            updated_at=now,
            version=ExamAttempt.version + 1,
            active_token_hash=None,
            active_token_generation=ExamAttempt.active_token_generation + 1,
        )
    )


async def counts(session, participant_ids):
    rows = (
        await session.execute(
            select(
                ExamAttempt.exam_participant_id,
                func.count(),
                func.count().filter(ExamAttempt.status == AttemptStatus.VOID),
            )
            .where(ExamAttempt.exam_participant_id.in_(participant_ids))
            .group_by(ExamAttempt.exam_participant_id)
        )
    ).all()
    return {row[0]: (row[1], row[2]) for row in rows}


async def current_for_participants(session, participant_ids):
    rows = (
        await session.scalars(
            select(ExamAttempt)
            .where(
                ExamAttempt.exam_participant_id.in_(participant_ids),
                ExamAttempt.status != AttemptStatus.VOID,
            )
            .order_by(ExamAttempt.exam_participant_id, ExamAttempt.attempt_no.desc())
        )
    ).all()
    result = {}
    for row in rows:
        result.setdefault(row.exam_participant_id, row)
    return result


async def by_id(session, attempt_id, *, lock=False):
    return await session.get(ExamAttempt, attempt_id, with_for_update=lock, populate_existing=lock)


async def participant_attempts(session, participant_id):
    return (
        await session.scalars(
            select(ExamAttempt)
            .where(ExamAttempt.exam_participant_id == participant_id)
            .order_by(ExamAttempt.attempt_no)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).all()


async def insert(session, attempt, answers, orders):
    session.add(attempt)
    await session.flush()
    session.add_all(answers)
    session.add_all(orders)
    await session.flush()


async def answer_orders(session, attempt_id):
    return (
        await session.execute(
            select(StudentAnswer, AttemptQuestionOrder)
            .join(
                AttemptQuestionOrder,
                (AttemptQuestionOrder.attempt_id == StudentAnswer.attempt_id)
                & (AttemptQuestionOrder.exam_question_id == StudentAnswer.exam_question_id),
            )
            .where(StudentAnswer.attempt_id == attempt_id)
            .order_by(AttemptQuestionOrder.display_order)
        )
    ).all()


async def answer_by_id(session, answer_id):
    return await session.get(StudentAnswer, answer_id, with_for_update=True, populate_existing=True)


async def answers_for_submission(session, attempt_id):
    return (
        await session.scalars(
            select(StudentAnswer)
            .where(StudentAnswer.attempt_id == attempt_id)
            .order_by(StudentAnswer.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).all()


async def active_participant_ids(session, participant_ids, now):
    return list(
        await session.scalars(
            select(ExamAttempt.exam_participant_id).where(
                ExamAttempt.exam_participant_id.in_(participant_ids),
                ExamAttempt.status == AttemptStatus.IN_PROGRESS,
                ExamAttempt.deadline_at > now,
            )
        )
    )


async def flush(session):
    await session.flush()


async def due_attempt_ids(session, now, limit):
    return list(
        await session.scalars(
            select(ExamAttempt.id)
            .where(
                ExamAttempt.status == AttemptStatus.IN_PROGRESS,
                ExamAttempt.deadline_at <= now,
            )
            .order_by(ExamAttempt.deadline_at, ExamAttempt.id)
            .limit(limit)
        )
    )
