from sqlalchemy import delete, func, select

from .models import Exam, ExamGrader, ExamParticipant, ExamQuestion


async def insert(session, item, questions):
    session.add(item)
    await session.flush()
    session.add_all(questions)
    await session.flush()


async def by_id(session, exam_id, *, lock=False):
    return await session.get(Exam, exam_id, with_for_update=lock, populate_existing=lock)


async def questions(session, exam_id):
    return (
        await session.scalars(
            select(ExamQuestion)
            .where(ExamQuestion.exam_id == exam_id)
            .order_by(ExamQuestion.order_no)
        )
    ).all()


async def list_page(session, pagination, status):
    statement = select(Exam)
    if pagination.q.strip():
        statement = statement.where(Exam.title.ilike("%" + pagination.q.strip() + "%"))
    if status is not None:
        statement = statement.where(Exam.status == status)
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = (
        await session.scalars(
            statement.order_by(Exam.created_at.desc(), Exam.id)
            .offset((pagination.page - 1) * pagination.page_size)
            .limit(pagination.page_size)
        )
    ).all()
    return rows, total


async def replace_questions(session, exam_id, desired):
    kept = {row.id for row in desired}
    for row in await questions(session, exam_id):
        if row.id not in kept:
            await session.delete(row)
    await session.flush()
    session.add_all(desired)
    await session.flush()


async def graders(session, exam_id):
    return (
        await session.scalars(
            select(ExamGrader.teacher_id)
            .where(ExamGrader.exam_id == exam_id)
            .order_by(ExamGrader.teacher_id)
        )
    ).all()


async def replace_graders(session, exam_id, teacher_ids, actor_id):
    await session.execute(delete(ExamGrader).where(ExamGrader.exam_id == exam_id))
    session.add_all(
        [
            ExamGrader(exam_id=exam_id, teacher_id=value, assigned_by=actor_id)
            for value in set(teacher_ids)
        ]
    )
    await session.flush()


async def participant_ids(session, exam_id):
    return (
        await session.scalars(select(ExamParticipant.id).where(ExamParticipant.exam_id == exam_id))
    ).all()


async def participants_for_users(session, exam_id, user_ids):
    return (
        await session.scalars(
            select(ExamParticipant).where(
                ExamParticipant.exam_id == exam_id, ExamParticipant.user_id.in_(user_ids)
            )
        )
    ).all()


async def add_participants(session, rows):
    session.add_all(rows)
    await session.flush()


async def participant_by_id(session, participant_id):
    return await session.get(
        ExamParticipant, participant_id, with_for_update=True, populate_existing=True
    )


async def participant_page(session, exam_id, pagination, status, user_ids=None):
    statement = select(ExamParticipant).where(ExamParticipant.exam_id == exam_id)
    if user_ids is not None:
        statement = statement.where(ExamParticipant.user_id.in_(user_ids))
    if status is not None:
        statement = statement.where(ExamParticipant.status == status)
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = (
        await session.scalars(
            statement.order_by(ExamParticipant.assigned_at, ExamParticipant.id)
            .offset((pagination.page - 1) * pagination.page_size)
            .limit(pagination.page_size)
        )
    ).all()
    return rows, total


async def participant_user_ids(session, exam_id):
    return (
        await session.scalars(
            select(ExamParticipant.user_id).where(ExamParticipant.exam_id == exam_id)
        )
    ).all()
