from collections.abc import AsyncIterator

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import Settings


class Resources:
    """集中管理数据库与 Redis 连接生命周期。"""

    def __init__(self, settings: Settings) -> None:
        self.engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        self.redis = Redis.from_url(settings.redis_url, decode_responses=True)
        self.log_collector = None
        self.log_storage_dir = settings.log_storage_dir

    async def start_logging(self):
        """各公开入口显式启动自己的独立日志汇聚任务。"""
        from .runtime_logging import RuntimeCollector

        self.log_collector = RuntimeCollector(self.session_factory, self.log_storage_dir)
        await self.log_collector.start()

    async def close(self) -> None:
        """关闭应用持有的异步连接池。"""

        if self.log_collector:
            await self.log_collector.close()
        await self.redis.aclose()
        await self.engine.dispose()


async def session_dependency(resources: Resources) -> AsyncIterator[AsyncSession]:
    """为一次请求提供数据库会话。"""

    async with resources.session_factory() as session:
        yield session
