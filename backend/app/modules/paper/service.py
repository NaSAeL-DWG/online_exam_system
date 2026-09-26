from decimal import Decimal

from app.core.clock import utc_now
from app.core.contracts import Page
from app.core.errors import BusinessError
from app.modules.identity import service as identity_service
from app.modules.identity.types import UserType
from app.modules.question import service as question_service
from app.modules.question.types import QuestionStatus
from . import crud
from .models import Paper
from .schemas import PaperDetail, PaperQuestionPublic, PaperSummary
from .types import PaperStatus


async def require_paper(session, paper_id, *, lock=False):
    item = await crud.by_id(session, paper_id, lock=lock)
    if item is None:
        raise BusinessError("PAPER_NOT_FOUND", "试卷不存在")
    return item


def summary(item, count, total):
    return PaperSummary(**item.model_dump(), question_count=count, total_score=total)


async def detail(session, item):
    rows = await crud.items(session, [item.id])
    questions = await question_service.copyable_questions(
        session, [row.question_id for row in rows], allow_closed=True
    )
    result = summary(item, len(rows), sum((row.score for row in rows), Decimal("0.0")))
    return PaperDetail(
        **result.model_dump(),
        questions=[
            PaperQuestionPublic(
                id=row.id,
                question_id=row.question_id,
                order_no=row.order_no,
                score=row.score,
                question=questions[row.question_id],
            )
            for row in rows
        ],
    )


async def get_paper(session, identity, paper_id):
    identity_service.ensure_role(identity.user, UserType.ADMIN, UserType.TEACHER)
    return await detail(session, await require_paper(session, paper_id, lock=True))


async def list_papers(session, identity, pagination, status):
    identity_service.ensure_role(identity.user, UserType.ADMIN, UserType.TEACHER)
    rows, total, counts = await crud.list_page(session, pagination, status)
    return Page[PaperSummary](
        items=[summary(row, *counts.get(row.id, (0, Decimal("0.0")))) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def create_paper(session, identity, payload):
    async with session.begin():
        await identity_service.validate_content_actor(session, identity)
        await question_service.copyable_questions(
            session, [row.question_id for row in payload.questions]
        )
        item = Paper(
            creator_id=identity.user.id, title=payload.title, description=payload.description
        )
        await crud.insert(session, item)
        await crud.synchronize_items(session, item.id, payload.questions)
        result = await detail(session, item)
    return result


async def update_paper(session, identity, paper_id, payload, *, archive=False):
    async with session.begin():
        await identity_service.validate_content_actor(session, identity)
        item = await require_paper(session, paper_id, lock=True)
        if item.version != payload.version:
            raise BusinessError("VERSION_CONFLICT", "试卷已被修改，请重新读取")
        if item.status == PaperStatus.ARCHIVED:
            raise BusinessError("PAPER_ARCHIVED", "归档试卷不能修改")
        if archive:
            item.status = PaperStatus.ARCHIVED
        else:
            old_ids = {row.question_id for row in await crud.items(session, [paper_id])}
            questions = await question_service.copyable_questions(
                session, {row.question_id for row in payload.questions}, allow_closed=True
            )
            if any(
                question.status == QuestionStatus.CLOSED and question.id not in old_ids
                for question in questions.values()
            ):
                raise BusinessError("QUESTION_CLOSED", "关闭题目不能新增使用")
            item.title = payload.title
            item.description = payload.description
            await crud.synchronize_items(session, paper_id, payload.questions)
        item.version += 1
        item.updated_at = utc_now()
        identity_service.record_audit(
            session,
            actor_id=identity.user.id,
            action="PAPER_ARCHIVED" if archive else "PAPER_UPDATED",
            entity_type="paper",
            entity_id=item.id,
            after_data={"version": item.version},
        )
        result = await detail(session, item)
    return result


async def copy_for_exam(session, paper_id):
    """在调用方事务内锁住试卷与全部题目，取得一致且独立的复制 DTO。"""
    item = await require_paper(session, paper_id, lock=True)
    if item.status == PaperStatus.ARCHIVED:
        raise BusinessError("PAPER_ARCHIVED", "归档试卷不能创建新考试")
    return await detail(session, item)
