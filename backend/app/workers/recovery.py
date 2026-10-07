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


@dataclass
class GradingRecoveryResult:
    scanned: int = 0
    graded: int = 0
    skipped: int = 0
    failed: int = 0
    exam_scanned: int = 0
    assigned: int = 0
    graded_attempt_ids: list[str] = field(default_factory=list)
    assigned_exam_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


async def recover_grading(resources: Resources, *, limit: int = 100) -> GradingRecoveryResult:
    """先补客观题及空答，再补结束考试的人工阅卷分配。"""

    from app.modules.grading import service as grading_service

    async with resources.session_factory() as session:
        attempts = await grading_service.scan_pending_grading_attempts(session, limit=limit)
    result = GradingRecoveryResult(scanned=len(attempts))
    for attempt_id, revision in attempts:
        try:
            # 单份答卷独立事务，失败保留持久待处理状态供下轮扫描重试。
            async with resources.session_factory() as session:
                graded = await grading_service.grade_attempt(session, attempt_id, revision)
        except Exception as exc:
            result.failed += 1
            logger.warning("判分补偿待重试 attempt_id=%s error=%s", attempt_id, type(exc).__name__)
        else:
            if graded:
                result.graded += 1
                result.graded_attempt_ids.append(str(attempt_id))
            else:
                result.skipped += 1

    async with resources.session_factory() as session:
        exam_ids = await grading_service.scan_assignable_exam_ids(session, limit=limit)
    result.exam_scanned = len(exam_ids)
    for exam_id in exam_ids:
        try:
            async with resources.session_factory() as session:
                assigned = await grading_service.assign_grading_tasks(session, exam_id)
        except Exception as exc:
            result.failed += 1
            logger.warning("阅卷分配待重试 exam_id=%s error=%s", exam_id, type(exc).__name__)
        else:
            result.assigned += assigned
            if assigned:
                result.assigned_exam_ids.append(str(exam_id))
    return result
