from datetime import timedelta

from sqlalchemy import delete, select

from app.core.clock import utc_now

from .models import LogSettings, RuntimeLog


async def settings(session, *, lock=False):
    return await session.get(LogSettings, 1, with_for_update=lock, populate_existing=True)


async def prune(session, file_enabled):
    """调用方持有设置行锁，使批量入库、清理和跨进程文件写入串行。"""
    if file_enabled:
        await session.execute(
            delete(RuntimeLog).where(RuntimeLog.timestamp < utc_now() - timedelta(days=7))
        )
    limit = 100000 if file_enabled else 20000
    excess = select(RuntimeLog.id).order_by(RuntimeLog.id.desc()).offset(limit)
    await session.execute(delete(RuntimeLog).where(RuntimeLog.id.in_(excess)))


async def append_batch(session, records):
    rows = [RuntimeLog(**record) for record in records]
    session.add_all(rows)
    await session.flush()
    return rows


async def runtime_rows(session, query, *, export=False):
    statement = select(RuntimeLog)
    levels = {
        "INFO": ["INFO"],
        "WARNING": ["INFO", "WARNING"],
        "ERROR": ["INFO", "WARNING", "ERROR"],
        "DEBUG": ["DEBUG", "INFO", "WARNING", "ERROR"],
    }
    statement = statement.where(RuntimeLog.level.in_(levels[query.level]))
    for name in ("module", "task", "correlation_id"):
        if value := getattr(query, name):
            statement = statement.where(getattr(RuntimeLog, name) == value)
    if query.start:
        statement = statement.where(RuntimeLog.timestamp >= query.start)
    if query.end:
        statement = statement.where(RuntimeLog.timestamp <= query.end)
    if query.q:
        statement = statement.where(RuntimeLog.message.icontains(query.q, autoescape=True))
    if not export:
        if query.before:
            statement = statement.where(RuntimeLog.id < int(query.before))
        if query.after:
            statement = statement.where(RuntimeLog.id > int(query.after))
    ascending = bool(query.after) and not export
    rows = list(
        (
            await session.scalars(
                statement.order_by(
                    RuntimeLog.id.asc() if ascending else RuntimeLog.id.desc()
                ).limit(10001 if export else query.page_size + 1)
            )
        ).all()
    )
    return rows
