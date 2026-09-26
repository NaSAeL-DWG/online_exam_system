from sqlalchemy import delete, func, select

from .models import Exam, ExamGrader, ExamQuestion


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
