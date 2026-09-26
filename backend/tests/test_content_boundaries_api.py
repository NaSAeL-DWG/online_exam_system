from uuid import uuid4

import pytest

from content_helpers import create_student
from test_classes_api import admin_login, user_login
from test_exams_api import create_exam, draft_payload
from test_papers_api import create_paper
from test_questions_api import question_payload


@pytest.mark.asyncio
async def test_students_cannot_read_papers_or_exam_answers_and_staff_writes_require_csrf(client):
    _, student_no = await create_student(client)
    headers = await admin_login(client)
    paper, _ = await create_paper(client, headers)
    exam = await create_exam(client, headers, paper)
    assert (
        await client.post("/api/staff/papers", json={"title": "无CSRF", "questions": []})
    ).status_code == 403
    assert (
        await client.put(f"/api/staff/exams/{exam['id']}", json=draft_payload(exam))
    ).status_code == 403
    client.cookies.clear()
    await user_login(client, student_no, "ValidPassword!123")
    for url in [
        "/api/staff/papers",
        f"/api/staff/papers/{paper['id']}",
        "/api/staff/exams",
        f"/api/staff/exams/{exam['id']}",
        f"/api/staff/exams/{exam['id']}/participants",
    ]:
        response = await client.get(url)
        assert response.status_code == 403
        assert "standard_answer" not in response.text


@pytest.mark.asyncio
async def test_exam_rejects_archived_source_naive_time_blank_title_and_unpublishable_empty_draft(
    client,
):
    headers = await admin_login(client)
    paper, _ = await create_paper(client, headers)
    exam = await create_exam(client, headers, paper)
    url = f"/api/staff/exams/{exam['id']}"
    naive = await client.put(
        url, headers=headers, json=draft_payload(exam, start_at="2026-10-01T10:00:00")
    )
    assert naive.status_code == 422
    blank = await client.post(
        "/api/staff/exams",
        headers=headers,
        json={"source_paper_id": paper["id"], "title": "   ", "audience_type": "PUBLIC"},
    )
    assert blank.status_code == 422
    await client.post(
        f"/api/staff/papers/{paper['id']}/archive", headers=headers, json={"version": 1}
    )
    archived = await client.post(
        "/api/staff/exams",
        headers=headers,
        json={"source_paper_id": paper["id"], "title": "归档来源", "audience_type": "PUBLIC"},
    )
    assert archived.status_code == 409
    assert archived.json()["detail"]["code"] == "PAPER_ARCHIVED"
    empty = await client.put(url, headers=headers, json=draft_payload(exam, questions=[]))
    assert empty.status_code == 200
    published = await client.post(
        url + "/publish", headers=headers, json={"version": empty.json()["version"]}
    )
    assert published.status_code == 409
    assert published.json()["detail"]["code"] == "EXAM_INCOMPLETE"


@pytest.mark.asyncio
async def test_question_option_bounds_duplicate_ids_and_oversize_images_are_rejected(client):
    headers = await admin_login(client)
    valid = question_payload()
    for count in [1, 9]:
        options = [{"id": str(uuid4()), "content": str(index)} for index in range(count)]
        response = await client.post(
            "/api/staff/questions",
            headers=headers,
            json=valid | {"options": options, "standard_answer": [options[0]["id"]]},
        )
        assert response.status_code == 422
    duplicate = await client.post(
        "/api/staff/questions", headers=headers, json=valid | {"options": [valid["options"][0]] * 2}
    )
    assert duplicate.status_code == 422
    oversized = await client.post(
        "/api/staff/assets",
        headers=headers,
        files={"file": ("huge.png", b"x" * (5 * 1024 * 1024 + 1), "image/png")},
    )
    assert oversized.status_code == 413
    assert oversized.json()["detail"]["code"] == "IMAGE_TOO_LARGE"
