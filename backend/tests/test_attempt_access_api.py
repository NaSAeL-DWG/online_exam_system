import asyncio
from datetime import datetime, timedelta, timezone
from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image

from content_helpers import create_student, create_teacher, teacher_login
from test_classes_api import admin_login
from test_exams_api import create_exam, draft_payload
from test_questions_api import question_payload
from test_student_attempts_api import released_exam, student_login


async def upload_image(client, headers, color):
    image = BytesIO()
    Image.new("RGB", (2, 2), color).save(image, format="PNG")
    response = await client.post(
        "/api/staff/assets",
        headers=headers,
        files={"file": ("exam-image.png", image.getvalue(), "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json()["url"], image.getvalue()


async def image_exam(client, **configuration):
    """只经公开 HTTP 准备独立快照，区分题干、选项、解析和来源后来增加的图片。"""
    headers = await admin_login(client)
    stem, stem_bytes = await upload_image(client, headers, "red")
    option, option_bytes = await upload_image(client, headers, "blue")
    explanation, _ = await upload_image(client, headers, "green")
    source_only, _ = await upload_image(client, headers, "yellow")
    payload = question_payload(
        content=f"观察题干图片 ![题干]({stem})",
        explanation=f"仅解析可见 ![解析]({explanation})",
    )
    payload["options"][0]["content"] = f"观察选项 ![选项]({option})"
    response = await client.post("/api/staff/questions", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    question = response.json()
    response = await client.post(
        "/api/staff/papers",
        headers=headers,
        json={
            "title": "图片授权验收-" + uuid4().hex,
            "questions": [{"question_id": question["id"], "score": "2.0"}],
        },
    )
    assert response.status_code == 201, response.text
    exam = await create_exam(client, headers, response.json(), audience_type="PUBLIC")
    response = await client.put(
        f"/api/staff/exams/{exam['id']}",
        headers=headers,
        json=draft_payload(
            exam,
            start_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
            **configuration,
        ),
    )
    assert response.status_code == 200, response.text
    response = await client.post(
        f"/api/staff/exams/{exam['id']}/publish",
        headers=headers,
        json={"version": response.json()["version"]},
    )
    assert response.status_code == 200, response.text
    exam = response.json()
    response = await client.put(
        f"/api/staff/questions/{question['id']}",
        headers=headers,
        json=payload | {"version": 1, "content": f"后来替换的来源 ![来源]({source_only})"},
    )
    assert response.status_code == 200, response.text
    return exam, [(stem, stem_bytes), (option, option_bytes)], [explanation, source_only]


@pytest.mark.asyncio
async def test_student_images_require_own_live_snapshot_and_lose_access_after_revocation(client):
    student, number = await create_student(client)
    _, other_number = await create_student(client)
    exam, visible, hidden = await image_exam(client)
    headers = await student_login(client, number)
    # 仅浏览考试并不授予图片权限，也不接受猜测资源地址。
    assert (await client.get(visible[0][0])).status_code == 403
    response = await client.post(
        f"/api/student/exams/{exam['id']}/attempts", headers=headers, json={}
    )
    assert response.status_code == 200, response.text
    for url, expected_bytes in visible:
        response = await client.get(url)
        assert response.status_code == 200, response.text
        assert response.content == expected_bytes
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
    for url in hidden:
        assert (await client.get(url)).status_code == 403
    await student_login(client, other_number)
    assert (await client.get(visible[0][0])).status_code == 403
    headers = await admin_login(client)
    participants_url = f"/api/staff/exams/{exam['id']}/participants"
    participant = (await client.get(participants_url)).json()["items"][0]
    assert participant["user"]["id"] == student["id"]
    revoked = await client.post(
        f"{participants_url}/{participant['id']}/cancel",
        headers=headers,
        json={"version": participant["version"], "reason": "图片授权撤销验收"},
    )
    assert revoked.status_code == 200, revoked.text
    await student_login(client, number)
    for url, _ in visible:
        assert (await client.get(url)).status_code == 403


@pytest.mark.asyncio
async def test_attempt_identity_and_answer_ownership_are_required_even_with_a_valid_page_token(
    client,
):
    _, first_number = await create_student(client)
    _, second_number = await create_student(client)
    _, teacher_number = await create_teacher(client)
    exam = await released_exam(client)
    first_headers = await student_login(client, first_number)
    started = await client.post(
        f"/api/student/exams/{exam['id']}/attempts", headers=first_headers, json={}
    )
    assert started.status_code == 200, started.text
    first_url = f"/api/student/attempts/{started.json()['id']}"
    activated = await client.post(first_url + "/activate", headers=first_headers, json={})
    assert activated.status_code == 200, activated.text
    first = activated.json()
    first_permission = {
        "page_token": first["page_token"],
        "token_generation": first["token_generation"],
    }
    first_answer = first["questions"][0]["answer"]
    second_headers = await student_login(client, second_number)
    # 令牌不是身份凭据，即使持有他人的正确页面令牌，也不能读写他人答卷。
    responses = [
        await client.get(first_url),
        await client.post(first_url + "/activate", headers=second_headers, json={}),
        await client.put(
            first_url + f"/answers/{first_answer['id']}",
            headers=second_headers,
            json=first_permission | {"version": first_answer["version"], "answer_data": None},
        ),
        await client.post(
            first_url + "/submit",
            headers=second_headers,
            json=first_permission | {"confirm_unanswered": True},
        ),
    ]
    for response in responses:
        assert response.status_code == 404, response.text
        assert response.json()["detail"]["code"] == "ATTEMPT_NOT_FOUND"
    started = await client.post(
        f"/api/student/exams/{exam['id']}/attempts", headers=second_headers, json={}
    )
    assert started.status_code == 200, started.text
    second_url = f"/api/student/attempts/{started.json()['id']}"
    activated = await client.post(second_url + "/activate", headers=second_headers, json={})
    assert activated.status_code == 200, activated.text
    second = activated.json()
    mismatched_answer = await client.put(
        second_url + f"/answers/{first_answer['id']}",
        headers=second_headers,
        json={
            "page_token": second["page_token"],
            "token_generation": second["token_generation"],
            "version": first_answer["version"],
            "answer_data": None,
        },
    )
    assert mismatched_answer.status_code == 404, mismatched_answer.text
    assert mismatched_answer.json()["detail"]["code"] == "ANSWER_NOT_FOUND"
    await student_login(client, first_number)
    unchanged = await client.get(first_url)
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json()["status"] == "IN_PROGRESS"
    assert unchanged.json()["questions"][0]["answer"] == first_answer
    for login in (admin_login, lambda value: teacher_login(value, teacher_number)):
        headers = await login(client)
        response = await client.post(
            f"/api/student/exams/{exam['id']}/attempts", headers=headers, json={}
        )
        assert response.status_code == 403, response.text
        assert (await client.get(first_url)).status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("completion", ["manual", "deadline"])
async def test_snapshot_images_are_hidden_after_submission_or_deadline_even_with_review_enabled(
    client, completion
):
    _, number = await create_student(client)
    exam, visible, _ = await image_exam(
        client, duration_seconds=4 if completion == "deadline" else 3600, allow_review=True
    )
    headers = await student_login(client, number)
    started = await client.post(
        f"/api/student/exams/{exam['id']}/attempts", headers=headers, json={}
    )
    assert started.status_code == 200, started.text
    attempt = started.json()
    assert (await client.get(visible[0][0])).status_code == 200
    if completion == "manual":
        url = f"/api/student/attempts/{attempt['id']}"
        activated = await client.post(url + "/activate", headers=headers, json={})
        assert activated.status_code == 200, activated.text
        permission = activated.json()
        submitted = await client.post(
            url + "/submit",
            headers=headers,
            json={
                "page_token": permission["page_token"],
                "token_generation": permission["token_generation"],
                "confirm_unanswered": True,
            },
        )
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["questions"] == []
    else:
        # 不读取答卷触发收尾，也不启动测试 worker，验证扫描滞后仍立即收回图片权限。
        remaining = (
            datetime.fromisoformat(attempt["deadline_at"]) - datetime.now(timezone.utc)
        ).total_seconds()
        await asyncio.sleep(max(0, remaining) + 0.05)
    for url, _ in visible:
        assert (await client.get(url)).status_code == 403
