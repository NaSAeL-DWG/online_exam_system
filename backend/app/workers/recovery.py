import logging
from dataclasses import asdict, dataclass, field

from app.core.database import Resources
from app.modules.attempt import service


logger = logging.getLogger(__name__)


@dataclass
class RecoveryResult:
    scanned: int = 0
    submitted: int = 0
    skipped: int = 0
    failed: int = 0
    submitted_attempt_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


async def recover_due_attempts(resources: Resources, *, limit: int = 100) -> RecoveryResult:
    """从持久数据库补提交，不要求截止任务仍然存在于 Redis。"""

    async with resources.session_factory() as session:
        attempt_ids = await service.scan_due_attempt_ids(session, limit=limit)
    result = RecoveryResult(scanned=len(attempt_ids))
    for attempt_id in attempt_ids:
        try:
            # 扫描事务已经结束，每份作答独立提交；一份失败不回滚其他答卷。
            async with resources.session_factory() as session:
                submitted = await service.timeout_attempt(session, attempt_id)
        except Exception as exc:
            result.failed += 1
            logger.warning("超时提交待重试 attempt_id=%s error=%s", attempt_id, type(exc).__name__)
        else:
            if submitted:
                result.submitted += 1
                result.submitted_attempt_ids.append(str(attempt_id))
            else:
                result.skipped += 1
    return result
