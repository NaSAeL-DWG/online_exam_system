from datetime import datetime, timedelta

import pytest

from content_helpers import create_student
from test_classes_api import admin_login
from test_grading_api import submit_values
from test_student_attempts_api import advance_server_clock, released_exam
from test_student_attempts_api import student_login
from test_attempt_access_api import image_exam


@pytest.mark.asyncio
async def test_results_publish_waits_for_end_and_all_valid_attempts_then_can_be_withdrawn_and_republished(
    client, monkeypatch
):
    _, number = await create_student(client)
    exam = await released_exam(client)
    await submit_values(client, number, exam, ["correct"] * len(exam["questions"]))
    headers = await admin_login(client)
    url = f"/api/staff/exams/{exam['id']}"
    before_end = await client.post(
        url + "/publish-results", headers=headers, json={"version": exam["version"]}
    )
    assert before_end.status_code == 409, before_end.text
    assert before_end.json()["detail"]["code"] == "RESULTS_NOT_READY"
    advance_server_clock(monkeypatch, datetime.fromisoformat(exam["end_at"]) + timedelta(seconds=1))
    pending = await client.post(
        url + "/publish-results", headers=headers, json={"version": exam["version"]}
    )
    assert pending.status_code == 409, pending.text
    await client.post(url + "/grading/refresh", headers=headers, json={})
    published = await client.post(
        url + "/publish-results", headers=headers, json={"version": exam["version"]}
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "RESULTS_PUBLISHED"
    assert published.json()["results_published_at"] is not None
    withdrawn = await client.post(
        url + "/withdraw-results",
        headers=headers,
        json={"version": published.json()["version"], "reason": "核对评分"},
    )
    assert withdrawn.status_code == 200, withdrawn.text
    republished = await client.post(
        url + "/publish-results", headers=headers, json={"version": withdrawn.json()["version"]}
    )
    assert republished.status_code == 200, republished.text
    assert republished.json()["version"] == exam["version"] + 3


@pytest.mark.asyncio
async def test_student_history_shows_each_published_score_and_last_result_but_hides_them_on_withdrawal(
    client, monkeypatch
):
    _, number = await create_student(client)
    exam = await released_exam(client, allow_review=True)
    first, _ = await submit_values(client, number, exam, ["correct"] * len(exam["questions"]))
    last, _ = await submit_values(client, number, exam, [None] * len(exam["questions"]))
    await student_login(client, number)
    url = f"/api/student/results/{exam['id']}"
    hidden = await client.get(url)
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["result_state"] == "NOT_PUBLISHED"
    assert hidden.json()["final_score"] is None
    assert all(row["final_score"] is None for row in hidden.json()["attempts"])
    headers = await admin_login(client)
    advance_server_clock(monkeypatch, datetime.fromisoformat(exam["end_at"]) + timedelta(seconds=1))
    await client.post(f"/api/staff/exams/{exam['id']}/grading/refresh", headers=headers, json={})
    published = await client.post(
        f"/api/staff/exams/{exam['id']}/publish-results",
        headers=headers,
        json={"version": exam["version"]},
    )
    assert published.status_code == 200, published.text
    await student_login(client, number)
    visible = await client.get(url)
    assert visible.json()["final_attempt_id"] == last["id"]
    assert visible.json()["final_score"] == "0.0"
    assert visible.json()["attempts"][0]["id"] == first["id"]
    assert visible.json()["attempts"][0]["final_score"] == exam["total_score"]
    assert "no-store" in visible.headers["cache-control"]
    history = await client.get("/api/student/results", params={"q": exam["title"]})
    assert any(row["exam_id"] == exam["id"] for row in history.json()["items"])
    headers = await admin_login(client)
    await client.post(
        f"/api/staff/exams/{exam['id']}/withdraw-results",
        headers=headers,
        json={"version": published.json()["version"], "reason": "复核"},
    )
    await student_login(client, number)
    hidden = await client.get(url)
    assert hidden.json()["result_state"] == "CORRECTING"
    assert hidden.json()["final_score"] is None
    assert all(row["final_score"] is None for row in hidden.json()["attempts"])


@pytest.mark.asyncio
async def test_published_review_uses_snapshot_and_authorizes_its_explanation_image_only_until_withdrawal(
    client, monkeypatch
):
    _, number = await create_student(client)
    exam, displayed, hidden_assets = await image_exam(client, allow_review=True)
    attempt, _ = await submit_values(client, number, exam, [None])
    url = f"/api/student/attempts/{attempt['id']}/review"
    hidden = await client.get(url)
    assert hidden.status_code == 403, hidden.text
    headers = await admin_login(client)
    advance_server_clock(monkeypatch, datetime.fromisoformat(exam["end_at"]) + timedelta(seconds=1))
    await client.post(f"/api/staff/exams/{exam['id']}/grading/refresh", headers=headers, json={})
    published = await client.post(
        f"/api/staff/exams/{exam['id']}/publish-results",
        headers=headers,
        json={"version": exam["version"]},
    )
    assert published.status_code == 200, published.text
    await student_login(client, number)
    review = await client.get(url)
    assert review.status_code == 200, review.text
    question = review.json()["questions"][0]
    assert "观察题干图片" in question["content"]
    assert question["standard_answer"] == exam["questions"][0]["standard_answer"]
    assert question["answer"]["score"] == "0.0"
    assert "no-store" in review.headers["cache-control"]
    assert (await client.get(hidden_assets[0])).status_code == 200
    assert (await client.get(hidden_assets[1])).status_code == 403
    _, other_number = await create_student(client)
    await student_login(client, other_number)
    assert (await client.get(url)).status_code == 404
    headers = await admin_login(client)
    await client.post(
        f"/api/staff/exams/{exam['id']}/withdraw-results",
        headers=headers,
        json={"version": published.json()["version"], "reason": "复核"},
    )
    await student_login(client, number)
    assert (await client.get(url)).status_code == 403
    assert (await client.get(hidden_assets[0])).status_code == 403
