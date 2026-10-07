from uuid import UUID

from fastapi import APIRouter, Depends

from app.deps import Identity, get_session, require_csrf, roles
from app.core.contracts import Page, Pagination
from app.modules.identity.types import UserType
from app.modules.exam.schemas import ExamDetail
from app.modules.exam import service as exam_service
from . import service
from .schemas import (
    AttemptDetail,
    AttemptSummary,
    FinalResult,
    HistoryResponse,
    ManualGrade,
    ReasonRequest,
    ReassignRequest,
    RefreshResult,
    StandardCorrection,
    TaskSummary,
)
from .types import TaskStatus

router = APIRouter(prefix="/api", tags=["判分与阅卷"])
staff = roles(UserType.ADMIN, UserType.TEACHER)


@router.get("/staff/attempts/{attempt_id}", response_model=AttemptDetail)
async def get_attempt(
    attempt_id: UUID, identity: Identity = Depends(staff), session=Depends(get_session)
):
    """教师共享读取有效提交答卷及任务权限、当前评分依据。"""
    return await service.get_attempt(session, identity, attempt_id)


@router.get("/staff/answers/{answer_id}/history", response_model=HistoryResponse)
async def get_history(
    answer_id: UUID, identity: Identity = Depends(staff), session=Depends(get_session)
):
    """读取有效答案的自动和人工评分历史。"""
    return await service.get_history(session, identity, answer_id)


@router.post(
    "/staff/exams/{exam_id}/grading/refresh",
    response_model=RefreshResult,
    dependencies=[Depends(require_csrf)],
)
async def refresh_grading(
    exam_id: UUID, identity: Identity = Depends(staff), session=Depends(get_session)
):
    """按数据库待处理状态幂等恢复自动判分和已结束考试的任务分配。"""
    return await service.refresh_grading(session, identity, exam_id)


@router.get("/staff/grading-tasks", response_model=Page[TaskSummary])
async def list_tasks(
    pagination: Pagination = Depends(),
    exam_id: UUID | None = None,
    status: TaskStatus | None = None,
    assigned_teacher_id: UUID | None = None,
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """分页查看整卷阅卷任务，支持考试、任务状态及指定教师筛选。"""
    return await service.list_tasks(
        session, identity, pagination, exam_id, status, assigned_teacher_id
    )


@router.post(
    "/staff/answers/{answer_id}/grade",
    response_model=AttemptDetail,
    dependencies=[Depends(require_csrf)],
)
async def grade_answer(
    answer_id: UUID,
    payload: ManualGrade,
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """按答案版本及单题依据修订评分，返回更新后的整份答卷。"""
    return await service.grade_answer(session, identity, answer_id, payload)


@router.post(
    "/admin/grading-tasks/{task_id}/reassign",
    response_model=AttemptDetail,
    dependencies=[Depends(require_csrf)],
)
async def reassign_task(
    task_id: UUID,
    payload: ReassignRequest,
    identity: Identity = Depends(roles(UserType.ADMIN)),
    session=Depends(get_session),
):
    """管理员记录原因并将未完任务交给激活教师。"""
    return await service.reassign_task(session, identity, task_id, payload)


@router.get("/staff/exams/{exam_id}/attempts", response_model=Page[AttemptSummary])
async def list_attempts(
    exam_id: UUID,
    pagination: Pagination = Depends(),
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """分页读取全部有效提交尝试，不把多次作答缩减为最终成绩。"""
    return await service.list_attempts(session, identity, exam_id, pagination)


@router.get("/staff/exams/{exam_id}/final-results", response_model=Page[FinalResult])
async def final_results(
    exam_id: UUID,
    pagination: Pagination = Depends(),
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """查看每名有效学生最后一次提交及当前最终成绩，待批改返回空分数。"""
    return await service.final_results(session, identity, exam_id, pagination)


@router.post(
    "/staff/exams/{exam_id}/questions/{question_id}/correct-standard",
    response_model=ExamDetail,
    dependencies=[Depends(require_csrf)],
)
async def correct_standard(
    exam_id: UUID,
    question_id: UUID,
    payload: StandardCorrection,
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """更正考试快照评分依据并重开该题评分，已公布时要求先撤回。"""
    return await service.correct_standard(session, identity, exam_id, question_id, payload)


@router.post(
    "/staff/exams/{exam_id}/withdraw-results",
    response_model=ExamDetail,
    dependencies=[Depends(require_csrf)],
)
async def withdraw_results(
    exam_id: UUID,
    payload: ReasonRequest,
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """记录原因并撤回已公布结果，随后才允许改分和依据更正。"""
    return await exam_service.withdraw_results(session, identity, exam_id, payload)
