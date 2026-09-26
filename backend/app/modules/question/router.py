from uuid import UUID

from fastapi import APIRouter, Depends

from app.deps import Identity, get_session, require_csrf, roles
from app.modules.identity.types import UserType
from app.core.contracts import Page, Pagination
from . import service
from .schemas import QuestionContent, QuestionPublic, QuestionUpdate, VersionRequest
from .types import Difficulty, QuestionStatus, QuestionType

router = APIRouter(prefix="/api/staff/questions", tags=["共享题库"])
staff = roles(UserType.ADMIN, UserType.TEACHER)


@router.get("", response_model=Page[QuestionPublic])
async def list_questions(
    pagination: Pagination = Depends(),
    subject: str | None = None,
    tag: str | None = None,
    difficulty: Difficulty | None = None,
    status: QuestionStatus | None = None,
    type: QuestionType | None = None,
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """按科目、知识点、难度、状态及题型分页检索共享题库。"""
    return await service.list_questions(
        session,
        identity,
        pagination,
        {"subject": subject, "tag": tag, "difficulty": difficulty, "status": status, "type": type},
    )


@router.post(
    "", status_code=201, response_model=QuestionPublic, dependencies=[Depends(require_csrf)]
)
async def create_question(
    payload: QuestionContent, identity: Identity = Depends(staff), session=Depends(get_session)
):
    """创建教师共享题目并保留 Markdown 原文。"""
    return await service.create_question(session, identity, payload)


@router.get("/{question_id}", response_model=QuestionPublic)
async def get_question(
    question_id: UUID, identity: Identity = Depends(staff), session=Depends(get_session)
):
    """查询共享题目详情；标准答案仅向教师及管理员开放。"""
    return await service.get_question(session, identity, question_id)


@router.put("/{question_id}", response_model=QuestionPublic, dependencies=[Depends(require_csrf)])
async def update_question(
    question_id: UUID,
    payload: QuestionUpdate,
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """凭当前版本更新共享题目，冲突时拒绝覆盖。"""
    return await service.update_question(session, identity, question_id, payload)


@router.post(
    "/{question_id}/close", response_model=QuestionPublic, dependencies=[Depends(require_csrf)]
)
async def close_question(
    question_id: UUID,
    payload: VersionRequest,
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """关闭题目并保留历史关联。"""
    return await service.update_question(session, identity, question_id, payload, close=True)
