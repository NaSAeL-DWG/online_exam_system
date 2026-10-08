from decimal import Decimal, ROUND_HALF_UP

from app.core.clock import utc_now
from app.modules.attempt import service as attempt_service, result_service as attempt_results
from app.modules.attempt.types import AttemptStatus, GradingStatus
from app.modules.exam import service as exam_service
from app.modules.exam import result_service as exam_results
from app.modules.exam.types import AudienceType, ExamStatus, ParticipantStatus
from app.modules.grading import result_service as grading_results
from app.modules.grading.types import TaskStatus
from app.modules.identity import service as identity_service
from app.modules.identity.types import UserType
from .schemas import QuestionRate, ScoreBand, TeacherAnalytics


def rate(numerator, denominator):
    """公开数值口径：比率是0—1，零分母无数据，统一四位小数。"""
    if denominator == 0:
        return None
    return (Decimal(numerator) / Decimal(denominator)).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )


def complete(attempt, exam):
    return (
        attempt.grading_status == GradingStatus.GRADED
        and attempt.grading_revision == exam.grading_revision
        and attempt.final_score is not None
    )


def bands(scores, full_score):
    result = [
        ScoreBand(label=label, lower_rate=Decimal(lower), upper_rate=Decimal(upper), count=0)
        for label, lower, upper in [
            ("0%—20%", "0.0000", "0.2000"),
            ("20%—40%", "0.2000", "0.4000"),
            ("40%—60%", "0.4000", "0.6000"),
            ("60%—80%", "0.6000", "0.8000"),
            ("80%—100%", "0.8000", "1.0000"),
        ]
    ]
    for score in scores:
        # 使用未舍入原值确定区间，满分归最后一组。
        index = min(int(score / full_score * 5), 4)
        result[index].count += 1
    return result


async def teacher_analytics(session, identity, exam_id):
    async with session.begin():
        await identity_service.validate_shared_actor(
            session, identity, UserType.ADMIN, UserType.TEACHER
        )
        exam = await exam_service.require_exam(session, exam_id, lock=True)
        ended = exam.end_at is not None and utc_now() >= exam.end_at
        participants = (
            [
                row
                for row in await exam_service.grading_participants(session, exam.id)
                if row.status == ParticipantStatus.ASSIGNED
            ]
            if exam.status != ExamStatus.CANCELLED
            else []
        )
        attempts = [
            row
            for row in await attempt_service.grading_attempts(
                session, [row.id for row in participants]
            )
            if row.status != AttemptStatus.VOID
        ]
        submitted = [row for row in attempts if row.status == AttemptStatus.SUBMITTED]
        finals = await attempt_service.last_submitted_attempts(
            session, [row.id for row in participants]
        )
        graded = [row for row in finals.values() if complete(row, exam)]
        scores = [row.final_score for row in graded]
        participated = {row.exam_participant_id for row in attempts}
        in_progress = {
            row.exam_participant_id for row in attempts if row.status == AttemptStatus.IN_PROGRESS
        }
        tasks = [
            row
            for row in await grading_results.tasks_for_attempts(
                session, [row.id for row in attempts]
            )
            if row.status != TaskStatus.VOID
        ]
        expected = len(participants) if exam.audience_type == AudienceType.RESTRICTED else None
        questions = await exam_results.question_rate_snapshots(session, exam.id)
        answers = await attempt_results.answers(session, [row.id for row in graded])
        totals = {row.id: Decimal("0.0") for row in questions}
        for answer in answers:
            totals[answer.exam_question_id] += answer.score
        question_rates = [
            QuestionRate(
                question_id=row.id,
                order_no=row.order_no,
                type=row.type,
                subject=row.subject,
                content=row.content,
                full_score=row.score,
                sample_count=len(graded),
                score_sum=totals[row.id],
                score_rate=rate(totals[row.id], len(graded) * row.score),
            )
            for row in questions
        ]
        result = TeacherAnalytics(
            exam_id=exam.id,
            title=exam.title,
            exam_status=exam.status,
            audience_type=exam.audience_type,
            total_score=exam.total_score,
            pass_percentage=exam.pass_percentage,
            ended=ended,
            expected_count=expected,
            participated_count=len(participated),
            submitted_count=len(finals),
            absent_count=expected - len(participated) if expected is not None and ended else None,
            participation_rate=rate(len(participated), expected) if expected is not None else None,
            in_progress_count=len(in_progress),
            pending_grading_count=len(finals) - len(graded),
            graded_count=len(graded),
            attempts_count=len(attempts),
            submitted_attempts_count=len(submitted),
            grading_tasks_count=len(tasks),
            pending_grading_tasks_count=sum(row.status != TaskStatus.COMPLETED for row in tasks),
            average_score=(sum(scores) / len(scores)).quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            )
            if scores
            else None,
            highest_score=max(scores) if scores else None,
            lowest_score=min(scores) if scores else None,
            pass_rate=rate(
                sum(score >= exam.total_score * exam.pass_percentage / 100 for score in scores),
                len(scores),
            ),
            score_distribution=bands(scores, exam.total_score),
            question_rates=question_rates,
            notes=[
                "人数按当前有效资格中的学生去重；作答与任务另计。",
                "成绩样本先选每人最后一次有效提交，再判断当前依据已判完；待批改不计零分。",
                "公开考试没有固定应考分母，不计算缺考或参考率。",
                "逐题得分率为已判完最终作答题分之和除以样本人数与快照题目满分的乘积。",
            ],
        )
    return result
