from decimal import Decimal

from app.modules.attempt import service as attempt_service, result_service as attempt_results
from app.modules.attempt.types import AttemptStatus, GradingStatus
from app.modules.exam import result_service as exam_results
from app.modules.identity import service as identity_service
from app.modules.identity.types import UserType
from app.modules.results import service as result_service
from .service import complete, rate
from .schemas import StudentAnalytics, ResultTrend, TypePerformance, KnowledgeMistake


async def student_analytics(session, identity):
    """实时统计本人已公布的最终结果；题型和知识点继续遵守回看权限。"""
    async with session.begin():
        await identity_service.validate_shared_actor(session, identity, UserType.STUDENT)
        contexts = [
            row
            for row in await exam_results.student_contexts(session, identity.user.id)
            if result_service.can_read_results(*row)
        ]
        finals = await attempt_service.last_submitted_attempts(
            session, [participant.id for _, participant in contexts]
        )
        samples = [
            (exam, participant, finals[participant.id])
            for exam, participant in contexts
            if participant.id in finals and complete(finals[participant.id], exam)
        ]
        samples.sort(key=lambda row: (row[0].end_at, row[0].id))
        trend = [
            ResultTrend(
                exam_id=exam.id,
                title=exam.title,
                end_at=exam.end_at,
                submitted_at=attempt.submitted_at,
                final_score=attempt.final_score,
                total_score=exam.total_score,
                score_rate=rate(attempt.final_score, exam.total_score),
            )
            for exam, _, attempt in samples
        ]
        review_samples = [row for row in samples if result_service.can_review(row[0], row[1])]
        review_contexts = [row for row in contexts if result_service.can_review(*row)]
        questions = {
            row.id: row
            for row in await exam_results.learning_question_metadata(
                session, [exam.id for exam, _ in review_contexts]
            )
        }
        final_answers = await attempt_results.answers(
            session, [attempt.id for _, _, attempt in review_samples]
        )
        by_type = {}
        for answer in final_answers:
            question = questions[answer.exam_question_id]
            item = by_type.setdefault(
                question.type,
                {"answer_count": 0, "score_sum": Decimal("0.0"), "full_score_sum": Decimal("0.0")},
            )
            item["answer_count"] += 1
            item["score_sum"] += answer.score
            item["full_score_sum"] += question.score
        types = [
            TypePerformance(
                type=kind,
                answer_count=item["answer_count"],
                score_sum=item["score_sum"],
                full_score_sum=item["full_score_sum"],
                score_rate=rate(item["score_sum"], item["full_score_sum"]),
            )
            for kind, item in sorted(by_type.items(), key=lambda row: row[0].value)
        ]
        by_participant = {participant.id: exam for exam, participant in review_contexts}
        attempts = [
            row
            for row in await attempt_service.grading_attempts(session, by_participant)
            if row.status == AttemptStatus.SUBMITTED
            and row.grading_status == GradingStatus.GRADED
            and row.grading_revision == by_participant[row.exam_participant_id].grading_revision
        ]
        answers = await attempt_results.answers(session, [row.id for row in attempts])
        knowledge = {}
        for answer in answers:
            question = questions[answer.exam_question_id]
            if (
                answer.grading_status != GradingStatus.GRADED
                or answer.grading_revision != question.grading_revision
                or answer.score is None
                or answer.score >= question.score
            ):
                continue
            for tag in set(question.knowledge_tags):
                knowledge[tag] = knowledge.get(tag, 0) + 1
        result = StudentAnalytics(
            sample_exam_count=len(samples),
            review_exam_count=len(review_samples),
            trend=trend,
            type_performance=types,
            knowledge_mistakes=[
                KnowledgeMistake(knowledge_tag=tag, count=count)
                for tag, count in sorted(knowledge.items())
            ],
            knowledge_note="按全部已公布且允许回看的有效错误作答记录计数；同题多次错误分别保留，一题多个知识点分别计入。",
        )
    return result
