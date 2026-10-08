from uuid import UUID
from fastapi import APIRouter, Depends, Response

from app.core.contracts import Page, Pagination
from app.deps import Identity, get_session, roles
from app.modules.identity.types import UserType
from . import service, review
from .schemas import StudentResultSummary, StudentResultDetail, StudentReview

router = APIRouter(prefix="/api/student", tags=["学生结果与回看"])
student = roles(UserType.STUDENT)


def private_response(response: Response):
    response.headers["Cache-Control"] = "private, no-store"


@router.get("/results", response_model=Page[StudentResultSummary])
async def list_results(
    response: Response,
    pagination: Pagination = Depends(),
    identity: Identity = Depends(student),
    session=Depends(get_session),
):
    """分页查看本人考试历史，未公布或更正中仅返回状态及空分数。"""
    private_response(response)
    return await service.list_results(session, identity, pagination)


@router.get("/results/{exam_id}", response_model=StudentResultDetail)
async def get_result(
    exam_id: UUID,
    response: Response,
    identity: Identity = Depends(student),
    session=Depends(get_session),
):
    """读取本人全部有效尝试及最后提交的最终成绩，实时执行公布状态检查。"""
    private_response(response)
    return await service.get_result(session, identity, exam_id)


@router.get("/attempts/{attempt_id}/review", response_model=StudentReview)
async def get_review(
    attempt_id: UUID,
    response: Response,
    identity: Identity = Depends(student),
    session=Depends(get_session),
):
    """回看本人已公布且允许回看的快照答卷，包括当次答案、题分和解析。"""
    private_response(response)
    return await review.get_review(session, identity, attempt_id)
