from app.core.errors import BusinessError
from app.modules.attempt import service as attempt_service
from app.modules.attempt.types import AttemptStatus, GradingStatus
from app.modules.exam import service as exam_service
from app.modules.exam.types import ParticipantStatus
from . import crud
from .types import TaskStatus


async def validate_completed_results(session, exam):
    """可组合公布检查：调用方持有考试锁，全部有效尝试和当前单题依据都必须完成。"""
    participants = await exam_service.grading_participants(session, exam.id)
    attempts = [
        row
        for row in await attempt_service.grading_attempts(
            session, [row.id for row in participants if row.status == ParticipantStatus.ASSIGNED]
        )
        if row.status != AttemptStatus.VOID
    ]
    if any(
        row.status != AttemptStatus.SUBMITTED
        or row.grading_status != GradingStatus.GRADED
        or row.grading_revision != exam.grading_revision
        or row.final_score is None
        for row in attempts
    ):
        raise BusinessError("RESULTS_NOT_READY", "全部有效作答须提交并按当前评分依据完成判分")
    questions = {row.id: row for row in await exam_service.attempt_questions(session, exam.id)}
    answers = await attempt_service.grading_answers_for_attempts(
        session, [row.id for row in attempts]
    )
    counts = {row.id: 0 for row in attempts}
    for answer in answers:
        counts[answer.attempt_id] += 1
        question = questions.get(answer.exam_question_id)
        if (
            question is None
            or answer.grading_status != GradingStatus.GRADED
            or answer.grading_revision != question.grading_revision
            or answer.score is None
        ):
            raise BusinessError("RESULTS_NOT_READY", "仍有单题未按当前评分依据完成判分")
    if any(count != len(questions) for count in counts.values()):
        raise BusinessError("RESULTS_NOT_READY", "答卷尚未完成全部题目判分")
    tasks = await crud.tasks_for_attempts(session, [row.id for row in attempts])
    if any(
        row.status != TaskStatus.COMPLETED or row.grading_revision != exam.grading_revision
        for row in tasks
    ):
        raise BusinessError("RESULTS_NOT_READY", "仍有人工阅卷任务未完成")
