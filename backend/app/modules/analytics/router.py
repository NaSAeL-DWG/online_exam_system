from uuid import UUID
from fastapi import APIRouter, Depends, Response
from app.deps import Identity, get_session, roles
from app.modules.identity.types import UserType
from . import service, student_service
from .schemas import TeacherAnalytics, StudentAnalytics

router = APIRouter(prefix="/api", tags=["考试与学习统计"])


@router.get("/staff/exams/{exam_id}/analytics", response_model=TeacherAnalytics)
async def teacher_analytics(
    exam_id: UUID,
    response: Response,
    identity: Identity = Depends(roles(UserType.ADMIN, UserType.TEACHER)),
    session=Depends(get_session),
):
    """读取当前考试去重人数、最终成绩分布及快照逐题得分率，明确无样本口径。"""
    response.headers["Cache-Control"] = "private, no-store"
    return await service.teacher_analytics(session, identity, exam_id)


@router.get("/student/analytics", response_model=StudentAnalytics)
async def student_analytics(
    response: Response,
    identity: Identity = Depends(roles(UserType.STUDENT)),
    session=Depends(get_session),
):
    """查询本人已公布成绩趋势，回看允许时汇总题型表现和历史错题知识点。"""
    response.headers["Cache-Control"] = "private, no-store"
    return await student_service.student_analytics(session, identity)
