from uuid import UUID
from fastapi import APIRouter, Depends, Response
from app.core.contracts import Page, Pagination
from app.deps import Identity, get_session, require_csrf, roles
from app.modules.identity.types import UserType
from app.modules.question.types import QuestionType
from . import service
from .schemas import AnnotationInput, AnnotationPublic, MistakeSummary, MistakeDetail

router = APIRouter(prefix="/api/student/mistakes", tags=["错题学习标记"])
student = roles(UserType.STUDENT)


@router.get("", response_model=Page[MistakeSummary])
async def list_mistakes(
    response: Response,
    pagination: Pagination = Depends(),
    subject: str | None = None,
    type: QuestionType | None = None,
    knowledge_tag: str | None = None,
    mastered: bool | None = None,
    identity: Identity = Depends(student),
    session=Depends(get_session),
):
    """按快照科目、题型、知识点与掌握状态分页查看全部历史可见错题。"""
    response.headers["Cache-Control"] = "private, no-store"
    return await service.list_mistakes(
        session, identity, pagination, subject, type, knowledge_tag, mastered
    )


@router.get("/{answer_id}", response_model=MistakeDetail)
async def get_mistake(
    answer_id: UUID,
    response: Response,
    identity: Identity = Depends(student),
    session=Depends(get_session),
):
    """读取本人当前可见错题的快照内容及独立学习标记。"""
    response.headers["Cache-Control"] = "private, no-store"
    return await service.get_mistake(session, identity, answer_id)


@router.put(
    "/{answer_id}/annotation", response_model=AnnotationPublic, dependencies=[Depends(require_csrf)]
)
async def annotate(
    answer_id: UUID,
    payload: AnnotationInput,
    response: Response,
    identity: Identity = Depends(student),
    session=Depends(get_session),
):
    """实时确认错题可见资格后保存备注和已掌握标记，不改变原成绩。"""
    response.headers["Cache-Control"] = "private, no-store"
    return await service.annotate(session, identity, answer_id, payload)
