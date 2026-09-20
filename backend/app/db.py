from collections.abc import AsyncIterator

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import Settings


class Resources:
    """集中管理数据库与 Redis 连接生命周期。"""

    def __init__(self, settings: Settings) -> None:
        self.engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        self.redis = Redis.from_url(settings.redis_url, decode_responses=True)

    async def close(self) -> None:
        """关闭应用持有的异步连接池。"""

        await self.redis.aclose()
        await self.engine.dispose()


async def session_dependency(resources: Resources) -> AsyncIterator[AsyncSession]:
    """为一次请求提供数据库会话。"""

    async with resources.session_factory() as session:
        yield session
