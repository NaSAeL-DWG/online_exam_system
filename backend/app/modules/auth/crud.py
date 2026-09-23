from sqlalchemy import select

from .models import SessionCleanup


def add_cleanup(session, user_id, revoke_before_version=None, clear_password_rate=False):
    task = SessionCleanup(
        user_id=user_id,
        revoke_before_version=revoke_before_version,
        clear_password_rate=clear_password_rate,
    )
    session.add(task)
    return task


async def lock_cleanup(session, task_id):
    return await session.get(SessionCleanup, task_id, with_for_update=True, populate_existing=True)


async def pending_cleanup_ids(session, limit):
    return (
        await session.scalars(
            select(SessionCleanup.id)
            .where(SessionCleanup.completed_at.is_(None))
            .order_by(SessionCleanup.created_at, SessionCleanup.id)
            .limit(limit)
        )
    ).all()


async def cleanup_counts(session):
    from sqlalchemy import func

    total = await session.scalar(
        select(func.count())
        .select_from(SessionCleanup)
        .where(SessionCleanup.completed_at.is_(None))
    )
    failed = await session.scalar(
        select(func.count())
        .select_from(SessionCleanup)
        .where(SessionCleanup.completed_at.is_(None), SessionCleanup.attempts > 0)
    )
    return total, failed
