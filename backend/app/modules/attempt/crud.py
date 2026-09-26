from sqlalchemy import func, select, update

from .models import ExamAttempt
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
