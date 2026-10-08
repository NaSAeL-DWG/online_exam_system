import pytest

from content_helpers import create_student
from test_classes_api import admin_login
from test_grading_api import submit_values
from test_questions_api import question_payload
from test_student_attempts_api import released_exam, student_login
from results_helpers import publish_ended


@pytest.mark.asyncio
async def test_mistakes_preserve_earlier_errors_filter_snapshots_and_persist_learning_annotations(
    client, monkeypatch
):
    _, number = await create_student(client)
    exam = await released_exam(
        client,
        allow_review=True,
        question_payloads=[
            question_payload(
                type="TRUE_FALSE",
                options=[],
                standard_answer=True,
                subject="数学",
                knowledge_tags=["逻辑", "基础"],
            )
        ],
    )
    first, _ = await submit_values(client, number, exam, [None])
    await submit_values(client, number, exam, [True])
    published = await publish_ended(client, monkeypatch, exam)
    await student_login(client, number)
    listing = await client.get(
        "/api/student/mistakes",
        params={"subject": "数学", "type": "TRUE_FALSE", "knowledge_tag": "逻辑", "page_size": 1},
    )
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1
    item = listing.json()["items"][0]
    assert item["attempt_id"] == first["id"]
    assert item["score"] == "0.0"
    assert item["mastered"] is False
    answer_id = item["answer_id"]
    headers = await student_login(client, number)
    updated = await client.put(
        f"/api/student/mistakes/{answer_id}/annotation",
        headers=headers,
        json={"note": "先检查命题的条件", "mastered": True},
    )
    assert updated.status_code == 200, updated.text
    detail = await client.get(f"/api/student/mistakes/{answer_id}")
    assert detail.json()["note"] == "先检查命题的条件"
    assert detail.json()["question"]["standard_answer"] is True
    assert (await client.get("/api/student/mistakes", params={"mastered": False})).json()[
        "total"
    ] == 0
    assert (await client.get("/api/student/mistakes", params={"mastered": True})).json()[
        "total"
    ] == 1
    headers = await admin_login(client)
    await client.post(
        f"/api/staff/exams/{exam['id']}/withdraw-results",
        headers=headers,
        json={"version": published["version"], "reason": "复核"},
    )
    headers = await student_login(client, number)
    assert (await client.get(f"/api/student/mistakes/{answer_id}")).status_code == 404
    assert (
        await client.put(
            f"/api/student/mistakes/{answer_id}/annotation",
            headers=headers,
            json={"note": "不可写", "mastered": False},
        )
    ).status_code == 404
