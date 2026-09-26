from uuid import UUID
from fastapi import APIRouter, Depends, File, Response, UploadFile

from app.deps import Identity, get_runtime_settings, get_session, require_csrf, roles
from app.modules.identity.types import UserType
from . import service
from .schemas import AssetPublic

router = APIRouter(tags=["私有图片资源"])
staff = roles(UserType.ADMIN, UserType.TEACHER)


@router.post(
    "/api/staff/assets",
    status_code=201,
    response_model=AssetPublic,
    dependencies=[Depends(require_csrf)],
)
async def upload_asset(
    file: UploadFile = File(),
    identity: Identity = Depends(staff),
    session=Depends(get_session),
    settings=Depends(get_runtime_settings),
):
    """验证并保存不可覆盖的本地图片，限制读取字节数。"""
    data = await file.read(settings.asset_max_bytes + 1)
    return await service.upload(session, identity, settings, file.filename, data)


@router.get(
    "/api/assets/{asset_id}",
    response_class=Response,
    responses={
        200: {
            "content": {
                media_type: {"schema": {"type": "string", "format": "binary"}}
                for media_type in ("image/png", "image/jpeg", "image/webp")
            }
        }
    },
)
async def read_asset(
    asset_id: UUID,
    identity: Identity = Depends(staff),
    session=Depends(get_session),
    settings=Depends(get_runtime_settings),
):
    """实时授权读取私有图片，禁止公共缓存和内容类型嗅探。"""
    data, media_type = await service.read(session, identity, settings, asset_id)
    return Response(
        content=data,
        media_type=media_type,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )
