from uuid import UUID
from fastapi import APIRouter, Depends

from app.core.contracts import Page, Pagination
from app.deps import Identity, get_session, require_csrf, roles
from app.modules.identity.types import UserType
from app.modules.question.schemas import VersionRequest
from . import service
from .schemas import (
    ExamCreate,
    ExamDetail,
    ExamSummary,
    ExamUpdate,
    ParticipantPublic,
    ParticipantAdd,
    ParticipantAddResult,
    ParticipantChange,
)
from .types import ExamStatus, ParticipantStatus

router = APIRouter(prefix="/api/staff/exams", tags=["考试组织"])
staff = roles(UserType.ADMIN, UserType.TEACHER)


@router.get("", response_model=Page[ExamSummary])
async def list_exams(
    pagination: Pagination = Depends(),
    status: ExamStatus | None = None,
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """分页读取考试摘要，不读取含答案的快照题目。"""
    return await service.list_exams(session, identity, pagination, status)


@router.post("", status_code=201, response_model=ExamDetail, dependencies=[Depends(require_csrf)])
async def create_exam(
    payload: ExamCreate, identity: Identity = Depends(staff), session=Depends(get_session)
):
    """从当前试卷立即建立独立快照，关闭来源题通过警告明确提示。"""
    return await service.create_exam(session, identity, payload)


@router.get("/{exam_id}", response_model=ExamDetail)
async def get_exam(
    exam_id: UUID, identity: Identity = Depends(staff), session=Depends(get_session)
):
    """查询教师共享考试详情及独立题目快照。"""
    return await service.get_exam(session, identity, exam_id)


@router.put("/{exam_id}", response_model=ExamDetail, dependencies=[Depends(require_csrf)])
async def update_exam(
    exam_id: UUID,
    payload: ExamUpdate,
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """修改独立考试草稿的题目、顺序、分值、配置及指定教师。"""
    return await service.update_exam(session, identity, exam_id, payload)


@router.post("/{exam_id}/publish", response_model=ExamDetail, dependencies=[Depends(require_csrf)])
async def publish_exam(
    exam_id: UUID,
    payload: VersionRequest,
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """校验完整配置与激活阅卷教师后发布，并锁定考试内容。"""
    return await service.change_release(session, identity, exam_id, payload)


@router.post("/{exam_id}/withdraw", response_model=ExamDetail, dependencies=[Depends(require_csrf)])
async def withdraw_exam(
    exam_id: UUID,
    payload: VersionRequest,
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """仅在不存在任何历史开始记录时撤回考试发布。"""
    return await service.change_release(session, identity, exam_id, payload, withdraw=True)


@router.get("/{exam_id}/participants", response_model=Page[ParticipantPublic])
async def list_participants(
    exam_id: UUID,
    pagination: Pagination = Depends(),
    status: ParticipantStatus | None = None,
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """分页查询独立考试资格及包含废弃历史的已用次数。"""
    return await service.list_participants(session, identity, exam_id, pagination, status)


@router.post(
    "/{exam_id}/participants",
    response_model=ParticipantAddResult,
    dependencies=[Depends(require_csrf)],
)
async def add_participants(
    exam_id: UUID,
    payload: ParticipantAdd,
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """按多个班级及单独学生补入并去重，不隐式恢复撤销资格。"""
    return await service.add_participants(session, identity, exam_id, payload)


@router.post(
    "/{exam_id}/participants/{participant_id}/cancel",
    response_model=ParticipantPublic,
    dependencies=[Depends(require_csrf)],
)
async def cancel_participant(
    exam_id: UUID,
    participant_id: UUID,
    payload: ParticipantChange,
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """显式撤销资格并在同一事务废弃全部既有作答。"""
    return await service.change_participant(session, identity, exam_id, participant_id, payload)


@router.post(
    "/{exam_id}/participants/{participant_id}/restore",
    response_model=ParticipantPublic,
    dependencies=[Depends(require_csrf)],
)
async def restore_participant(
    exam_id: UUID,
    participant_id: UUID,
    payload: ParticipantChange,
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """恢复资格但不复活历史作答，也不重置已使用次数。"""
    return await service.change_participant(
        session, identity, exam_id, participant_id, payload, restore=True
    )
