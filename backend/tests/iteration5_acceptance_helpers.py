"""独立验收只通过公开 HTTP 接口建立和观察考试数据。"""

from datetime import datetime, timedelta
from io import BytesIO

from PIL import Image

from content_helpers import create_student
from test_classes_api import admin_login
from test_grading_api import submit_values
from test_questions_api import question_payload
from test_student_attempts_api import advance_server_clock, released_exam


async def image_asset(client, color):
    headers = await admin_login(client)
    buffer = BytesIO()
    Image.new("RGB", (2, 2), color).save(buffer, format="PNG")
    data = buffer.getvalue()
    response = await client.post(
        "/api/staff/assets",
        headers=headers,
        files={"file": ("feedback.png", data, "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json(), data


async def refresh_grading(client, exam):
    headers = await admin_login(client)
    response = await client.post(
        f"/api/staff/exams/{exam['id']}/grading/refresh", headers=headers, json={}
    )
    assert response.status_code == 200, response.text


async def exam_action(client, exam, action, **fields):
    headers = await admin_login(client)
    detail = await client.get(f"/api/staff/exams/{exam['id']}")
    assert detail.status_code == 200, detail.text
    return await client.post(
        f"/api/staff/exams/{exam['id']}/{action}",
        headers=headers,
        json={"version": detail.json()["version"]} | fields,
    )


async def wrong_attempt_case(client, monkeypatch, *, allow_review=True):
    student, number = await create_student(client)
    explanation_asset, explanation_bytes = await image_asset(client, "blue")
    payload = question_payload(
        type="TRUE_FALSE",
        options=[],
        standard_answer=True,
        content="验收快照题干-不会随来源变化",
        explanation=f"独立验收隐藏解析 ![依据]({explanation_asset['url']})",
        knowledge_tags=["独立验收知识点"],
    )
    exam = await released_exam(
        client,
        allow_review=allow_review,
        shuffle_questions=False,
        question_payloads=[payload],
    )
    attempt, _ = await submit_values(client, number, exam, [False])
    advance_server_clock(monkeypatch, datetime.fromisoformat(exam["end_at"]) + timedelta(seconds=1))
    await refresh_grading(client, exam)
    return student, number, exam, attempt, explanation_asset, explanation_bytes
