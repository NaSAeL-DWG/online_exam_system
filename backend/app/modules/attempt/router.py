from uuid import UUID

from fastapi import APIRouter, Depends

from app.deps import Identity, get_runtime_settings, get_session, require_csrf, roles
from app.modules.identity.types import UserType
from . import service
from .schemas import (
    ActivateRequest,
    AnswerPublic,
    AnswerSave,
    AttemptActivation,
    AttemptDetail,
    SubmitRequest,
)

router = APIRouter(prefix="/api/student", tags=["学生作答"])
student = roles(UserType.STUDENT)


@router.post(
    "/exams/{exam_id}/attempts", response_model=AttemptDetail, dependencies=[Depends(require_csrf)]
)
async def start_attempt(
    exam_id: UUID,
    identity: Identity = Depends(student),
    session=Depends(get_session),
    settings=Depends(get_runtime_settings),
):
    """点击开始才占用机会；并发开始恢复同一份作答和持久展示顺序。"""
    return await service.start_attempt(session, identity, exam_id, settings)


@router.get("/attempts/{attempt_id}", response_model=AttemptDetail)
async def get_attempt(
    attempt_id: UUID, identity: Identity = Depends(student), session=Depends(get_session)
):
    """读取本人有效作答及服务器答案，字段白名单排除评分依据。"""
    return await service.get_attempt(session, identity, attempt_id)


@router.post(
    "/attempts/{attempt_id}/activate",
    response_model=AttemptActivation,
    dependencies=[Depends(require_csrf)],
)
async def activate_attempt(
    attempt_id: UUID,
    payload: ActivateRequest,
    identity: Identity = Depends(student),
    session=Depends(get_session),
):
    """原令牌恢复刷新；主动接管原子递增代次并使旧页面写权限失效。"""
    return await service.activate_attempt(session, identity, attempt_id, payload)


@router.put(
    "/attempts/{attempt_id}/answers/{answer_id}",
    response_model=AnswerPublic,
    dependencies=[Depends(require_csrf)],
)
async def save_answer(
    attempt_id: UUID,
    answer_id: UUID,
    payload: AnswerSave,
    identity: Identity = Depends(student),
    session=Depends(get_session),
):
    """仅当前激活页面在截止前按答案版本保存本人单题答案。"""
    return await service.save_answer(session, identity, attempt_id, answer_id, payload)


@router.post(
    "/attempts/{attempt_id}/submit",
    response_model=AttemptDetail,
    dependencies=[Depends(require_csrf)],
)
async def submit_attempt(
    attempt_id: UUID,
    payload: SubmitRequest,
    identity: Identity = Depends(student),
    session=Depends(get_session),
):
    """确认空题后手动交卷；截止后仅提交已保存答案，重复提交返回既有收据。"""
    return await service.submit_attempt(session, identity, attempt_id, payload)
