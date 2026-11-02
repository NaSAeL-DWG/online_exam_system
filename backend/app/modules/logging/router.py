from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response

from app.deps import get_session, require_csrf, roles
from app.modules.identity.types import UserType

from . import service
from .schemas import AuditPage, DebugUpdate, FileUpdate, LogQuery, RuntimePage, SettingsPublic

router = APIRouter(prefix="/api/admin/logs", tags=["系统日志"])
admin = roles(UserType.ADMIN)


@router.get("/settings", response_model=SettingsPublic)
async def read_settings(identity=Depends(admin), session=Depends(get_session)):
    """读取全局日志设置与有效的临时 DEBUG 模块。"""
    return await service.read_settings(session, identity)


@router.get("/runtime", response_model=RuntimePage)
async def runtime_logs(
    query: Annotated[LogQuery, Query()], identity=Depends(admin), session=Depends(get_session)
):
    """按累加等级和游标查询管理员可见的运行日志。"""
    return await service.runtime_page(session, identity, query)


@router.get("/audit", response_model=AuditPage)
async def audit_logs(
    query: Annotated[LogQuery, Query()], identity=Depends(admin), session=Depends(get_session)
):
    """查询与业务保留策略独立的安全操作审计。"""
    return await service.audit_page(session, identity, query)


@router.patch("/settings", response_model=SettingsPublic, dependencies=[Depends(require_csrf)])
async def update_settings(body: FileUpdate, identity=Depends(admin), session=Depends(get_session)):
    """持久修改全局文件开关并立即执行对应保留规则。"""
    return await service.change_settings(session, identity, file_enabled=body.file_enabled)


@router.put("/debug/{module}", response_model=SettingsPublic, dependencies=[Depends(require_csrf)])
async def update_debug(
    body: DebugUpdate,
    module: Annotated[str, Path(pattern=r"^[A-Za-z0-9_.-]{1,100}$")],
    identity=Depends(admin),
    session=Depends(get_session),
):
    """开启15分钟模块详细采集，或提前停止。"""
    return await service.change_settings(session, identity, module=module, enabled=body.enabled)


@router.post(
    "/runtime/export",
    dependencies=[Depends(require_csrf)],
    response_class=Response,
    responses={
        200: {"content": {"text/plain": {"schema": {"type": "string", "format": "binary"}}}}
    },
)
async def export_runtime(
    query: Annotated[LogQuery, Query()], identity=Depends(admin), session=Depends(get_session)
):
    """下载当前筛选范围内最多一万条运行日志。"""
    content = await service.export_logs(session, identity, query)
    return Response(
        content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="runtime.log"'},
    )


@router.post(
    "/audit/export",
    dependencies=[Depends(require_csrf)],
    response_class=Response,
    responses={
        200: {"content": {"text/plain": {"schema": {"type": "string", "format": "binary"}}}}
    },
)
async def export_audit(
    query: Annotated[LogQuery, Query()], identity=Depends(admin), session=Depends(get_session)
):
    """下载只含安全摘要的操作审计并记录导出动作。"""
    content = await service.export_logs(session, identity, query, audit=True)
    return Response(
        content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit.log"'},
    )
