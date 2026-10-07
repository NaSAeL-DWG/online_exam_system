from decimal import Decimal, ROUND_HALF_UP

from app.core.clock import utc_now
from app.core.contracts import Page

from app.core.errors import BusinessError
from app.modules.exam.types import MultipleChoiceMode
from app.modules.question.types import QuestionType
from app.modules.attempt import service as attempt_service
from app.modules.attempt.types import AttemptStatus, GradingMethod, GradingStatus
from app.modules.exam import service as exam_service
from app.modules.exam.types import ExamStatus, ParticipantStatus
from app.modules.identity import service as identity_service
from app.modules.identity.types import UserStatus, UserType
from . import crud
from .models import GradingHistory, GradingTask
from .schemas import (
    AnswerPublic,
    AttemptDetail,
    AttemptSummary,
    FinalResult,
    GradingQuestion,
    HistoryPublic,
    HistoryResponse,
    RefreshResult,
    TaskPublic,
    TaskSummary,
)
from .types import TaskStatus


def automatic_score(kind, option_ids, standard, answer, full_score, mode):
    """公开纯判分能力：非空简答返回待人工，其余题分四舍五入到一位小数。"""
    zero = Decimal("0.0")
    if answer is None or (type(answer) is str and not answer.strip()) or answer == []:
        return zero
    if kind == QuestionType.SHORT_ANSWER:
        return None
    if kind in (QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE):
        if (
            not isinstance(answer, list)
            or any(type(value) is not str for value in answer)
            or len(set(answer)) != len(answer)
            or not set(answer) <= set(option_ids)
            or (kind == QuestionType.SINGLE_CHOICE and len(answer) != 1)
        ):
            raise BusinessError("INVALID_ANSWER", "选项ID无效或重复")
        chosen, correct = set(answer), set(standard)
        if chosen == correct:
            return full_score
        if (
            kind == QuestionType.MULTIPLE_CHOICE
            and mode == MultipleChoiceMode.PARTIAL
            and chosen <= correct
        ):
            return (full_score * Decimal(len(chosen)) / Decimal(len(correct))).quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            )
        return zero
    if type(answer) is not bool:
        raise BusinessError("INVALID_ANSWER", "判断题答案必须为布尔值")
    return full_score if answer == standard else zero


def valid_submission(exam, participant, attempt):
    return (
        exam.status != ExamStatus.CANCELLED
        and participant.status == ParticipantStatus.ASSIGNED
        and attempt.status == AttemptStatus.SUBMITTED
    )


async def locked_context(session, attempt_id):
    reference = await attempt_service.grading_attempt(session, attempt_id)
    if reference is None:
        raise BusinessError("ATTEMPT_NOT_FOUND", "答卷不存在")
    exam, participant = await exam_service.locked_attempt_context(
        session, reference.exam_participant_id
    )
    attempt = await attempt_service.grading_attempt(session, attempt_id, lock=True)
    return exam, participant, attempt


def save_score(session, answer, question, score, method, actor_id=None, comment=None, reason=None):
    """评分与不可变前后值历史在同一顶层事务持久化。"""
    now = utc_now()
    crud.add_history(
        session,
        GradingHistory(
            answer_id=answer.id,
            grading_revision=question.grading_revision,
            answer_version=answer.version + 1,
            actor_id=actor_id,
            method=method,
            old_score=answer.score,
            new_score=score,
            old_is_correct=answer.is_correct,
            new_is_correct=score == question.score,
            old_comment=answer.grader_comment,
            new_comment=comment,
            reason=reason,
        ),
    )
    answer.score = score
    answer.is_correct = score == question.score
    answer.grader_comment = comment
    answer.graded_by = actor_id
    answer.grading_method = method
    answer.grading_revision = question.grading_revision
    answer.grading_status = GradingStatus.GRADED
    answer.graded_at = now
    answer.updated_at = now
    answer.version += 1


def aggregate_attempt(attempt, questions, answers, task=None):
    """单题依赖各自修订；全局修订推进不会令无关简答重新阅卷。"""
    snapshots = {question.id: question for question in questions}
    complete = all(
        answer.grading_status == GradingStatus.GRADED
        and answer.grading_revision == snapshots[answer.exam_question_id].grading_revision
        for answer in answers
    )
    now = utc_now()
    pending_automatic = any(
        answer.grading_status != GradingStatus.GRADED
        and (
            snapshots[answer.exam_question_id].type != QuestionType.SHORT_ANSWER
            or answer.answer_data is None
        )
        for answer in answers
    )
    attempt.grading_status = (
        GradingStatus.GRADED
        if complete
        else (GradingStatus.PENDING if pending_automatic else GradingStatus.GRADING)
    )
    attempt.final_score = (
        sum((answer.score for answer in answers), Decimal("0.0")) if complete else None
    )
    attempt.graded_at = now if complete else None
    attempt.updated_at = now
    attempt.version += 1
    if task is not None and complete:
        task.status = TaskStatus.COMPLETED
        task.completed_at = now
        if task.first_review_completed_at is None:
            task.first_review_completed_at = now
        task.version += 1
        task.updated_at = now


async def grade_attempt(session, attempt_id, revision=None):
    """后台顶层自动评分：重查有效性与目标修订，重复任务不改人工结果。"""
    async with session.begin():
        reference = await attempt_service.grading_attempt(session, attempt_id)
        if reference is None:
            return False
        exam, participant, attempt = await locked_context(session, attempt_id)
        if not valid_submission(exam, participant, attempt) or (
            revision is not None and revision != exam.grading_revision
        ):
            return False
        if (
            attempt.grading_revision != exam.grading_revision
            or attempt.grading_status != GradingStatus.PENDING
        ):
            return False
        questions = await exam_service.attempt_questions(session, exam.id)
        task = await crud.task_for_attempt(session, attempt.id, lock=True)
        answers = await attempt_service.grading_answers(session, attempt.id)
        snapshots = {question.id: question for question in questions}
        for answer in answers:
            question = snapshots[answer.exam_question_id]
            if (
                answer.grading_status == GradingStatus.GRADED
                and answer.grading_revision == question.grading_revision
            ):
                continue
            score = automatic_score(
                question.type,
                [str(option["id"]) for option in question.options],
                question.standard_answer,
                answer.answer_data,
                question.score,
                exam.multiple_choice_mode,
            )
            if score is not None:
                save_score(
                    session,
                    answer,
                    question,
                    score,
                    GradingMethod.AUTO,
                    reason="评分依据自动重判" if answer.score is not None else None,
                )
            else:
                answer.grading_status = GradingStatus.PENDING
                answer.grading_revision = question.grading_revision
        aggregate_attempt(attempt, questions, answers, task)
    return True


async def scan_pending_grading_attempts(session, limit=100):
    """公开持久扫描边界；扫描后逐份使用独立Session评分。"""
    return await attempt_service.pending_grading_attempts(session, limit)


async def scan_assignable_exam_ids(session, limit=100):
    """数据库只扫描持久待分配标记，已处理历史不会占满恢复批次。"""
    return await exam_service.ended_grading_exam_ids(session, limit)


async def assign_grading_tasks(session, exam_id):
    """结束后按整份答卷均分，保留既有工作和不可重复的任务身份。"""
    async with session.begin():
        exam = await exam_service.require_exam(session, exam_id, lock=True)
        if exam.status != ExamStatus.RELEASED or exam.end_at is None or utc_now() < exam.end_at:
            return 0
        participants = await exam_service.grading_participants(session, exam_id, lock=True)
        attempts = await attempt_service.grading_attempts(
            session,
            [row.id for row in participants if row.status == ParticipantStatus.ASSIGNED],
            lock=True,
        )
        valid = [attempt for attempt in attempts if attempt.status != AttemptStatus.VOID]
        # 到期交卷及自动空答判分均完成后才能建立人工任务。
        if any(
            attempt.status == AttemptStatus.IN_PROGRESS
            or attempt.grading_status == GradingStatus.PENDING
            for attempt in valid
        ):
            return 0
        configured = await exam_service.grading_teacher_ids(session, exam_id)
        existing = await crud.tasks_for_attempts(session, [attempt.id for attempt in valid])
        users = await identity_service.locked_summaries(
            session,
            set(configured)
            | {task.assigned_teacher_id for task in existing if task.assigned_teacher_id},
        )
        teachers = sorted(
            [
                value
                for value in configured
                if users[value].status == UserStatus.ACTIVATED
                and users[value].user_type == UserType.TEACHER
            ],
            key=str,
        )
        tasks = {
            task.attempt_id: task
            for task in await crud.tasks_for_attempts(
                session, [attempt.id for attempt in valid], lock=True
            )
        }
        counts = {
            teacher: sum(task.assigned_teacher_id == teacher for task in tasks.values())
            for teacher in teachers
        }
        changed = 0
        for attempt in valid:
            if attempt.grading_status == GradingStatus.GRADED:
                continue
            task = tasks.get(attempt.id)
            if task is not None:
                teacher = users.get(task.assigned_teacher_id)
                if task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS) and (
                    teacher is None or teacher.status != UserStatus.ACTIVATED
                ):
                    task.status = TaskStatus.UNASSIGNED
                    task.version += 1
                    task.updated_at = utc_now()
                    changed += 1
                continue
            teacher_id = (
                min(teachers, key=lambda value: (counts[value], str(value))) if teachers else None
            )
            task = GradingTask(
                attempt_id=attempt.id,
                grading_revision=attempt.grading_revision,
                assigned_teacher_id=teacher_id,
                status=TaskStatus.PENDING if teacher_id else TaskStatus.UNASSIGNED,
                assigned_at=utc_now() if teacher_id else None,
            )
            await crud.insert_task(session, task)
            if teacher_id:
                counts[teacher_id] += 1
            identity_service.record_audit(
                session,
                actor_id=None,
                action="GRADING_TASK_ASSIGNED" if teacher_id else "GRADING_TASK_UNASSIGNED",
                entity_type="grading_task",
                entity_id=task.id,
                after_data={
                    "attempt_id": str(attempt.id),
                    "teacher_id": str(teacher_id) if teacher_id else None,
                },
            )
            changed += 1
        # 与任务创建同事务清除待办，崩溃回滚时不会遗失后续恢复入口。
        exam.grading_assignment_pending = False
    return changed


def can_grade_task(identity, exam, task):
    if (
        task is None
        or task.status == TaskStatus.VOID
        or exam.status == ExamStatus.RESULTS_PUBLISHED
    ):
        return False
    if task.first_review_completed_at is not None:
        return identity.user.user_type in (UserType.TEACHER, UserType.ADMIN)
    if task.status == TaskStatus.UNASSIGNED:
        return False
    return (
        identity.user.user_type == UserType.TEACHER and task.assigned_teacher_id == identity.user.id
    )


def can_reassign_task(identity, task):
    return (
        identity.user.user_type == UserType.ADMIN
        and task is not None
        and task.status not in (TaskStatus.COMPLETED, TaskStatus.VOID)
    )


def task_dto(task, users):
    """任务映射只使用已加载身份，列表与详情共享同一字段白名单。"""
    if task is None:
        return None
    return TaskPublic(
        id=task.id,
        attempt_id=task.attempt_id,
        assigned_teacher=users.get(task.assigned_teacher_id),
        status=task.status,
        grading_revision=task.grading_revision,
        first_review_completed_at=task.first_review_completed_at,
        completed_at=task.completed_at,
        assigned_at=task.assigned_at,
        version=task.version,
    )


async def task_public(session, task):
    users = await identity_service.summaries(
        session, [task.assigned_teacher_id] if task and task.assigned_teacher_id else []
    )
    return task_dto(task, users)


async def attempt_summary(session, exam, participant, attempt, task):
    users = await identity_service.summaries(session, [participant.user_id])
    return AttemptSummary(
        id=attempt.id,
        exam_id=exam.id,
        exam_title=exam.title,
        student=users[participant.user_id],
        attempt_no=attempt.attempt_no,
        status=attempt.status,
        submitted_at=attempt.submitted_at,
        effective_submitted_at=attempt.effective_submitted_at,
        grading_status=attempt.grading_status,
        grading_revision=attempt.grading_revision,
        final_score=attempt.final_score,
        graded_at=attempt.graded_at,
        task=await task_public(session, task),
    )


async def attempt_detail(session, identity, exam, participant, attempt, task=None):
    if task is None:
        task = await crud.task_for_attempt(session, attempt.id)
    questions = await exam_service.attempt_questions(session, exam.id)
    answers = {
        answer.exam_question_id: answer
        for answer in await attempt_service.grading_answers(session, attempt.id)
    }
    allowed = can_grade_task(identity, exam, task)
    return AttemptDetail(
        **(await attempt_summary(session, exam, participant, attempt, task)).model_dump(),
        questions=[
            GradingQuestion(
                id=question.id,
                type=question.type,
                content=question.content,
                options=question.options,
                standard_answer=question.standard_answer,
                explanation=question.explanation,
                score=question.score,
                grading_revision=question.grading_revision,
                answer=AnswerPublic.model_validate(answers[question.id]),
                can_grade=allowed
                and question.type == QuestionType.SHORT_ANSWER
                and answers[question.id].answer_data is not None,
            )
            for question in questions
        ],
        can_grade=allowed,
        can_reassign=can_reassign_task(identity, task),
        results_published=exam.status == ExamStatus.RESULTS_PUBLISHED,
    )


async def get_attempt(session, identity, attempt_id):
    async with session.begin():
        await identity_service.validate_content_actor(session, identity)
        exam, participant, attempt = await locked_context(session, attempt_id)
        if not valid_submission(exam, participant, attempt):
            raise BusinessError("ATTEMPT_NOT_FOUND", "有效提交答卷不存在")
        result = await attempt_detail(session, identity, exam, participant, attempt)
    return result


async def get_history(session, identity, answer_id):
    identity_service.ensure_role(identity.user, UserType.ADMIN, UserType.TEACHER)
    answer = await attempt_service.grading_answer_reference(session, answer_id)
    if answer is None:
        raise BusinessError("ANSWER_NOT_FOUND", "答案不存在")
    exam, participant, attempt = await locked_context(session, answer.attempt_id)
    if not valid_submission(exam, participant, attempt):
        raise BusinessError("ANSWER_NOT_FOUND", "有效答案不存在")
    rows = await crud.histories(session, answer_id)
    users = await identity_service.summaries(
        session, {row.actor_id for row in rows if row.actor_id}
    )
    return HistoryResponse(
        items=[
            HistoryPublic(**row.model_dump(exclude={"actor_id"}), actor=users.get(row.actor_id))
            for row in rows
        ]
    )


async def refresh_grading(session, identity, exam_id):
    """显式恢复入口，先结束读事务，再逐份调用拥有独立事务的自动评分。"""
    identity_service.ensure_role(identity.user, UserType.ADMIN, UserType.TEACHER)
    exam = await exam_service.require_exam(session, exam_id)
    participants = await exam_service.grading_participants(session, exam.id)
    attempts = await attempt_service.grading_attempts(session, [row.id for row in participants])
    pending = [
        (row.id, row.grading_revision)
        for row in attempts
        if row.status == AttemptStatus.SUBMITTED and row.grading_status == GradingStatus.PENDING
    ]
    await session.rollback()
    graded = 0
    for attempt_id, revision in pending:
        graded += int(await grade_attempt(session, attempt_id, revision))
    assigned = await assign_grading_tasks(session, exam_id)
    return RefreshResult(graded_attempts=graded, assigned_tasks=assigned)


async def list_tasks(session, identity, pagination, exam_id=None, status=None, teacher_id=None):
    identity_service.ensure_role(identity.user, UserType.ADMIN, UserType.TEACHER)
    attempt_ids = None
    if exam_id is not None:
        await exam_service.require_exam(session, exam_id)
        participants = await exam_service.grading_participants(session, exam_id)
        attempt_ids = [
            attempt.id
            for attempt in await attempt_service.grading_attempts(
                session,
                [row.id for row in participants if row.status == ParticipantStatus.ASSIGNED],
            )
            if attempt.status == AttemptStatus.SUBMITTED
        ]
    rows, total = await crud.task_page(session, pagination, attempt_ids, status, teacher_id)
    attempts = {
        row.id: row
        for row in await attempt_service.grading_attempts_by_ids(
            session, [task.attempt_id for task in rows]
        )
    }
    participants, exams = await exam_service.grading_contexts(
        session, {row.exam_participant_id for row in attempts.values()}
    )
    users = await identity_service.summaries(
        session,
        {row.user_id for row in participants.values()}
        | {row.assigned_teacher_id for row in rows if row.assigned_teacher_id},
    )
    items = []
    for task in rows:
        attempt = attempts[task.attempt_id]
        participant = participants[attempt.exam_participant_id]
        exam = exams[participant.exam_id]
        items.append(
            TaskSummary(
                **task_dto(task, users).model_dump(),
                exam_id=exam.id,
                exam_title=exam.title,
                student=users[participant.user_id],
                attempt_no=attempt.attempt_no,
                can_grade=can_grade_task(identity, exam, task),
                can_reassign=can_reassign_task(identity, task),
            )
        )
    return Page[TaskSummary](
        items=items, total=total, page=pagination.page, page_size=pagination.page_size
    )


async def grade_answer(session, identity, answer_id, payload):
    """人工首阅、改分、历史及总分在同一事务更新，并发旧版本明确冲突。"""
    async with session.begin():
        await identity_service.validate_content_actor(session, identity)
        reference = await attempt_service.grading_answer_reference(session, answer_id)
        if reference is None:
            raise BusinessError("ANSWER_NOT_FOUND", "答案不存在")
        exam, participant, attempt = await locked_context(session, reference.attempt_id)
        if not valid_submission(exam, participant, attempt):
            raise BusinessError("ANSWER_NOT_FOUND", "有效答案不存在")
        if exam.status == ExamStatus.RESULTS_PUBLISHED:
            raise BusinessError("RESULTS_WITHDRAW_REQUIRED", "已公布结果须先撤回再更正评分")
        task = await crud.task_for_attempt(session, attempt.id, lock=True)
        if not can_grade_task(identity, exam, task):
            raise BusinessError("GRADING_FORBIDDEN", "首次整卷阅完前仅指定教师可以评分")
        questions = await exam_service.attempt_questions(session, exam.id)
        answers = await attempt_service.grading_answers(session, attempt.id)
        answer = next(row for row in answers if row.id == answer_id)
        question = next(row for row in questions if row.id == answer.exam_question_id)
        if question.type != QuestionType.SHORT_ANSWER or answer.answer_data is None:
            raise BusinessError("INVALID_GRADE", "只有非空简答题接受人工评分")
        if (
            answer.version != payload.version
            or question.grading_revision != payload.grading_revision
        ):
            raise BusinessError("VERSION_CONFLICT", "答案评分或评分依据已更新，请重新读取")
        if payload.score > question.score:
            raise BusinessError("INVALID_GRADE", "题目得分不得超过满分")
        if answer.score is not None and not (payload.reason and payload.reason.strip()):
            raise BusinessError("GRADING_REASON_REQUIRED", "更正已有评分须填写原因")
        save_score(
            session,
            answer,
            question,
            payload.score,
            GradingMethod.MANUAL,
            identity.user.id,
            payload.comment,
            payload.reason.strip() if payload.reason else None,
        )
        task.status = TaskStatus.IN_PROGRESS
        task.version += 1
        task.updated_at = utc_now()
        aggregate_attempt(attempt, questions, answers, task)
        result = await attempt_detail(session, identity, exam, participant, attempt, task)
    return result


async def wait_teacher_tasks(session, teacher_id):
    """身份停用用例的可组合更新，不获取考试锁或结束外层事务。"""
    await crud.wait_teacher_tasks(session, teacher_id, utc_now())


async def void_attempt_tasks(session, attempt_ids):
    """资格撤销或考试取消的可组合操作，任务与答卷同事务失效。"""
    await crud.void_tasks(session, attempt_ids, utc_now())


async def reassign_task(session, identity, task_id, payload):
    """管理员改派未完任务，原题分与首次完成事实保持有效。"""
    async with session.begin():
        await identity_service.validate_shared_actor(session, identity, UserType.ADMIN)
        reference = await crud.task_by_id(session, task_id)
        if reference is None:
            raise BusinessError("GRADING_TASK_NOT_FOUND", "阅卷任务不存在")
        exam, participant, attempt = await locked_context(session, reference.attempt_id)
        if not valid_submission(exam, participant, attempt):
            raise BusinessError("GRADING_TASK_NOT_FOUND", "有效阅卷任务不存在")
        users = await identity_service.locked_summaries(session, [payload.teacher_id])
        teacher = users.get(payload.teacher_id)
        if (
            teacher is None
            or teacher.user_type != UserType.TEACHER
            or teacher.status != UserStatus.ACTIVATED
        ):
            raise BusinessError("INVALID_TEACHER", "改派目标须为激活教师")
        task = await crud.task_by_id(session, task_id, lock=True)
        if task.version != payload.version:
            raise BusinessError("VERSION_CONFLICT", "阅卷任务已更新，请重新读取")
        if task.status in (TaskStatus.COMPLETED, TaskStatus.VOID):
            raise BusinessError("GRADING_TASK_STATE_INVALID", "仅未完成任务可以改派")
        before = task.assigned_teacher_id
        task.assigned_teacher_id = payload.teacher_id
        task.assigned_at = utc_now()
        task.status = TaskStatus.PENDING
        task.version += 1
        task.updated_at = utc_now()
        identity_service.record_audit(
            session,
            actor_id=identity.user.id,
            action="GRADING_TASK_REASSIGNED",
            entity_type="grading_task",
            entity_id=task.id,
            reason=payload.reason,
            before_data={"teacher_id": str(before) if before else None},
            after_data={"teacher_id": str(payload.teacher_id), "version": task.version},
        )
        result = await attempt_detail(session, identity, exam, participant, attempt, task)
    return result


async def list_attempts(session, identity, exam_id, pagination):
    identity_service.ensure_role(identity.user, UserType.ADMIN, UserType.TEACHER)
    exam = await exam_service.require_exam(session, exam_id)
    participants = [
        row
        for row in await exam_service.grading_participants(session, exam_id)
        if row.status == ParticipantStatus.ASSIGNED
    ]
    if exam.status == ExamStatus.CANCELLED:
        participants = []
    if pagination.q.strip():
        ids = await identity_service.filter_user_ids(
            session, [row.user_id for row in participants], pagination.q
        )
        participants = [row for row in participants if row.user_id in ids]
    by_id = {row.id: row for row in participants}
    rows, total = await attempt_service.submitted_grading_page(session, by_id, pagination)
    tasks = {
        task.attempt_id: task
        for task in await crud.tasks_for_attempts(session, [row.id for row in rows])
    }
    users = await identity_service.summaries(
        session,
        {by_id[row.exam_participant_id].user_id for row in rows}
        | {task.assigned_teacher_id for task in tasks.values() if task.assigned_teacher_id},
    )
    items = []
    for attempt in rows:
        task = tasks.get(attempt.id)
        items.append(
            AttemptSummary(
                id=attempt.id,
                exam_id=exam.id,
                exam_title=exam.title,
                student=users[by_id[attempt.exam_participant_id].user_id],
                attempt_no=attempt.attempt_no,
                status=attempt.status,
                submitted_at=attempt.submitted_at,
                effective_submitted_at=attempt.effective_submitted_at,
                grading_status=attempt.grading_status,
                grading_revision=attempt.grading_revision,
                final_score=attempt.final_score,
                graded_at=attempt.graded_at,
                task=task_dto(task, users),
            )
        )
    return Page[AttemptSummary](
        items=items, total=total, page=pagination.page, page_size=pagination.page_size
    )


async def final_results(session, identity, exam_id, pagination):
    """教师可见最终成绩，严格先选最后有效提交再检查是否判完。"""
    identity_service.ensure_role(identity.user, UserType.ADMIN, UserType.TEACHER)
    exam = await exam_service.require_exam(session, exam_id)
    if exam.status == ExamStatus.CANCELLED:
        return Page[FinalResult](
            items=[], total=0, page=pagination.page, page_size=pagination.page_size
        )
    rows, total = await exam_service.grading_participant_page(session, exam_id, pagination)
    users = await identity_service.summaries(session, [row.user_id for row in rows])
    attempts = await attempt_service.last_submitted_attempts(session, [row.id for row in rows])
    items = []
    for participant in rows:
        attempt = attempts.get(participant.id)
        complete = (
            attempt is not None
            and attempt.grading_status == GradingStatus.GRADED
            and attempt.grading_revision == exam.grading_revision
        )
        items.append(
            FinalResult(
                participant_id=participant.id,
                student=users[participant.user_id],
                attempt_id=attempt.id if attempt else None,
                attempt_no=attempt.attempt_no if attempt else None,
                grading_status=attempt.grading_status if attempt else None,
                final_score=attempt.final_score if complete else None,
                submitted_at=attempt.submitted_at if attempt else None,
            )
        )
    return Page[FinalResult](
        items=items, total=total, page=pagination.page, page_size=pagination.page_size
    )


async def correct_standard(session, identity, exam_id, question_id, payload):
    """更正单题并推进全部有效尝试的目标修订，保留无关题分与首阅事实。"""
    pending = []
    async with session.begin():
        await identity_service.validate_content_actor(session, identity)
        exam = await exam_service.require_exam(session, exam_id, lock=True)
        question = await exam_service.correct_grading_standard(
            session, identity, exam, question_id, payload
        )
        participants = await exam_service.grading_participants(session, exam_id, lock=True)
        attempts = await attempt_service.grading_attempts(
            session,
            [row.id for row in participants if row.status == ParticipantStatus.ASSIGNED],
            lock=True,
        )
        valid = [attempt for attempt in attempts if attempt.status != AttemptStatus.VOID]
        existing_tasks = await crud.tasks_for_attempts(session, [attempt.id for attempt in valid])
        teachers = await identity_service.locked_summaries(
            session,
            {task.assigned_teacher_id for task in existing_tasks if task.assigned_teacher_id},
        )
        tasks = {
            task.attempt_id: task
            for task in await crud.tasks_for_attempts(
                session, [attempt.id for attempt in valid], lock=True
            )
        }
        affected_answers = {
            answer.attempt_id: answer
            for answer in await attempt_service.grading_answers_for_attempts(
                session, [attempt.id for attempt in valid]
            )
            if answer.exam_question_id == question_id
        }
        for attempt in valid:
            answer = affected_answers[attempt.id]
            answer.grading_status = GradingStatus.PENDING
            answer.grading_revision = question.grading_revision
            answer.version += 1
            answer.updated_at = utc_now()
            attempt.grading_revision = exam.grading_revision
            attempt.grading_status = GradingStatus.PENDING
            attempt.final_score = None
            attempt.graded_at = None
            attempt.version += 1
            attempt.updated_at = utc_now()
            task = tasks.get(attempt.id)
            if task is not None:
                task.grading_revision = exam.grading_revision
                if question.type == QuestionType.SHORT_ANSWER and answer.answer_data is not None:
                    teacher = teachers.get(task.assigned_teacher_id)
                    task.status = (
                        TaskStatus.PENDING
                        if teacher and teacher.status == UserStatus.ACTIVATED
                        else TaskStatus.UNASSIGNED
                    )
                    task.completed_at = None
                task.version += 1
                task.updated_at = utc_now()
            if attempt.status == AttemptStatus.SUBMITTED:
                pending.append((attempt.id, attempt.grading_revision))
        result = await exam_service.detail(session, exam)
    for attempt_id, revision in pending:
        await attempt_service.enqueue_submitted_grading(attempt_id, revision)
    return result
