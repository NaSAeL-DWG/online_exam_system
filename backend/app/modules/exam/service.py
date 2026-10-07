from copy import deepcopy
from decimal import Decimal
from pydantic import ValidationError
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
    StudentExamSummary,
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
            item.grading_assignment_pending = any(
                row.type == QuestionType.SHORT_ANSWER for row in questions
            )
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
    user_ids = None
    if pagination.q.strip():
        user_ids = await identity_service.filter_user_ids(
            session, await crud.participant_user_ids(session, exam_id), pagination.q
        )
    rows, total = await crud.participant_page(session, exam_id, pagination, status, user_ids)
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


def student_summary(exam, participant, counts, current, now):
    used = counts[0]
    reason = None
    if participant and participant.status == ParticipantStatus.CANCELLED:
        reason = "PARTICIPANT_CANCELLED"
    elif exam.status == ExamStatus.CANCELLED:
        reason = "EXAM_CANCELLED"
    elif now < exam.start_at:
        reason = "EXAM_NOT_STARTED"
    elif now >= exam.end_at:
        reason = "EXAM_ENDED"
    elif used >= exam.max_attempts and not (
        current and current.status.value == "IN_PROGRESS" and current.deadline_at > now
    ):
        reason = "ATTEMPTS_EXHAUSTED"
    return StudentExamSummary(
        id=exam.id,
        title=exam.title,
        description=exam.description,
        audience_type=exam.audience_type,
        status=exam.status,
        start_at=exam.start_at,
        end_at=exam.end_at,
        duration_seconds=exam.duration_seconds,
        max_attempts=exam.max_attempts,
        total_score=exam.total_score,
        server_now=now,
        participant_status=participant.status if participant else None,
        cancelled_reason=participant.cancelled_reason
        if participant and participant.status == ParticipantStatus.CANCELLED
        else exam.cancelled_reason,
        used_attempts=used,
        remaining_attempts=max(0, exam.max_attempts - used),
        current_attempt_id=current.id if current else None,
        current_attempt_status=current.status.value if current else None,
        can_start=reason is None,
        unavailable_reason=reason,
    )


async def list_student_exams(session, identity, pagination):
    identity_service.ensure_role(identity.user, UserType.STUDENT)
    rows, total = await crud.student_page(session, identity.user.id, pagination)
    participant_ids = [participant.id for _, participant in rows if participant]
    counts = await attempt_service.participant_attempt_counts(session, participant_ids)
    current = await attempt_service.current_participant_attempts(session, participant_ids)
    now = utc_now()
    return Page[StudentExamSummary](
        items=[
            student_summary(
                exam,
                participant,
                counts.get(participant.id, (0, 0)) if participant else (0, 0),
                current.get(participant.id) if participant else None,
                now,
            )
            for exam, participant in rows
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def get_student_exam(session, identity, exam_id):
    identity_service.ensure_role(identity.user, UserType.STUDENT)
    exam = await require_exam(session, exam_id)
    rows = await crud.participants_for_users(session, exam_id, [identity.user.id])
    participant = rows[0] if rows else None
    if (
        exam.status == ExamStatus.DRAFT
        or (exam.audience_type == AudienceType.RESTRICTED and not participant)
        or (exam.status == ExamStatus.CANCELLED and not participant)
    ):
        raise BusinessError("EXAM_NOT_FOUND", "考试不存在")
    ids = [participant.id] if participant else []
    counts = await attempt_service.participant_attempt_counts(session, ids)
    current = await attempt_service.current_participant_attempts(session, ids)
    return student_summary(
        exam,
        participant,
        counts.get(participant.id, (0, 0)) if participant else (0, 0),
        current.get(participant.id) if participant else None,
        utc_now(),
    )


async def prepare_student_start(session, identity, exam_id):
    """可组合开始能力：身份共享锁后按考试、资格顺序锁定，公开资格仅在实际开始建立。"""
    await identity_service.validate_shared_actor(session, identity, UserType.STUDENT)
    exam = await require_exam(session, exam_id, lock=True)
    if exam.status == ExamStatus.CANCELLED:
        raise BusinessError("EXAM_CANCELLED", "考试已取消")
    if exam.status != ExamStatus.RELEASED:
        raise BusinessError("EXAM_STATE_INVALID", "考试未开放作答")
    now = utc_now()
    participant = await crud.participant_for_user(session, exam_id, identity.user.id)
    if participant is None and exam.audience_type == AudienceType.PUBLIC:
        if now < exam.start_at:
            raise BusinessError("EXAM_NOT_STARTED", "考试尚未开始")
        if now >= exam.end_at:
            raise BusinessError("EXAM_ENDED", "考试已经结束")
        participant = ExamParticipant(exam_id=exam_id, user_id=identity.user.id)
        await crud.add_participants(session, [participant])
        identity_service.record_audit(
            session,
            actor_id=identity.user.id,
            action="EXAM_PUBLIC_PARTICIPANT_CREATED",
            entity_type="exam_participant",
            entity_id=participant.id,
        )
    if participant is None:
        raise BusinessError("PARTICIPANT_REQUIRED", "没有本场考试参考资格")
    if participant.status == ParticipantStatus.CANCELLED:
        raise BusinessError("PARTICIPANT_CANCELLED", "参考资格已撤销")
    return exam, participant, await crud.questions(session, exam_id)


async def locked_attempt_context(session, participant_id, identity=None):
    """公开作答协调能力：先定位归属，再按考试、资格顺序重读锁定。"""
    if identity:
        await identity_service.validate_shared_actor(session, identity, UserType.STUDENT)
    reference = await crud.participant_by_id(session, participant_id, lock=False)
    if reference is None or (identity and reference.user_id != identity.user.id):
        raise BusinessError("ATTEMPT_NOT_FOUND", "作答不存在")
    exam = await require_exam(session, reference.exam_id, lock=True)
    participant = await crud.participant_by_id(session, participant_id)
    if identity:
        if participant.status == ParticipantStatus.CANCELLED:
            raise BusinessError("PARTICIPANT_CANCELLED", "参考资格已撤销")
        if exam.status == ExamStatus.CANCELLED:
            raise BusinessError("EXAM_CANCELLED", "考试已取消")
    return exam, participant


async def attempt_questions(session, exam_id):
    """合法作答用例的快照读取能力；调用方已持有考试与资格锁。"""
    return await crud.questions(session, exam_id)


async def attempt_question(session, exam_id, question_id):
    """单题保存只读取目标题快照，避免每次自动保存加载整场Markdown和评分依据。"""
    question = await crud.question_by_id(session, exam_id, question_id)
    if question is None:
        raise BusinessError("ANSWER_NOT_FOUND", "答案对应的考试题目不存在")
    return question


async def cancel_exam(session, identity, exam_id, payload):
    async with session.begin():
        await identity_service.validate_content_actor(session, identity)
        exam = await require_exam(session, exam_id, lock=True)
        ensure_version(exam, payload.version)
        if exam.status == ExamStatus.CANCELLED:
            raise BusinessError("EXAM_CANCELLED", "已取消考试不可恢复或再次取消")
        previous_status = exam.status
        exam.status = ExamStatus.CANCELLED
        exam.cancelled_at = utc_now()
        exam.cancelled_reason = payload.reason
        exam.version += 1
        exam.updated_at = utc_now()
        await attempt_service.void_participant_attempts(
            session, await crud.participant_ids(session, exam_id), payload.reason
        )
        identity_service.record_audit(
            session,
            actor_id=identity.user.id,
            action="EXAM_CANCELLED",
            entity_type="exam",
            entity_id=exam.id,
            reason=payload.reason,
            before_data={"status": previous_status.value},
            after_data={"status": exam.status.value, "version": exam.version},
        )
        result = await detail(session, exam)
    return result


async def grading_participants(session, exam_id, *, lock=False):
    """评分用例批量资格读取，考试锁始终先于资格锁。"""
    return await crud.grading_participants(session, exam_id, lock=lock)


async def grading_teacher_ids(session, exam_id):
    """返回配置的指定教师，任务分配不得自行扩展名单。"""
    return list(await crud.graders(session, exam_id))


async def ended_grading_exam_ids(session, limit=100):
    """后台扫描已结束的发布考试，具体待分配状态由阅卷用例检查。"""
    return await crud.ended_exam_ids(session, utc_now(), limit)


async def grading_contexts(session, participant_ids):
    """任务分页批量读取资格与考试，避免逐任务查询。"""
    participants = await crud.participants_by_ids(session, participant_ids)
    exams = await crud.exams_by_ids(session, {row.exam_id for row in participants})
    return {row.id: row for row in participants}, {row.id: row for row in exams}


async def grading_participant_page(session, exam_id, pagination):
    """成绩列表只纳入当前有效资格，姓名与账号筛选由身份公开能力完成。"""
    user_ids = None
    if pagination.q.strip():
        user_ids = await identity_service.filter_user_ids(
            session, await crud.participant_user_ids(session, exam_id), pagination.q
        )
    return await crud.participant_page(
        session, exam_id, pagination, ParticipantStatus.ASSIGNED, user_ids
    )


async def correct_grading_standard(session, identity, exam, question_id, payload):
    """专门更正评分依据，调用方持有考试锁并负责全部受影响答卷事务。"""
    ensure_version(exam, payload.version)
    if exam.status == ExamStatus.RESULTS_PUBLISHED:
        raise BusinessError("RESULTS_WITHDRAW_REQUIRED", "已公布结果须先撤回再更正评分依据")
    if exam.status != ExamStatus.RELEASED:
        raise BusinessError("EXAM_STATE_INVALID", "仅已发布的有效考试可专门更正评分依据")
    question = await crud.question_by_id(session, exam.id, question_id)
    if question is None:
        raise BusinessError("QUESTION_NOT_FOUND", "考试快照题目不存在")
    if question.grading_revision != payload.grading_revision:
        raise BusinessError("VERSION_CONFLICT", "评分依据已更新，请重新读取")
    try:
        QuestionContent.model_validate(
            question.model_dump()
            | {"standard_answer": payload.standard_answer, "explanation": payload.explanation}
        )
    except ValidationError:
        raise BusinessError("INVALID_ANSWER", "更正后的评分依据不符合题型或选项约束") from None
    before = {
        "standard_answer": question.standard_answer,
        "explanation": question.explanation,
        "grading_revision": question.grading_revision,
    }
    exam.grading_revision += 1
    exam.grading_assignment_pending = True
    exam.version += 1
    exam.updated_at = utc_now()
    question.standard_answer = deepcopy(payload.standard_answer)
    question.explanation = payload.explanation
    question.grading_revision = exam.grading_revision
    question.updated_at = utc_now()
    identity_service.record_audit(
        session,
        actor_id=identity.user.id,
        action="EXAM_STANDARD_CORRECTED",
        entity_type="exam_question",
        entity_id=question.id,
        reason=payload.reason,
        before_data=before,
        after_data={
            "standard_answer": question.standard_answer,
            "explanation": question.explanation,
            "grading_revision": question.grading_revision,
        },
    )
    return question


async def withdraw_results(session, identity, exam_id, payload):
    """更正前撤回既有公布结果；完整公布与学生成绩入口留给迭代5。"""
    async with session.begin():
        await identity_service.validate_content_actor(session, identity)
        exam = await require_exam(session, exam_id, lock=True)
        ensure_version(exam, payload.version)
        if exam.status != ExamStatus.RESULTS_PUBLISHED:
            raise BusinessError("EXAM_STATE_INVALID", "仅已公布结果可以撤回")
        exam.status = ExamStatus.RELEASED
        exam.results_withdrawn_at = utc_now()
        exam.results_withdraw_reason = payload.reason
        exam.version += 1
        exam.updated_at = utc_now()
        identity_service.record_audit(
            session,
            actor_id=identity.user.id,
            action="EXAM_RESULTS_WITHDRAWN",
            entity_type="exam",
            entity_id=exam.id,
            reason=payload.reason,
            before_data={"status": ExamStatus.RESULTS_PUBLISHED.value},
            after_data={"status": exam.status.value, "version": exam.version},
        )
        result = await detail(session, exam)
    return result
