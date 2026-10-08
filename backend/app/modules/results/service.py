from app.core.contracts import Page
from app.core.errors import BusinessError
from app.modules.attempt import service as attempt_service
from app.modules.attempt.types import AttemptStatus, GradingStatus
from app.modules.exam import result_service as exam_results
from app.modules.exam.types import ExamStatus, ParticipantStatus
from app.modules.identity import service as identity_service
from app.modules.identity.types import UserType
from .schemas import StudentResultSummary, StudentResultDetail, StudentAttemptResult


def result_state(exam, participant):
    """所有学生学习反馈共用可见性判定，撤回与撤销不能被已有标记绕过。"""
    if exam.status == ExamStatus.CANCELLED:
        return "CANCELLED"
    if participant.status != ParticipantStatus.ASSIGNED:
        return "PARTICIPANT_CANCELLED"
    if exam.status == ExamStatus.RESULTS_PUBLISHED:
        return "PUBLISHED"
    return "CORRECTING" if exam.results_withdrawn_at else "NOT_PUBLISHED"


def can_read_results(exam, participant):
    return result_state(exam, participant) == "PUBLISHED"


def can_review(exam, participant):
    return can_read_results(exam, participant) and exam.allow_review


async def require_context(session, student_id, exam_id, *, review=False):
    contexts = await exam_results.student_contexts(session, student_id, exam_id)
    if not contexts:
        raise BusinessError("EXAM_NOT_FOUND", "没有本人考试记录")
    exam, participant = contexts[0]
    if not can_read_results(exam, participant):
        raise BusinessError("RESULTS_HIDDEN", "结果尚未公布、正在更正或已失效")
    if review and not exam.allow_review:
        raise BusinessError("REVIEW_FORBIDDEN", "本场考试不允许回看答卷")
    return exam, participant


def valid_attempts(exam, participant, attempts):
    if exam.status == ExamStatus.CANCELLED or participant.status != ParticipantStatus.ASSIGNED:
        return []
    return [row for row in attempts if row.status != AttemptStatus.VOID]


def summary(exam, participant, attempts):
    rows = valid_attempts(exam, participant, attempts)
    submitted = [row for row in rows if row.status == AttemptStatus.SUBMITTED]
    # 必须先取最后提交，再判断评分完成；不能回退到较早已判完的一次。
    final = max(submitted, key=lambda row: row.attempt_no, default=None)
    visible = can_read_results(exam, participant)
    complete = (
        final
        and final.grading_status == GradingStatus.GRADED
        and final.grading_revision == exam.grading_revision
    )
    return StudentResultSummary(
        exam_id=exam.id,
        title=exam.title,
        exam_status=exam.status,
        result_state=result_state(exam, participant),
        participant_status=participant.status,
        end_at=exam.end_at,
        total_score=exam.total_score,
        allow_review=exam.allow_review,
        can_review=can_review(exam, participant),
        attempts_count=len(rows),
        final_attempt_id=final.id if final else None,
        final_attempt_no=final.attempt_no if final else None,
        grading_status=final.grading_status if final else None,
        final_score=final.final_score if visible and complete else None,
        submitted_at=final.submitted_at if final else None,
    )


async def list_results(session, identity, pagination):
    async with session.begin():
        await identity_service.validate_shared_actor(session, identity, UserType.STUDENT)
        contexts, total = await exam_results.student_context_page(
            session, identity.user.id, pagination
        )
        attempts = await attempt_service.grading_attempts(session, [row.id for _, row in contexts])
        by_participant = {row.id: [] for _, row in contexts}
        for attempt in attempts:
            by_participant[attempt.exam_participant_id].append(attempt)
        items = [
            summary(exam, participant, by_participant[participant.id])
            for exam, participant in contexts
        ]
    return Page[StudentResultSummary](
        items=items, total=total, page=pagination.page, page_size=pagination.page_size
    )


async def get_result(session, identity, exam_id):
    async with session.begin():
        await identity_service.validate_shared_actor(session, identity, UserType.STUDENT)
        contexts = await exam_results.student_contexts(session, identity.user.id, exam_id)
        if not contexts:
            raise BusinessError("EXAM_NOT_FOUND", "没有本人考试记录")
        exam, participant = contexts[0]
        attempts = valid_attempts(
            exam, participant, await attempt_service.grading_attempts(session, [participant.id])
        )
        overview = summary(exam, participant, attempts)
        rows = [
            StudentAttemptResult(
                id=row.id,
                attempt_no=row.attempt_no,
                status=row.status,
                started_at=row.started_at,
                submitted_at=row.submitted_at,
                grading_status=row.grading_status,
                final_score=row.final_score
                if can_read_results(exam, participant)
                and row.grading_status == GradingStatus.GRADED
                and row.grading_revision == exam.grading_revision
                else None,
                can_review=can_review(exam, participant) and row.status == AttemptStatus.SUBMITTED,
            )
            for row in attempts
        ]
        result = StudentResultDetail(**overview.model_dump(), attempts=rows)
    return result
