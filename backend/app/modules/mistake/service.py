from app.core.contracts import Page
from app.core.errors import BusinessError
from app.modules.attempt import service as attempt_service, result_service as attempt_results
from app.modules.attempt.types import AttemptStatus, GradingStatus
from app.modules.exam import result_service as exam_results
from app.modules.exam import service as exam_service
from app.modules.identity import service as identity_service
from app.modules.identity.types import UserType
from app.modules.results import service as results_service, review
from . import crud
from .schemas import AnnotationPublic, MistakeSummary, MistakeDetail


async def visible_data(session, student_id):
    """公开可组合学习查询，错题来自全部可回看的当前有效提交，不能只取最后一次。"""
    contexts = [
        row
        for row in await exam_results.student_contexts(session, student_id)
        if results_service.can_review(*row)
    ]
    by_participant = {participant.id: exam for exam, participant in contexts}
    attempts = {
        row.id: row
        for row in await attempt_service.grading_attempts(session, by_participant)
        if row.status == AttemptStatus.SUBMITTED
        and row.grading_status == GradingStatus.GRADED
        and row.grading_revision == by_participant[row.exam_participant_id].grading_revision
    }
    return by_participant, attempts


def summary(exam, attempt, question, answer, annotation):
    return MistakeSummary(
        answer_id=answer.id,
        attempt_id=attempt.id,
        attempt_no=attempt.attempt_no,
        exam_id=exam.id,
        exam_title=exam.title,
        submitted_at=attempt.submitted_at,
        question_id=question.id,
        type=question.type,
        subject=question.subject,
        knowledge_tags=question.knowledge_tags,
        content=question.content,
        score=answer.score,
        full_score=question.score,
        note=annotation.note if annotation else None,
        mastered=annotation.mastered if annotation else False,
    )


async def list_mistakes(session, identity, pagination, subject, kind, knowledge_tag, mastered):
    async with session.begin():
        await identity_service.validate_shared_actor(session, identity, UserType.STUDENT)
        exams, attempts = await visible_data(session, identity.user.id)
        search = pagination.q.strip().casefold()
        title_exam_ids = [exam.id for exam in exams.values() if search in exam.title.casefold()]
        allowed = await exam_results.mistake_question_ids(
            session,
            [exam.id for exam in exams.values()],
            subject,
            kind,
            knowledge_tag,
            pagination.q,
            title_exam_ids,
        )
        mastered_ids = (
            await crud.mastered_ids(session, identity.user.id) if mastered is not None else None
        )
        answers, total = await attempt_results.mistake_page(
            session, list(attempts), allowed, pagination, mastered, mastered_ids
        )
        questions = {
            row.id: row
            for row in await exam_results.question_summaries_by_ids(
                session, [row.exam_question_id for row in answers]
            )
        }
        annotations = {
            row.answer_id: row
            for row in await crud.annotations(
                session, identity.user.id, [row.id for row in answers]
            )
        }
        items = [
            summary(
                exams[attempts[row.attempt_id].exam_participant_id],
                attempts[row.attempt_id],
                questions[row.exam_question_id],
                row,
                annotations.get(row.id),
            )
            for row in answers
        ]
    return Page[MistakeSummary](
        items=items, total=total, page=pagination.page, page_size=pagination.page_size
    )


async def require_mistake(session, student_id, answer_id):
    reference = await attempt_service.grading_answer_reference(session, answer_id)
    if reference is None:
        raise BusinessError("MISTAKE_NOT_FOUND", "没有当前可见的本人错题")
    try:
        exam, _, attempt = await review.attempt_context(session, student_id, reference.attempt_id)
    except BusinessError as exc:
        if exc.code in {
            "ATTEMPT_NOT_FOUND",
            "EXAM_NOT_FOUND",
            "RESULTS_HIDDEN",
            "REVIEW_FORBIDDEN",
        }:
            raise BusinessError("MISTAKE_NOT_FOUND", "没有当前可见的本人错题") from None
        raise
    answer = await attempt_results.refreshed_answer(session, answer_id)
    question = await exam_service.attempt_question(session, exam.id, answer.exam_question_id)
    if (
        answer.grading_status != GradingStatus.GRADED
        or answer.grading_revision != question.grading_revision
        or answer.score is None
        or answer.score >= question.score
    ):
        raise BusinessError("MISTAKE_NOT_FOUND", "该题已取得满分或尚未完成当前评分")
    return exam, attempt, question, answer


async def get_mistake(session, identity, answer_id):
    async with session.begin():
        await identity_service.validate_shared_actor(session, identity, UserType.STUDENT)
        exam, attempt, question, answer = await require_mistake(
            session, identity.user.id, answer_id
        )
        annotations = await crud.annotations(session, identity.user.id, [answer_id])
        item = summary(exam, attempt, question, answer, annotations[0] if annotations else None)
        orders = await attempt_results.orders(session, attempt.id)
        order = next(row for row in orders if row.exam_question_id == question.id)
        result = MistakeDetail(
            **item.model_dump(),
            question=review.question_dto(question, answer, order.display_order, order.option_order),
        )
    return result


async def annotate(session, identity, answer_id, payload):
    async with session.begin():
        await identity_service.validate_shared_actor(session, identity, UserType.STUDENT)
        await require_mistake(session, identity.user.id, answer_id)
        await crud.save_annotation(
            session, identity.user.id, answer_id, payload.note, payload.mastered
        )
    return AnnotationPublic(note=payload.note, mastered=payload.mastered)
