from app.core.errors import BusinessError
from app.core.clock import utc_now
from app.core.contracts import Page
from app.modules.identity import service as identity_service
from app.modules.identity.types import UserType
from . import crud
from .models import Question
from .schemas import QuestionPublic
from .types import QuestionStatus


async def require_question(session, question_id, *, lock=False):
    item = await crud.by_id(session, question_id, lock=lock)
    if item is None:
        raise BusinessError("QUESTION_NOT_FOUND", "题目不存在")
    return item


async def create_question(session, identity, payload):
    async with session.begin():
        await identity_service.validate_actor(session, identity, UserType.ADMIN, UserType.TEACHER)
        item = Question(creator_id=identity.user.id, **payload.model_dump(mode="json"))
        await crud.insert(session, item)
        result = QuestionPublic.model_validate(item)
    return result


async def get_question(session, identity, question_id):
    identity_service.ensure_role(identity.user, UserType.ADMIN, UserType.TEACHER)
    return QuestionPublic.model_validate(await require_question(session, question_id))


async def list_questions(session, identity, pagination, filters):
    identity_service.ensure_role(identity.user, UserType.ADMIN, UserType.TEACHER)
    rows, total = await crud.list_page(session, pagination, filters)
    return Page[QuestionPublic](
        items=[QuestionPublic.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def update_question(session, identity, question_id, payload, *, close=False):
    async with session.begin():
        await identity_service.validate_actor(session, identity, UserType.ADMIN, UserType.TEACHER)
        item = await require_question(session, question_id, lock=True)
        if item.version != payload.version:
            raise BusinessError("VERSION_CONFLICT", "内容已被其他教师修改，请重新读取后再编辑")
        if close:
            item.status = QuestionStatus.CLOSED
        else:
            for name, value in payload.model_dump(mode="json", exclude={"version"}).items():
                setattr(item, name, value)
        item.version += 1
        item.updated_at = utc_now()
        identity_service.record_audit(
            session,
            actor_id=identity.user.id,
            action="QUESTION_CLOSED" if close else "QUESTION_UPDATED",
            entity_type="question",
            entity_id=item.id,
            after_data={"version": item.version},
        )
        result = QuestionPublic.model_validate(item)
    return result


async def copyable_questions(session, question_ids, *, allow_closed=False):
    """公开组合查询；调用方事务内按稳定顺序锁定来源并返回独立 DTO。"""
    rows = await crud.locked_many(session, set(question_ids))
    if len(rows) != len(set(question_ids)):
        raise BusinessError("QUESTION_NOT_FOUND", "部分来源题目不存在")
    if not allow_closed and any(row.status == QuestionStatus.CLOSED for row in rows):
        raise BusinessError("QUESTION_CLOSED", "关闭题目不能新增使用")
    return {row.id: QuestionPublic.model_validate(row) for row in rows}
