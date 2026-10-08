from datetime import datetime, timedelta, timezone

import pytest

from content_helpers import create_student
from test_classes_api import admin_login
from test_grading_api import submit_values
from test_questions_api import question_payload
from test_student_attempts_api import released_exam, student_login, advance_server_clock
from results_helpers import publish_ended


@pytest.mark.asyncio
async def test_teacher_statistics_deduplicate_students_and_use_last_submission_with_public_null_denominators(
    client, monkeypatch
):
    _, first_no = await create_student(client)
    _, second_no = await create_student(client)
    exam = await released_exam(
        client,
        question_payloads=[question_payload(type="TRUE_FALSE", options=[], standard_answer=True)],
    )
    await submit_values(client, first_no, exam, [True])
    await submit_values(client, first_no, exam, [False])
    await submit_values(client, second_no, exam, [True])
    headers = await admin_login(client)
    url = f"/api/staff/exams/{exam['id']}"
    initial = await client.get(url + "/analytics")
    assert initial.status_code == 200, initial.text
    assert initial.json()["graded_count"] == 0
    assert initial.json()["average_score"] is None
    assert initial.json()["pending_grading_count"] == 2
    advance_server_clock(monkeypatch, datetime.fromisoformat(exam["end_at"]) + timedelta(seconds=1))
    await client.post(url + "/grading/refresh", headers=headers, json={})
    analytics = (await client.get(url + "/analytics")).json()
    assert analytics["participated_count"] == 2
    assert analytics["submitted_count"] == 2
    assert analytics["attempts_count"] == 3
    assert analytics["graded_count"] == 2
    assert analytics["average_score"] == "1.3"
    assert analytics["highest_score"] == "2.5"
    assert analytics["lowest_score"] == "0.0"
    assert analytics["pass_rate"] == "0.5000"
    assert analytics["expected_count"] is None
    assert analytics["absent_count"] is None
    assert analytics["participation_rate"] is None
    assert analytics["question_rates"][0]["score_rate"] == "0.5000"
    assert [row["count"] for row in analytics["score_distribution"]] == [1, 0, 0, 0, 1]


@pytest.mark.asyncio
async def test_student_analytics_use_published_final_scores_and_gate_type_and_knowledge_details_by_review(
    client, monkeypatch
):
    _, number = await create_student(client)
    payload = question_payload(type="MULTIPLE_CHOICE", knowledge_tags=["集合", "基础"])
    payload["standard_answer"] = [row["id"] for row in payload["options"][:2]]
    exam = await released_exam(
        client, allow_review=True, multiple_choice_mode="PARTIAL", question_payloads=[payload]
    )
    await submit_values(client, number, exam, [[payload["options"][0]["id"]]])
    await student_login(client, number)
    hidden = await client.get("/api/student/analytics")
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["trend"] == []
    published = await publish_ended(client, monkeypatch, exam)
    advance_server_clock(monkeypatch, datetime.now(timezone.utc))
    closed_review = await released_exam(
        client,
        allow_review=False,
        question_payloads=[
            question_payload(
                type="TRUE_FALSE", options=[], standard_answer=True, knowledge_tags=["隐藏标签"]
            )
        ],
    )
    await submit_values(client, number, closed_review, [True])
    await publish_ended(client, monkeypatch, closed_review)
    await student_login(client, number)
    response = await client.get("/api/student/analytics")
    analytics = response.json()
    assert analytics["sample_exam_count"] == 2
    assert analytics["review_exam_count"] == 1
    assert sorted(row["score_rate"] for row in analytics["trend"]) == ["0.5200", "1.0000"]
    assert analytics["type_performance"] == [
        {
            "type": "MULTIPLE_CHOICE",
            "answer_count": 1,
            "score_sum": "1.3",
            "full_score_sum": "2.5",
            "score_rate": "0.5200",
        }
    ]
    assert sorted(row["knowledge_tag"] for row in analytics["knowledge_mistakes"]) == [
        "基础",
        "集合",
    ]
    assert all(row["count"] == 1 for row in analytics["knowledge_mistakes"])
    assert "no-store" in response.headers["cache-control"]
    headers = await admin_login(client)
    await client.post(
        f"/api/staff/exams/{exam['id']}/withdraw-results",
        headers=headers,
        json={"version": published["version"], "reason": "复核"},
    )
    await student_login(client, number)
    hidden_again = (await client.get("/api/student/analytics")).json()
    assert hidden_again["sample_exam_count"] == 1
    assert hidden_again["type_performance"] == []
    assert hidden_again["knowledge_mistakes"] == []
