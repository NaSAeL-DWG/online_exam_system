from uuid import UUID
from fastapi import APIRouter, Depends

from app.core.contracts import Page, Pagination
from app.deps import Identity, get_session, require_csrf, roles
from app.modules.identity.types import UserType
from app.modules.question.schemas import VersionRequest
from . import service
from .schemas import PaperDetail, PaperInput, PaperSummary, PaperUpdate
from .types import PaperStatus

router = APIRouter(prefix="/api/staff/papers", tags=["共享试卷"])
staff = roles(UserType.ADMIN, UserType.TEACHER)


@router.get("", response_model=Page[PaperSummary])
async def list_papers(
    pagination: Pagination = Depends(),
    status: PaperStatus | None = None,
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """分页检索试卷摘要与汇总分值，不加载题目内容。"""
    return await service.list_papers(session, identity, pagination, status)


@router.post("", status_code=201, response_model=PaperDetail, dependencies=[Depends(require_csrf)])
async def create_paper(
    payload: PaperInput, identity: Identity = Depends(staff), session=Depends(get_session)
):
    """手动选题组卷，数组顺序作为显示顺序。"""
    return await service.create_paper(session, identity, payload)


@router.get("/{paper_id}", response_model=PaperDetail)
async def get_paper(
    paper_id: UUID, identity: Identity = Depends(staff), session=Depends(get_session)
):
    """读取共享试卷及当前题库题目。"""
    return await service.get_paper(session, identity, paper_id)


@router.put("/{paper_id}", response_model=PaperDetail, dependencies=[Depends(require_csrf)])
async def update_paper(
    paper_id: UUID,
    payload: PaperUpdate,
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """原子调整题目、顺序及分值，检查共享编辑版本。"""
    return await service.update_paper(session, identity, paper_id, payload)


@router.post(
    "/{paper_id}/archive", response_model=PaperDetail, dependencies=[Depends(require_csrf)]
)
async def archive_paper(
    paper_id: UUID,
    payload: VersionRequest,
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """归档试卷并保留既有引用。"""
    return await service.update_paper(session, identity, paper_id, payload, archive=True)
