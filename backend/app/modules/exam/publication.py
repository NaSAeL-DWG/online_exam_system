from app.core.clock import utc_now
from app.core.errors import BusinessError
from app.modules.identity import service as identity_service
from app.modules.grading import publication as grading_publication
from . import service
from .types import ExamStatus


async def publish_results(session, identity, exam_id, payload):
    """顶层公布事务与评分、更正、撤销共用考试锁，避免检查和公布间的状态变化。"""
    async with session.begin():
        await identity_service.validate_content_actor(session, identity)
        exam = await service.require_exam(session, exam_id, lock=True)
        service.ensure_version(exam, payload.version)
        if exam.status != ExamStatus.RELEASED:
            raise BusinessError("EXAM_STATE_INVALID", "仅已发布且有效的考试可以公布结果")
        if exam.end_at is None or utc_now() < exam.end_at:
            raise BusinessError("RESULTS_NOT_READY", "考试结束后才能公布结果")
        await grading_publication.validate_completed_results(session, exam)
        exam.status = ExamStatus.RESULTS_PUBLISHED
        exam.results_published_at = utc_now()
        exam.version += 1
        exam.updated_at = utc_now()
        identity_service.record_audit(
            session,
            actor_id=identity.user.id,
            action="EXAM_RESULTS_PUBLISHED",
            entity_type="exam",
            entity_id=exam.id,
            before_data={"status": ExamStatus.RELEASED.value},
            after_data={
                "status": exam.status.value,
                "version": exam.version,
                "grading_revision": exam.grading_revision,
            },
        )
        result = await service.detail(session, exam)
    return result
