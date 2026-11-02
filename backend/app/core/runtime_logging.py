"""标准 logging 的有界异步汇聚入口；不在业务事务或 logging.emit 中访问数据库。"""

import asyncio
from contextvars import ContextVar
from datetime import datetime, timezone
import logging
from queue import Empty, Full, Queue
import re
import time

from app.core.clock import utc_now

correlation_context = ContextVar("log_correlation", default=None)


def module_name(logger_name):
    parts = logger_name.split(".")
    if len(parts) > 2 and parts[1] == "modules":
        return parts[2]
    if len(parts) > 1 and parts[1] == "workers":
        return "worker"
    if len(parts) > 2 and parts[1] == "core":
        return parts[2]
    return "api" if logger_name in {"app.api", "app.main"} else "cli"


def safe_identifier(value, fallback):
    value = str(value or fallback)
    return value if re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", value) else fallback


def safe_message(value):
    # 已有业务调用只传固定模板和安全 ID；额外拦截常见凭据拼接，且不渲染 exc_info。
    value = str(value).replace("\r", "\\r").replace("\n", "\\n")
    value = re.sub(
        r"(?i)(password|passwd|token|secret|authorization|cookie|database_url|redis_url)\s*[:=]\s*\S+",
        r"\1=[已隐藏]",
        value,
    )
    value = re.sub(
        r"(?i)\b(?:postgres(?:ql)?(?:\+asyncpg)?|redis)://\S+", "[连接信息已隐藏]", value
    )
    return value[:4096]


class BoundedHandler(logging.Handler):
    def __init__(self, collector):
        super().__init__(logging.DEBUG)
        self.collector = collector

    def emit(self, record):
        collector = self.collector
        if not record.name.startswith("app.") or record.name.startswith(
            ("app.modules.logging", "app.core.runtime_logging")
        ):
            return
        module = safe_identifier(getattr(record, "log_module", None), module_name(record.name))
        if record.levelno < logging.INFO:
            expiry = collector.debug_modules.get(module)
            if expiry is None or expiry <= utc_now():
                return
        try:
            timestamp = getattr(record, "log_timestamp", None) or datetime.fromtimestamp(
                record.created, timezone.utc
            )
            collector.queue.put_nowait(
                {
                    "timestamp": timestamp,
                    "level": "ERROR" if record.levelno >= logging.ERROR else record.levelname,
                    "module": module,
                    "task": safe_identifier(getattr(record, "task", None), record.funcName),
                    "message": safe_message(record.getMessage()),
                    "correlation_id": safe_identifier(
                        getattr(record, "correlation_id", None) or correlation_context.get(), ""
                    )
                    or None,
                }
            )
        except (Full, ValueError, TypeError):
            collector.dropped += 1


class RuntimeCollector:
    def __init__(self, session_factory, directory):
        self.session_factory = session_factory
        self.directory = directory
        self.queue = Queue(maxsize=5000)
        self.debug_modules = {}
        self.dropped = 0
        self.task = None
        self.stop = False
        self.handler = BoundedHandler(self)
        self.last_refresh = 0.0
        self.last_maintenance = 0.0
        self.busy = False

    async def start(self):
        await self.refresh()
        app_logger = logging.getLogger("app")
        app_logger.setLevel(logging.DEBUG)
        # 应用日志只经过同一个采集器；阻止父级控制台处理器旁路输出未启用的 DEBUG。
        app_logger.propagate = False
        app_logger.addHandler(self.handler)
        self.task = asyncio.create_task(self.run(), name="runtime-log-writer")

    async def refresh(self):
        from app.modules.logging.service import collector_settings

        try:
            settings = await collector_settings(self.session_factory)
            self.debug_modules = {
                name: datetime.fromisoformat(expiry)
                for name, expiry in settings.debug_modules.items()
            }
        except Exception:
            # 故障时保留已知到期时间；不经 logging 输出数据库异常，避免自激或凭据泄露。
            pass
        self.last_refresh = time.monotonic()

    async def run(self):
        from app.modules.logging.service import maintain_runtime, persist_runtime_batch

        while not self.stop or not self.queue.empty():
            if time.monotonic() - self.last_refresh >= 1:
                await self.refresh()
            if time.monotonic() - self.last_maintenance >= 30:
                try:
                    await maintain_runtime(self.session_factory)
                except Exception:
                    pass
                self.last_maintenance = time.monotonic()
            batch = []
            for _ in range(200):
                try:
                    batch.append(self.queue.get_nowait())
                except Empty:
                    break
            if batch:
                self.busy = True
                dropped = self.dropped
                try:
                    await persist_runtime_batch(
                        self.session_factory, self.directory, batch, dropped
                    )
                    self.dropped -= dropped
                except Exception:
                    self.dropped += len(batch)
                finally:
                    self.busy = False
            else:
                await asyncio.sleep(0.1)

    async def flush(self):
        """CLI 等待有限批次完成；存储故障不会无限重试或积累内存。"""
        async with asyncio.timeout(15):
            while not self.queue.empty() or self.busy:
                await asyncio.sleep(0.01)

    async def close(self):
        logging.getLogger("app").removeHandler(self.handler)
        self.stop = True
        if self.task:
            try:
                await asyncio.wait_for(self.task, timeout=15)
            except TimeoutError:
                self.task.cancel()
                await asyncio.gather(self.task, return_exceptions=True)
