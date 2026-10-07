import logging
import random
import hashlib
import hmac
import secrets
from datetime import timedelta

from app.core.clock import utc_now
from app.core.errors import BusinessError
from app.modules.exam import service as exam_service
from app.modules.question.types import QuestionType
from .models import AttemptQuestionOrder, ExamAttempt, StudentAnswer
from .schemas import AnswerPublic, AttemptActivation, AttemptDetail, AttemptQuestion
from .types import AttemptStatus, GradingStatus, SubmissionType
from . import crud


async def has_started(session, participant_ids):
    """包含 VOID 历史；调用方须先锁考试，再检查真实持久记录。"""
    return await crud.has_any(session, participant_ids)


async def void_participant_attempts(session, participant_ids, reason):
    """参与资格撤销用例中的可组合写入，不提交调用方事务。"""
    await crud.void_all(session, participant_ids, reason, utc_now())
    from app.modules.grading import service as grading_service

    await grading_service.void_attempt_tasks(
        session, [row.id for row in await crud.for_participants(session, participant_ids)]
    )


async def participant_attempt_counts(session, participant_ids):
    """公开管理查询返回已用次数与废弃次数；恢复资格不更改历史。"""
    return await crud.counts(session, participant_ids)


async def current_participant_attempts(session, participant_ids):
    """批量读取最近有效作答，保留本轮只含状态的提交收据入口。"""
    return await crud.current_for_participants(session, participant_ids)


async def detail(session, attempt, exam, questions=None):
    if attempt.status == AttemptStatus.SUBMITTED:
        questions = []
    elif questions is None:
        questions = await exam_service.attempt_questions(session, exam.id)
    snapshots = {question.id: question for question in questions}
    displayed = []
    rows = await crud.answer_orders(session, attempt.id) if questions else []
    for answer, order in rows:
        question = snapshots[answer.exam_question_id]
        options = {str(option["id"]): option for option in question.options}
        displayed.append(
            AttemptQuestion(
                id=question.id,
                type=question.type,
                content=question.content,
                score=question.score,
                options=[options[option_id] for option_id in order.option_order],
                display_order=order.display_order,
                answer=AnswerPublic.model_validate(answer),
            )
        )
    return AttemptDetail(
        id=attempt.id,
        exam_id=exam.id,
        exam_title=exam.title,
        attempt_no=attempt.attempt_no,
        status=attempt.status,
        started_at=attempt.started_at,
        deadline_at=attempt.deadline_at,
        submitted_at=attempt.submitted_at,
        effective_submitted_at=attempt.effective_submitted_at,
        submission_type=attempt.submission_type,
        grading_status=attempt.grading_status,
        server_now=utc_now(),
        version=attempt.version,
        token_generation=attempt.active_token_generation,
        questions=displayed,
    )


async def start_attempt(session, identity, exam_id, settings):
    pending_error = None
    completed = None
    async with session.begin():
        exam, participant, questions = await exam_service.prepare_student_start(
            session, identity, exam_id
        )
        attempts = await crud.participant_attempts(session, participant.id)
        current = next(
            (attempt for attempt in attempts if attempt.status == AttemptStatus.IN_PROGRESS), None
        )
        now = utc_now()
        if current and current.deadline_at <= now:
            complete_submission(current, now, SubmissionType.TIMEOUT)
            completed = (current.id, current.grading_revision)
            # 先释放进行中唯一索引，再建立新一次作答；原已消耗次数保持不变。
            await crud.flush(session)
            current = None
        if now < exam.start_at:
            pending_error = BusinessError("EXAM_NOT_STARTED", "考试尚未开始")
        elif now >= exam.end_at:
            pending_error = BusinessError("EXAM_ENDED", "考试已经结束")
        elif current:
            result = await detail(session, current, exam, questions)
        elif len(attempts) >= exam.max_attempts:
            pending_error = BusinessError("ATTEMPTS_EXHAUSTED", "可用作答次数已用完")
        else:
            current = ExamAttempt(
                exam_participant_id=participant.id,
                attempt_no=len(attempts) + 1,
                started_at=now,
                deadline_at=min(now + timedelta(seconds=exam.duration_seconds), exam.end_at),
                last_active_at=now,
                grading_revision=exam.grading_revision,
            )
            displayed = list(questions)
            if exam.shuffle_questions:
                random.SystemRandom().shuffle(displayed)
            orders = []
            for index, question in enumerate(displayed, 1):
                option_ids = [str(option["id"]) for option in question.options]
                if exam.shuffle_options:
                    random.SystemRandom().shuffle(option_ids)
                orders.append(
                    AttemptQuestionOrder(
                        attempt_id=current.id,
                        exam_question_id=question.id,
                        display_order=index,
                        option_order=option_ids,
                    )
                )
            answers = [
                StudentAnswer(attempt_id=current.id, exam_question_id=question.id)
                for question in questions
            ]
            await crud.insert(session, current, answers, orders)
            result = await detail(session, current, exam, questions)
    # 即使下一次开始被时间或次数拒绝，也保留本事务完成的到期收尾事实。
    if completed:
        await enqueue_submitted_grading(*completed, settings=settings)
    if pending_error:
        raise pending_error
    # 队列只加速处理；投递失败后已提交的作答由持久到期扫描补偿。
    try:
        from app.core.attempt_queue import enqueue_attempt_timeout

        await enqueue_attempt_timeout(result.id, result.deadline_at, settings=settings)
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "作答超时任务投递失败，将由扫描补偿：%s", type(exc).__name__
        )
    return result


async def require_locked_attempt(session, identity, attempt_id):
    reference = await crud.by_id(session, attempt_id)
    if reference is None:
        raise BusinessError("ATTEMPT_NOT_FOUND", "作答不存在")
    exam, participant = await exam_service.locked_attempt_context(
        session, reference.exam_participant_id, identity
    )
    attempt = await crud.by_id(session, attempt_id, lock=True)
    if attempt.status == AttemptStatus.VOID:
        raise BusinessError("ATTEMPT_NOT_FOUND", "作答不存在")
    return exam, participant, attempt


async def get_attempt(session, identity, attempt_id):
    completed = None
    async with session.begin():
        exam, _, attempt = await require_locked_attempt(session, identity, attempt_id)
        if attempt.status == AttemptStatus.IN_PROGRESS and utc_now() >= attempt.deadline_at:
            complete_submission(attempt, utc_now(), SubmissionType.TIMEOUT)
            completed = (attempt.id, attempt.grading_revision)
        result = await detail(session, attempt, exam)
    if completed:
        await enqueue_submitted_grading(*completed)
    return result


def ensure_writable(attempt):
    if attempt.status == AttemptStatus.SUBMITTED:
        raise BusinessError("ATTEMPT_SUBMITTED", "作答已经提交")
    if utc_now() >= attempt.deadline_at:
        raise BusinessError("ATTEMPT_EXPIRED", "本次作答已到截止时间")


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def ensure_page_token(attempt, raw_token, generation=None):
    if (
        not attempt.active_token_hash
        or not hmac.compare_digest(attempt.active_token_hash, token_hash(raw_token))
        or (generation is not None and attempt.active_token_generation != generation)
    ):
        raise BusinessError("PAGE_TAKEN_OVER", "答题页面已被接管，请重新接管后继续")


async def activate_attempt(session, identity, attempt_id, payload):
    async with session.begin():
        exam, _, attempt = await require_locked_attempt(session, identity, attempt_id)
        ensure_writable(attempt)
        if payload.page_token is not None:
            ensure_page_token(attempt, payload.page_token)
            raw_token = payload.page_token
        else:
            # 初始激活比较页面观察到的代次，另一设备抢先激活后不自动接管。
            if (
                payload.expected_generation is not None
                and payload.expected_generation != attempt.active_token_generation
            ):
                raise BusinessError("PAGE_TAKEN_OVER", "作答已在其他页面激活，请确认接管后继续")
            raw_token = secrets.token_urlsafe(32)
            attempt.active_token_hash = token_hash(raw_token)
            attempt.active_token_generation += 1
            attempt.version += 1
        attempt.last_active_at = utc_now()
        attempt.updated_at = utc_now()
        result = AttemptActivation(
            **(await detail(session, attempt, exam)).model_dump(), page_token=raw_token
        )
    return result


def validated_answer(question, value):
    """按快照题型验证原始JSON，false保留为有效答案，不做宽松类型转换。"""
    if value is None:
        return None
    if question.type in (QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE):
        if not isinstance(value, list) or any(type(option_id) is not str for option_id in value):
            raise BusinessError("INVALID_ANSWER", "选择题答案必须为选项ID数组")
        options = {str(option["id"]) for option in question.options}
        if len(set(value)) != len(value) or not set(value) <= options:
            raise BusinessError("INVALID_ANSWER", "选项ID无效或重复")
        if question.type == QuestionType.SINGLE_CHOICE and len(value) > 1:
            raise BusinessError("INVALID_ANSWER", "单选题最多选择一个选项")
        return value or None
    if question.type == QuestionType.TRUE_FALSE:
        if type(value) is not bool:
            raise BusinessError("INVALID_ANSWER", "判断题答案必须为布尔值")
        return value
    if type(value) is not str or len(value) > 20000:
        raise BusinessError("INVALID_ANSWER", "简答题答案必须为不超过20000字的纯文本")
    return value if value.strip() else None


async def save_answer(session, identity, attempt_id, answer_id, payload):
    async with session.begin():
        exam, _, attempt = await require_locked_attempt(session, identity, attempt_id)
        answer = await crud.answer_by_id(session, answer_id)
        if answer is None or answer.attempt_id != attempt.id:
            raise BusinessError("ANSWER_NOT_FOUND", "答案不存在")
        ensure_writable(attempt)
        ensure_page_token(attempt, payload.page_token, payload.token_generation)
        if answer.version != payload.version:
            raise BusinessError("VERSION_CONFLICT", "答案已经更新，请重新读取")
        question = await exam_service.attempt_question(session, exam.id, answer.exam_question_id)
        value = validated_answer(question, payload.answer_data)
        # 获取全部业务锁并校验答案后再次读取时间，扫描延迟不能延长保存窗口。
        ensure_writable(attempt)
        now = utc_now()
        answer.answer_data = value
        answer.version += 1
        answer.answered_at = now if value is not None else None
        answer.updated_at = now
        attempt.last_active_at = now
        attempt.updated_at = now
        result = AnswerPublic.model_validate(answer)
    return result


def complete_submission(attempt, now, submission_type):
    """HTTP和后台到期处理共享提交事实，判分在提交后的独立事务执行。"""
    attempt.status = AttemptStatus.SUBMITTED
    attempt.submitted_at = now
    attempt.effective_submitted_at = (
        attempt.deadline_at if submission_type == SubmissionType.TIMEOUT else now
    )
    attempt.submission_type = submission_type
    attempt.grading_status = GradingStatus.PENDING
    attempt.version += 1
    attempt.updated_at = now


async def submit_attempt(session, identity, attempt_id, payload):
    async with session.begin():
        exam, _, attempt = await require_locked_attempt(session, identity, attempt_id)
        ensure_page_token(attempt, payload.page_token, payload.token_generation)
        if attempt.status != AttemptStatus.SUBMITTED:
            answers = await crud.answers_for_submission(session, attempt.id)
            now = utc_now()
            timed_out = now >= attempt.deadline_at
            if (
                not timed_out
                and any(answer.answer_data is None for answer in answers)
                and not payload.confirm_unanswered
            ):
                raise BusinessError(
                    "UNANSWERED_CONFIRMATION_REQUIRED", "仍有未答题目，请确认后交卷"
                )
            complete_submission(
                attempt, now, SubmissionType.TIMEOUT if timed_out else SubmissionType.MANUAL
            )
        result = await detail(session, attempt, exam)
    await enqueue_submitted_grading(attempt.id, attempt.grading_revision)
    return result


async def active_participant_ids(session, participant_ids):
    """资源授权公开查询：仅未到期进行中的作答资格可读取答题快照图片。"""
    return await crud.active_participant_ids(session, participant_ids, utc_now())


async def scan_due_attempt_ids(session, limit=100):
    """公开到期扫描查询；扫描Session结束后后台逐份使用独立事务收尾。"""
    return await crud.due_attempt_ids(session, utc_now(), limit)


async def timeout_attempt(session, attempt_id):
    """后台公开顶层用例：与HTTP共用收尾，重复、未到期和VOID均无副作用。"""
    async with session.begin():
        reference = await crud.by_id(session, attempt_id)
        if reference is None:
            return False
        exam, participant = await exam_service.locked_attempt_context(
            session, reference.exam_participant_id
        )
        attempt = await crud.by_id(session, attempt_id, lock=True)
        from app.modules.exam.types import ExamStatus, ParticipantStatus

        if (
            exam.status == ExamStatus.CANCELLED
            or participant.status != ParticipantStatus.ASSIGNED
            or attempt.status != AttemptStatus.IN_PROGRESS
        ):
            return False
        now = utc_now()
        if now < attempt.deadline_at:
            return False
        # 账号停用阻止继续作答，但不阻止既有作答在固定截止时正常交卷。
        complete_submission(attempt, now, SubmissionType.TIMEOUT)
    await enqueue_submitted_grading(attempt.id, attempt.grading_revision)
    return True


async def enqueue_submitted_grading(attempt_id, grading_revision, *, settings=None):
    """业务提交后投递加速任务，失败由数据库待评分扫描补偿。"""
    try:
        from app.core.grading_queue import enqueue_attempt_grading

        await enqueue_attempt_grading(attempt_id, grading_revision, settings=settings)
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "自动判分任务投递失败，将由扫描补偿：%s", type(exc).__name__
        )


async def grading_attempt(session, attempt_id, *, lock=False):
    """阅卷公开查询，锁定前须先取得考试、资格锁。"""
    return await crud.by_id(session, attempt_id, lock=lock)


async def grading_attempts(session, participant_ids, *, lock=False):
    """批量取得全部尝试，评分不会只处理最终成绩采用的那一次。"""
    return await crud.for_participants(session, participant_ids, lock=lock)


async def grading_answers(session, attempt_id):
    """在作答锁后按答案ID固定顺序加锁，供评分事务组合。"""
    return await crud.answers_for_submission(session, attempt_id)


async def grading_answer_reference(session, answer_id):
    """仅定位答案归属；实际写入在持有全部业务锁后重读。"""
    return await crud.answer_reference(session, answer_id)


async def pending_grading_attempts(session, limit=100):
    """持久补偿查询，只返回提交且尚未自动判完的目标修订。"""
    return await crud.pending_grading(session, limit)


async def grading_attempts_by_ids(session, attempt_ids):
    """任务分页的批量作答查询。"""
    return await crud.by_ids(session, attempt_ids)


async def submitted_grading_page(session, participant_ids, pagination):
    """有效资格内的提交答卷分页能力，不过滤已判完状态。"""
    return await crud.submitted_page(session, participant_ids, pagination)


async def last_submitted_attempts(session, participant_ids):
    """先选最后有效提交，调用方再检查当前评分完成状态。"""
    return await crud.last_submitted(session, participant_ids)


async def grading_answers_for_attempts(session, attempt_ids):
    """标准更正批量锁读答案，避免逐份答卷重新执行查询。"""
    return await crud.grading_answers_for_attempts(session, attempt_ids)
