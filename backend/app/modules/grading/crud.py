from sqlalchemy import func, select, update

from .models import GradingHistory, GradingTask
from .types import TaskStatus


def add_history(session, history):
    session.add(history)


async def histories(session, answer_id):
    return (
        await session.scalars(
            select(GradingHistory)
            .where(GradingHistory.answer_id == answer_id)
            .order_by(GradingHistory.answer_version, GradingHistory.created_at, GradingHistory.id)
        )
    ).all()


async def task_for_attempt(session, attempt_id, *, lock=False):
    statement = select(GradingTask).where(GradingTask.attempt_id == attempt_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return await session.scalar(statement)


async def tasks_for_attempts(session, attempt_ids, *, lock=False):
    statement = (
        select(GradingTask).where(GradingTask.attempt_id.in_(attempt_ids)).order_by(GradingTask.id)
    )
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return (await session.scalars(statement)).all()


async def task_by_id(session, task_id, *, lock=False):
    return await session.get(GradingTask, task_id, with_for_update=lock, populate_existing=lock)


async def insert_task(session, task):
    session.add(task)
    await session.flush()


async def task_page(session, pagination, attempt_ids=None, status=None, teacher_id=None):
    statement = select(GradingTask).where(GradingTask.status != TaskStatus.VOID)
    if attempt_ids is not None:
        statement = statement.where(GradingTask.attempt_id.in_(attempt_ids))
    if status is not None:
        statement = statement.where(GradingTask.status == status)
    if teacher_id is not None:
        statement = statement.where(GradingTask.assigned_teacher_id == teacher_id)
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = (
        await session.scalars(
            statement.order_by(GradingTask.created_at, GradingTask.id)
            .offset((pagination.page - 1) * pagination.page_size)
            .limit(pagination.page_size)
        )
    ).all()
    return rows, total


async def void_tasks(session, attempt_ids, now):
    await session.execute(
        update(GradingTask)
        .where(GradingTask.attempt_id.in_(attempt_ids), GradingTask.status != TaskStatus.VOID)
        .values(
            status=TaskStatus.VOID,
            completed_at=None,
            version=GradingTask.version + 1,
            updated_at=now,
        )
    )


async def wait_teacher_tasks(session, teacher_id, now):
    await session.execute(
        update(GradingTask)
        .where(
            GradingTask.assigned_teacher_id == teacher_id,
            GradingTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
        )
        .values(status=TaskStatus.UNASSIGNED, version=GradingTask.version + 1, updated_at=now)
    )


async def flush(session):
    await session.flush()
