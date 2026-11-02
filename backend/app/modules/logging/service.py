from app.core.errors import BusinessError
from datetime import datetime, timedelta
from uuid import UUID

from app.core.clock import utc_now
from app.modules.identity.service import (
    ensure_role,
    record_audit,
    safe_audit_entries,
    validate_actor,
    publish_committed_audits,
)
from app.modules.identity.types import UserType

from . import crud
from .schemas import AuditPage, RuntimeItem, RuntimePage, SettingsPublic


def public_settings(row):
    from app.core.clock import utc_now

    return SettingsPublic(
        file_enabled=row.file_enabled,
        runtime_limit=100000 if row.file_enabled else 20000,
        retention_days=7 if row.file_enabled else None,
        debug_modules=[
            {"module": name, "expires_at": expiry}
            for name, expiry in row.debug_modules.items()
            if datetime.fromisoformat(expiry) > utc_now()
        ],
    )


async def read_settings(session, identity):
    ensure_role(identity.user, UserType.ADMIN)
    return public_settings(await crud.settings(session))


def runtime_item(row):
    return RuntimeItem(
        id=str(row.id),
        cursor=str(row.id),
        timestamp=row.timestamp,
        level=row.level,
        module=row.module,
        task=row.task,
        message=row.message,
        correlation_id=row.correlation_id,
        formatted=f"{row.timestamp.isoformat()} {row.level}: [{row.module}]({row.task}): {row.message}",
    )


def validate_runtime_cursor(query):
    import re

    if any(
        value is not None and (not re.fullmatch(r"[0-9]+", value) or int(value) > 2**63 - 1)
        for value in (query.before, query.after)
    ):
        raise BusinessError("LOG_CURSOR_INVALID", "日志游标无效，请刷新后重试")


async def runtime_page(session, identity, query):
    ensure_role(identity.user, UserType.ADMIN)
    validate_runtime_cursor(query)
    rows = await crud.runtime_rows(session, query)
    more = len(rows) > query.page_size
    selected = rows[: query.page_size]
    if query.after:
        selected.reverse()
    items = [runtime_item(row) for row in selected]
    return RuntimePage(
        items=items,
        has_more=more,
        next_before=items[-1].cursor if items else None,
        latest_cursor=items[0].cursor if items else None,
    )


async def audit_page(session, identity, query):
    async with session.begin():
        entries = await safe_audit_entries(session, identity, query)
    more = len(entries) > query.page_size
    entries = entries[: query.page_size]
    if query.after:
        entries.reverse()
    return AuditPage(
        items=entries,
        has_more=more,
        next_before=entries[-1]["cursor"] if entries else None,
        latest_cursor=entries[0]["cursor"] if entries else None,
    )


async def change_settings(session, identity, *, file_enabled=None, module=None, enabled=None):
    """设置修改、即时在线收缩及操作审计在同一业务事务中完成。"""
    async with session.begin():
        actor = await validate_actor(session, identity, UserType.ADMIN)
        row = await crud.settings(session, lock=True)
        if file_enabled is not None:
            row.file_enabled = file_enabled
            await crud.prune(session, file_enabled)
            action = "LOG_FILE_SETTINGS"
            details = {"file_enabled": file_enabled}
        else:
            modules = dict(row.debug_modules)
            if enabled:
                modules[module] = (utc_now() + timedelta(minutes=15)).isoformat()
            else:
                modules.pop(module, None)
            row.debug_modules = modules
            action = "LOG_DEBUG_SETTINGS"
            details = {"module": module, "enabled": enabled}
        record_audit(
            session,
            actor_id=actor.id,
            action=action,
            entity_type="log_settings",
            entity_id=UUID(int=1),
            after_data=details,
        )
        result = public_settings(row)
    return result


async def export_logs(session, identity, query, *, audit=False):
    """先验证完整结果数量再导出；不能通过分页游标绕过一万条上限。"""
    async with session.begin():
        actor = await validate_actor(session, identity, UserType.ADMIN)
        if audit:
            entries = await safe_audit_entries(session, identity, query, export=True)
            lines = [entry["formatted"] for entry in entries]
        else:
            rows = await crud.runtime_rows(session, query, export=True)
            lines = [runtime_item(row).formatted for row in reversed(rows)]
        if len(lines) > 10000:
            raise BusinessError("LOG_EXPORT_LIMIT", "结果超过10000条，请缩小筛选范围后再下载")
        record_audit(
            session,
            actor_id=actor.id,
            action="LOG_EXPORT",
            entity_type="audit" if audit else "runtime_log",
            entity_id=UUID(int=1),
            after_data={"count": len(lines)},
        )
    return "\n".join(lines) + ("\n" if lines else "")


async def collector_settings(session_factory):
    async with session_factory() as session, session.begin():
        settings = await crud.settings(session)
        await publish_committed_audits(session)
        return settings


async def maintain_runtime(session_factory):
    """即使没有新日志，也周期执行七天清理；与批量入库共用全局锁。"""
    async with session_factory() as session, session.begin():
        settings = await crud.settings(session, lock=True)
        await crud.prune(session, settings.file_enabled)


async def persist_runtime_batch(session_factory, directory, records, dropped=0):
    """独立批量事务；设置行锁同时协调 API/worker/CLI 的入库次序和文件单写入者。"""
    import asyncio
    from .file_storage import write_batch

    async with session_factory() as session, session.begin():
        settings = await crud.settings(session, lock=True)
        if dropped:
            records = [
                *records,
                {
                    "timestamp": utc_now(),
                    "level": "WARNING",
                    "module": "logging",
                    "task": "collector",
                    "message": f"日志缓冲或存储故障丢弃 {dropped} 条运行日志",
                    "correlation_id": None,
                },
            ]
        rows = await crud.append_batch(session, records)
        if settings.file_enabled:
            # 文件写入在线程完成前持有全局锁，避免取消后线程继续与另一写入者并发。
            operation = asyncio.create_task(asyncio.to_thread(write_batch, directory, rows))
            try:
                await asyncio.shield(operation)
            except asyncio.CancelledError:
                await operation
                raise
            except OSError:
                await crud.append_batch(
                    session,
                    [
                        {
                            "timestamp": utc_now(),
                            "level": "ERROR",
                            "module": "logging",
                            "task": "file_writer",
                            "message": "日志文件写入失败，在线记录继续保留",
                            "correlation_id": None,
                        }
                    ],
                )
        await crud.prune(session, settings.file_enabled)
