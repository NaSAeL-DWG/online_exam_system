from copy import deepcopy
from decimal import Decimal
from app.core.clock import utc_now

from app.core.contracts import Page
from app.core.errors import BusinessError
from app.modules.identity import service as identity_service
from app.modules.identity.types import UserStatus, UserType
from app.modules.paper import service as paper_service
from app.modules.question.schemas import QuestionContent
from app.modules.question import service as question_service
from app.modules.question.types import QuestionStatus
from . import crud
from .models import Exam, ExamQuestion
from .schemas import ExamDetail, ExamQuestionPublic, ExamSummary, SnapshotEdit
from .types import ExamStatus


async def require_exam(session, exam_id, *, lock=False):
    item = await crud.by_id(session, exam_id, lock=lock)
    if item is None:
        raise BusinessError("EXAM_NOT_FOUND", "考试不存在")
    return item


async def detail(session, item):
    return ExamDetail(
        **ExamSummary.model_validate(item).model_dump(),
        questions=[
            ExamQuestionPublic.model_validate(row) for row in await crud.questions(session, item.id)
        ],
        grader_ids=list(await crud.graders(session, item.id)),
    )


async def create_exam(session, identity, payload):
    async with session.begin():
        await identity_service.validate_actor(session, identity, UserType.ADMIN, UserType.TEACHER)
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
    users = await identity_service.summaries(session, set(ids))
    if len(users) != len(set(ids)) or any(
        user.user_type != UserType.TEACHER or user.status != UserStatus.ACTIVATED
        for user in users.values()
    ):
        raise BusinessError("INVALID_TEACHER", "指定阅卷教师必须处于激活状态")


async def update_exam(session, identity, exam_id, payload):
    async with session.begin():
        await identity_service.validate_actor(session, identity, UserType.ADMIN, UserType.TEACHER)
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
