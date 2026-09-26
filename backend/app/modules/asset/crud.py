from .models import UploadedAsset


async def insert(session, item):
    session.add(item)
    await session.flush()


async def by_id(session, asset_id):
    return await session.get(UploadedAsset, asset_id)
