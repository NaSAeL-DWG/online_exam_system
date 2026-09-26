import asyncio
from pathlib import PurePosixPath
from uuid import uuid4

from app.core.errors import BusinessError
from app.modules.identity import service as identity_service
from app.modules.identity.types import UserType
from . import crud, storage
from .models import UploadedAsset
from .schemas import AssetPublic


async def upload(session, identity, settings, filename, data):
    if len(data) > settings.asset_max_bytes:
        raise BusinessError("IMAGE_TOO_LARGE", "图片超过上传大小限制")
    media_type = await asyncio.to_thread(storage.validate_image, data)
    async with session.begin():
        await identity_service.validate_actor(session, identity, UserType.ADMIN, UserType.TEACHER)
        item = UploadedAsset(
            uploader_id=identity.user.id,
            storage_key=uuid4().hex,
            original_name=PurePosixPath((filename or "image").replace("\\", "/")).name[:255],
            media_type=media_type,
            size_bytes=len(data),
        )
        await asyncio.to_thread(
            storage.write_new, settings.asset_storage_dir, item.storage_key, data
        )
        await crud.insert(session, item)
        result = AssetPublic(
            id=item.id,
            url=f"/api/assets/{item.id}",
            original_name=item.original_name,
            media_type=item.media_type,
            size_bytes=item.size_bytes,
        )
    return result


async def read(session, identity, settings, asset_id):
    # 迭代3须经快照题干引用授权；迭代5解析引用还须校验公布与回看。
    # 当前学生没有答题入口，拒绝任意资源URL可阻止提前读取答案图片。
    identity_service.ensure_role(identity.user, UserType.ADMIN, UserType.TEACHER)
    item = await crud.by_id(session, asset_id)
    if item is None:
        raise BusinessError("ASSET_NOT_FOUND", "图片不存在")
    try:
        data = await asyncio.to_thread(
            storage.read_bytes, settings.asset_storage_dir, item.storage_key
        )
    except FileNotFoundError:
        raise BusinessError("ASSET_NOT_FOUND", "图片不存在") from None
    return data, item.media_type
