import re

from app.core.errors import BusinessError
from app.modules.attempt import service as attempt_service, result_service as attempt_results
from app.modules.attempt.types import AttemptStatus, GradingStatus
from app.modules.exam import service as exam_service, result_service as exam_results
from app.modules.identity import service as identity_service
from app.modules.identity.types import UserType
from . import service
from .schemas import ReviewAnswer, ReviewQuestion, StudentReview


async def attempt_context(session, student_id, attempt_id):
    """仅定位归属，持有考试共享锁后再读答卷，避免撤回或废弃期间沿用旧对象。"""
    reference = await attempt_service.grading_attempt(session, attempt_id)
    if reference is None:
        raise BusinessError("ATTEMPT_NOT_FOUND", "没有本人答卷")
    participants, _ = await exam_service.grading_contexts(session, [reference.exam_participant_id])
    participant = participants.get(reference.exam_participant_id)
    if participant is None or participant.user_id != student_id:
        raise BusinessError("ATTEMPT_NOT_FOUND", "没有本人答卷")
    exam, participant = await service.require_context(
        session, student_id, participant.exam_id, review=True
    )
    attempt = await attempt_results.refreshed_attempt(session, attempt_id)
    if attempt.status != AttemptStatus.SUBMITTED:
        raise BusinessError("RESULTS_HIDDEN", "该作答尚未提交或已失效")
    if (
        attempt.grading_status != GradingStatus.GRADED
        or attempt.grading_revision != exam.grading_revision
    ):
        raise BusinessError("RESULTS_HIDDEN", "该作答尚未按当前依据判完")
    return exam, participant, attempt


def question_dto(question, answer, display_order=None, option_order=None):
    options = question.options
    if option_order:
        by_id = {str(row["id"]): row for row in options}
        options = [by_id[value] for value in option_order]
    return ReviewQuestion(
        id=question.id,
        order_no=question.order_no,
        display_order=display_order or question.order_no,
        type=question.type,
        content=question.content,
        options=options,
        standard_answer=question.standard_answer,
        explanation=question.explanation,
        subject=question.subject,
        knowledge_tags=question.knowledge_tags,
        difficulty=question.difficulty,
        score=question.score,
        answer=ReviewAnswer(
            id=answer.id,
            answer_data=answer.answer_data,
            grading_status=answer.grading_status,
            score=answer.score,
            is_correct=answer.is_correct,
            grader_comment=answer.grader_comment,
        ),
    )


async def get_review(session, identity, attempt_id):
    async with session.begin():
        await identity_service.validate_shared_actor(session, identity, UserType.STUDENT)
        exam, _, attempt = await attempt_context(session, identity.user.id, attempt_id)
        questions = {row.id: row for row in await exam_service.attempt_questions(session, exam.id)}
        answers = {
            row.exam_question_id: row
            for row in await attempt_results.answers(session, [attempt.id])
        }
        orders = await attempt_results.orders(session, attempt.id)
        result = StudentReview(
            id=attempt.id,
            exam_id=exam.id,
            exam_title=exam.title,
            attempt_no=attempt.attempt_no,
            submitted_at=attempt.submitted_at,
            total_score=exam.total_score,
            final_score=attempt.final_score,
            questions=[
                question_dto(
                    questions[row.exam_question_id],
                    answers[row.exam_question_id],
                    row.display_order,
                    row.option_order,
                )
                for row in orders
            ],
        )
    return result


async def can_read_asset(session, student_id, asset_id):
    """可组合图片授权：仅已公布、允许回看的本人有效提交所引用的独立快照。"""
    contexts = [
        row
        for row in await exam_results.student_contexts(session, student_id)
        if service.can_review(*row)
    ]
    if not contexts:
        return False
    attempts = await attempt_service.grading_attempts(
        session, [participant.id for _, participant in contexts]
    )
    submitted_participants = {
        row.exam_participant_id for row in attempts if row.status == AttemptStatus.SUBMITTED
    }
    exam_ids = [
        exam.id for exam, participant in contexts if participant.id in submitted_participants
    ]
    reference = re.compile(rf"/api/assets/{asset_id}(?=$|[\s)\]\"'<>?#])", re.IGNORECASE)
    for question in await exam_results.questions_for_exams(session, exam_ids):
        texts = [question.content, question.explanation or ""]
        texts.extend(row["content"] for row in question.options)
        if isinstance(question.standard_answer, str):
            texts.append(question.standard_answer)
        if any(reference.search(value) for value in texts):
            return True
    return False
