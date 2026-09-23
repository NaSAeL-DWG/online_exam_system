from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.contracts import Page, Pagination
from app.deps import Identity, get_session, require_csrf, roles
from app.modules.identity.types import UserType
from . import service
from .schemas import (
    ClassCreateRequest,
    ClassPatchRequest,
    ClassPublic,
    ClassResponse,
    MemberPutRequest,
)

router = APIRouter(prefix="/api/classes", tags=["教学班"])
staff = roles(UserType.ADMIN, UserType.TEACHER)
admin = roles(UserType.ADMIN)


@router.get("", response_model=Page[ClassPublic])
async def list_classes(
    pagination: Pagination = Depends(),
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """分页检索有权查看的教学班，列表仅包含学生人数。"""
    return await service.list_classes(session, identity, pagination)


@router.post(
    "", status_code=201, response_model=ClassResponse, dependencies=[Depends(require_csrf)]
)
async def create_class(
    payload: ClassCreateRequest, identity: Identity = Depends(admin), session=Depends(get_session)
):
    """创建教学班并关联教师。"""
    return await service.create_class(session, identity, payload)


@router.get("/{class_id}", response_model=ClassResponse)
async def get_class(
    class_id: UUID, identity: Identity = Depends(staff), session=Depends(get_session)
):
    """取得教学班详情及成员资料。"""
    return await service.get_class(session, identity, class_id)


@router.patch("/{class_id}", response_model=ClassResponse, dependencies=[Depends(require_csrf)])
async def patch_class(
    class_id: UUID,
    payload: ClassPatchRequest,
    identity: Identity = Depends(admin),
    session=Depends(get_session),
):
    """修改班级资料、教师关系或归档状态。"""
    return await service.patch_class(session, identity, class_id, payload)


@router.put(
    "/{class_id}/members/{user_id}",
    response_model=ClassResponse,
    dependencies=[Depends(require_csrf)],
)
async def put_member(
    class_id: UUID,
    user_id: UUID,
    payload: MemberPutRequest,
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """由管理员或关联教师维护合法角色成员。"""
    return await service.put_member(session, identity, class_id, user_id, payload)


@router.delete(
    "/{class_id}/members/{user_id}", status_code=204, dependencies=[Depends(require_csrf)]
)
async def delete_member(
    class_id: UUID, user_id: UUID, identity: Identity = Depends(staff), session=Depends(get_session)
):
    """移出教学班成员并保留审计。"""
    await service.delete_member(session, identity, class_id, user_id)
