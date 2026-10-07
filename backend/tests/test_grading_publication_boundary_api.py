from uuid import UUID

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import create_async_engine

from app.modules.exam.models import Exam
from app.modules.exam.types import ExamStatus
from test_classes_api import admin_login, user_login
from test_grading_api import grade_payload, manual_case


@pytest.mark.asyncio
async def test_published_scores_and_standards_require_withdrawal_before_correction(
    client, monkeypatch, request
):
    exam, detail, _, first_no, _, _ = await manual_case(client, monkeypatch)
    client.cookies.clear()
    headers = await user_login(client, first_no, "TeacherChanged!123")
    for question in detail["questions"]:
        response = await client.post(
            f"/api/staff/answers/{question['answer']['id']}/grade",
            headers=headers,
            json=grade_payload(question, "2.0"),
        )
        assert response.status_code == 200, response.text
        detail = response.json()
    # 完整公布入口属于迭代5；仅安排已公布的持久前置状态，断言全部通过HTTP。
    engine = create_async_engine(request.getfixturevalue("database_url"))
    try:
        async with engine.begin() as connection:
            await connection.execute(
                update(Exam)
                .where(Exam.id == UUID(exam["id"]))
                .values(status=ExamStatus.RESULTS_PUBLISHED)
            )
    finally:
        await engine.dispose()
    headers = await admin_login(client)
    current = (await client.get(f"/api/staff/attempts/{detail['id']}")).json()
    assert current["results_published"] is True
    assert current["can_grade"] is False
    question = current["questions"][0]
    blocked_score = await client.post(
        f"/api/staff/answers/{question['answer']['id']}/grade",
        headers=headers,
        json=grade_payload(question, "1.0", "更正评分"),
    )
    assert blocked_score.status_code == 409, blocked_score.text
    assert blocked_score.json()["detail"]["code"] == "RESULTS_WITHDRAW_REQUIRED"
    correction_url = f"/api/staff/exams/{exam['id']}/questions/{question['id']}/correct-standard"
    payload = {
        "version": exam["version"],
        "grading_revision": question["grading_revision"],
        "standard_answer": "更正依据",
        "reason": "参考依据错误",
    }
    blocked_standard = await client.post(correction_url, headers=headers, json=payload)
    assert blocked_standard.status_code == 409, blocked_standard.text
    assert blocked_standard.json()["detail"]["code"] == "RESULTS_WITHDRAW_REQUIRED"
    invalid = await client.post(
        f"/api/staff/exams/{exam['id']}/withdraw-results",
        headers=headers,
        json={"version": exam["version"], "reason": "   "},
    )
    assert invalid.status_code == 422, invalid.text
    withdrawn = await client.post(
        f"/api/staff/exams/{exam['id']}/withdraw-results",
        headers=headers,
        json={"version": exam["version"], "reason": "更正评分依据前撤回"},
    )
    assert withdrawn.status_code == 200, withdrawn.text
    assert withdrawn.json()["status"] == "RELEASED"
    assert withdrawn.json()["results_withdraw_reason"] == "更正评分依据前撤回"
    payload["version"] = withdrawn.json()["version"]
    assert (await client.post(correction_url, headers=headers, json=payload)).status_code == 200
