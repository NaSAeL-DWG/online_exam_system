from uuid import UUID
from fastapi import APIRouter, Depends

from app.core.contracts import Page, Pagination
from app.deps import Identity, get_session, require_csrf, roles
from app.modules.identity.types import UserType
from . import service
from .schemas import ExamCreate, ExamDetail, ExamSummary, ExamUpdate
from .types import ExamStatus

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
