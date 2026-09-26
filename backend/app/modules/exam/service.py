from copy import deepcopy
from decimal import Decimal
from app.core.clock import utc_now

from app.core.contracts import Page
from app.core.errors import BusinessError
from app.modules.identity import service as identity_service
from app.modules.attempt import service as attempt_service
from app.modules.identity.types import UserStatus, UserType
from app.modules.paper import service as paper_service
from app.modules.teaching_class import service as class_service
from app.modules.question.schemas import QuestionContent
from app.modules.question import service as question_service
from app.modules.question.types import QuestionStatus, QuestionType
from . import crud
from .models import Exam, ExamParticipant, ExamQuestion
from .schemas import (
    ExamDetail,
    ExamQuestionPublic,
    ExamSummary,
    SnapshotEdit,
    ParticipantPublic,
    ParticipantAddResult,
)
from .types import AudienceType, ExamStatus, ParticipantStatus


async def require_exam(session, exam_id, *, lock=False):
    item = await crud.by_id(session, exam_id, lock=lock)
    if item is None:
        raise BusinessError("EXAM_NOT_FOUND", "考试不存在")
    return item


async def detail(session, item):
    grader_ids = list(await crud.graders(session, item.id))
    teachers = await identity_service.summaries(session, grader_ids)
    return ExamDetail(
        **ExamSummary.model_validate(item).model_dump(),
        questions=[
            ExamQuestionPublic.model_validate(row) for row in await crud.questions(session, item.id)
        ],
        grader_ids=grader_ids,
        graders=[teachers[value] for value in grader_ids],
    )


async def create_exam(session, identity, payload):
    async with session.begin():
        await identity_service.validate_content_actor(session, identity)
        paper = await paper_service.copy_for_exam(session, payload.source_paper_id)
        item = Exam(
            creator_id=identity.user.id, **payload.model_dump(), total_score=paper.total_score
        )
        questions = []
        for row in paper.questions:
            content = QuestionContent.model_validate(row.question.model_dump()).model_dump(
                mode="json"
            )
            questions.append(
                ExamQuestion(
                    exam_id=item.id,
                    source_question_id=row.question_id,
                    source_paper_question_id=row.id,
                    order_no=row.order_no,
                    score=row.score,
                    **deepcopy(content),
                )
            )
            if row.question.status == QuestionStatus.CLOSED:
                item.warnings.append(f"来源题目 {row.question_id} 已关闭，已按既有试卷复制")
        await crud.insert(session, item, questions)
        identity_service.record_audit(
            session,
            actor_id=identity.user.id,
            action="EXAM_CREATED",
            entity_type="exam",
            entity_id=item.id,
            after_data={"source_paper_id": str(paper.id)},
        )
        result = await detail(session, item)
    return result


async def get_exam(session, identity, exam_id):
    identity_service.ensure_role(identity.user, UserType.ADMIN, UserType.TEACHER)
    return await detail(session, await require_exam(session, exam_id, lock=True))


async def list_exams(session, identity, pagination, status):
    identity_service.ensure_role(identity.user, UserType.ADMIN, UserType.TEACHER)
    rows, total = await crud.list_page(session, pagination, status)
    return Page[ExamSummary](
        items=[ExamSummary.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def ensure_version(item, version):
    if item.version != version:
        raise BusinessError("VERSION_CONFLICT", "考试已被修改，请重新读取")


async def validate_graders(session, ids):
    users = await identity_service.locked_summaries(session, set(ids))
    if len(users) != len(set(ids)) or any(
        user.user_type != UserType.TEACHER or user.status != UserStatus.ACTIVATED
        for user in users.values()
    ):
        raise BusinessError("INVALID_TEACHER", "指定阅卷教师必须处于激活状态")


async def update_exam(session, identity, exam_id, payload):
    async with session.begin():
        await identity_service.validate_content_actor(session, identity)
        item = await require_exam(session, exam_id, lock=True)
        ensure_version(item, payload.version)
        if item.status != ExamStatus.DRAFT:
            raise BusinessError("EXAM_LOCKED", "考试发布后不能修改题目或配置")
        await validate_graders(session, payload.grader_ids)
        old = {row.id: row for row in await crud.questions(session, exam_id)}
        source_ids = {
            row.source_question_id
            for row in payload.questions
            if row.source_question_id and not (isinstance(row, SnapshotEdit) and row.id)
        }
        sources = await question_service.copyable_questions(session, source_ids)
        desired = []
        for order_no, value in enumerate(payload.questions, 1):
            existing_id = value.id if isinstance(value, SnapshotEdit) else None
            if existing_id:
                row = old.get(existing_id)
                if row is None or row.source_question_id != value.source_question_id:
                    raise BusinessError("INVALID_SNAPSHOT", "快照题目不属于本场考试或来源被修改")
            else:
                row = ExamQuestion(
                    exam_id=exam_id,
                    source_question_id=value.source_question_id,
                    order_no=order_no,
                    score=value.score,
                )
            content = (
                value if isinstance(value, SnapshotEdit) else sources[value.source_question_id]
            )
            for name, field_value in (
                QuestionContent.model_validate(content.model_dump()).model_dump(mode="json").items()
            ):
                setattr(row, name, deepcopy(field_value))
            row.order_no = order_no
            row.score = value.score
            row.updated_at = utc_now()
            desired.append(row)
        await crud.replace_questions(session, exam_id, desired)
        await crud.replace_graders(session, exam_id, payload.grader_ids, identity.user.id)
        for name, value in payload.model_dump(
            exclude={"version", "questions", "grader_ids"}
        ).items():
            setattr(item, name, value)
        item.total_score = sum((row.score for row in desired), Decimal("0.0"))
        item.version += 1
        item.content_revision += 1
        item.updated_at = utc_now()
        identity_service.record_audit(
            session,
            actor_id=identity.user.id,
            action="EXAM_DRAFT_UPDATED",
            entity_type="exam",
            entity_id=item.id,
            after_data={"version": item.version},
        )
        result = await detail(session, item)
    return result


async def change_release(session, identity, exam_id, payload, *, withdraw=False):
    async with session.begin():
        await identity_service.validate_content_actor(session, identity)
        item = await require_exam(session, exam_id, lock=True)
        ensure_version(item, payload.version)
        if withdraw:
            if item.status != ExamStatus.RELEASED:
                raise BusinessError("EXAM_STATE_INVALID", "仅已发布考试可撤回发布")
            if await attempt_service.has_started(
                session, await crud.participant_ids(session, exam_id)
            ):
                raise BusinessError("EXAM_ALREADY_STARTED", "已有开始作答记录，不能撤回考试发布")
            item.status = ExamStatus.DRAFT
            item.released_at = None
        else:
            if item.status != ExamStatus.DRAFT:
                raise BusinessError("EXAM_STATE_INVALID", "仅草稿考试可发布")
            questions = await crud.questions(session, exam_id)
            if (
                not questions
                or not item.start_at
                or not item.end_at
                or not item.duration_seconds
                or item.start_at >= item.end_at
                or item.end_at <= utc_now()
            ):
                raise BusinessError("EXAM_INCOMPLETE", "发布前须配置题目、有效时间窗口和作答时长")
            grader_ids = await crud.graders(session, exam_id)
            graders = await identity_service.locked_summaries(session, grader_ids)
            active_graders = [
                user
                for user in graders.values()
                if user.user_type == UserType.TEACHER and user.status == UserStatus.ACTIVATED
            ]
            if (
                any(row.type == QuestionType.SHORT_ANSWER for row in questions)
                and not active_graders
            ):
                raise BusinessError("GRADER_REQUIRED", "含简答题须指定至少一名激活阅卷教师")
            item.status = ExamStatus.RELEASED
            item.released_at = utc_now()
        item.version += 1
        item.updated_at = utc_now()
        identity_service.record_audit(
            session,
            actor_id=identity.user.id,
            action="EXAM_WITHDRAWN" if withdraw else "EXAM_RELEASED",
            entity_type="exam",
            entity_id=item.id,
            after_data={"version": item.version, "status": item.status.value},
        )
        result = await detail(session, item)
    return result


def participant_public(row, user, counts):
    return ParticipantPublic(
        id=row.id,
        user=user,
        status=row.status,
        version=row.version,
        assigned_at=row.assigned_at,
        cancelled_at=row.cancelled_at,
        cancelled_reason=row.cancelled_reason,
        used_attempts=counts[0],
        voided_attempts=counts[1],
    )


async def list_participants(session, identity, exam_id, pagination, status):
    identity_service.ensure_role(identity.user, UserType.ADMIN, UserType.TEACHER)
    await require_exam(session, exam_id)
    rows, total = await crud.participant_page(session, exam_id, pagination, status)
    users = await identity_service.summaries(session, [row.user_id for row in rows])
    counts = await attempt_service.participant_attempt_counts(session, [row.id for row in rows])
    return Page[ParticipantPublic](
        items=[
            participant_public(row, users[row.user_id], counts.get(row.id, (0, 0))) for row in rows
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def add_participants(session, identity, exam_id, payload):
    async with session.begin():
        await identity_service.validate_content_actor(session, identity)
        exam = await require_exam(session, exam_id, lock=True)
        if exam.status == ExamStatus.CANCELLED:
            raise BusinessError("EXAM_STATE_INVALID", "已取消考试不能补入名单")
        ids = set(payload.student_ids) | await class_service.expand_exam_students(
            session, payload.class_ids
        )
        users = await identity_service.locked_summaries(session, ids)
        if len(users) != len(ids) or any(
            user.user_type != UserType.STUDENT or user.status != UserStatus.ACTIVATED
            for user in users.values()
        ):
            raise BusinessError("INVALID_MEMBER", "补入名单的学生必须处于激活状态")
        existing = {
            row.user_id: row for row in await crud.participants_for_users(session, exam_id, ids)
        }
        added = [
            ExamParticipant(exam_id=exam_id, user_id=value)
            for value in sorted(ids - existing.keys(), key=str)
        ]
        await crud.add_participants(session, added)
        cancelled = sorted(
            [row.user_id for row in existing.values() if row.status == ParticipantStatus.CANCELLED],
            key=str,
        )
        identity_service.record_audit(
            session,
            actor_id=identity.user.id,
            action="EXAM_PARTICIPANTS_ADDED",
            entity_type="exam",
            entity_id=exam_id,
            after_data={
                "class_ids": [str(value) for value in payload.class_ids],
                "student_ids": [str(value) for value in payload.student_ids],
                "added_user_ids": [str(row.user_id) for row in added],
                "cancelled_user_ids": [str(value) for value in cancelled],
            },
        )
        result = ParticipantAddResult(
            added=len(added), existing=len(existing) - len(cancelled), cancelled_user_ids=cancelled
        )
    return result


async def change_participant(session, identity, exam_id, participant_id, payload, *, restore=False):
    async with session.begin():
        await identity_service.validate_content_actor(session, identity)
        exam = await require_exam(session, exam_id, lock=True)
        if exam.status == ExamStatus.CANCELLED:
            raise BusinessError("EXAM_STATE_INVALID", "已取消考试不能改变资格")
        row = await crud.participant_by_id(session, participant_id)
        if row is None or row.exam_id != exam_id:
            raise BusinessError("PARTICIPANT_NOT_FOUND", "考试资格不存在")
        ensure_version(row, payload.version)
        expected = ParticipantStatus.CANCELLED if restore else ParticipantStatus.ASSIGNED
        if row.status != expected:
            raise BusinessError("PARTICIPANT_STATE_INVALID", "资格状态已经改变，请重新读取")
        users = await identity_service.locked_summaries(session, [row.user_id])
        if restore and users[row.user_id].status != UserStatus.ACTIVATED:
            raise BusinessError("INVALID_MEMBER", "只能恢复已激活学生的资格")
        if restore:
            row.status = ParticipantStatus.ASSIGNED
            row.cancelled_at = None
            row.cancelled_reason = None
        else:
            row.status = ParticipantStatus.CANCELLED
            row.cancelled_at = utc_now()
            row.cancelled_reason = payload.reason
            await attempt_service.void_participant_attempts(session, [row.id], payload.reason)
        row.version += 1
        row.updated_at = utc_now()
        identity_service.record_audit(
            session,
            actor_id=identity.user.id,
            action="EXAM_PARTICIPANT_RESTORED" if restore else "EXAM_PARTICIPANT_CANCELLED",
            entity_type="exam_participant",
            entity_id=row.id,
            reason=payload.reason,
            after_data={"status": row.status.value, "version": row.version},
        )
        counts = await attempt_service.participant_attempt_counts(session, [row.id])
        result = participant_public(row, users[row.user_id], counts.get(row.id, (0, 0)))
    return result


async def ensure_public_start_participant(session, exam_id, student_id):
    """仅供迭代3开始作答顶层用例组合：持有考试锁，幂等创建且尊重显式撤销。"""
    exam = await require_exam(session, exam_id, lock=True)
    if exam.status != ExamStatus.RELEASED or exam.audience_type != AudienceType.PUBLIC:
        raise BusinessError("EXAM_STATE_INVALID", "当前考试不接受公开开始")
    users = await identity_service.locked_summaries(session, [student_id])
    user = users.get(student_id)
    if user is None or user.user_type != UserType.STUDENT or user.status != UserStatus.ACTIVATED:
        raise BusinessError("INVALID_MEMBER", "学生账号未激活")
    rows = await crud.participants_for_users(session, exam_id, [student_id])
    if rows:
        row = rows[0]
        if row.status == ParticipantStatus.CANCELLED:
            raise BusinessError("PARTICIPANT_CANCELLED", "参考资格已撤销")
    else:
        row = ExamParticipant(exam_id=exam_id, user_id=student_id)
        await crud.add_participants(session, [row])
        identity_service.record_audit(
            session,
            actor_id=student_id,
            action="EXAM_PUBLIC_PARTICIPANT_CREATED",
            entity_type="exam_participant",
            entity_id=row.id,
        )
    return row.id
