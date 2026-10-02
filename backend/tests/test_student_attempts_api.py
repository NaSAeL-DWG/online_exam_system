import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from content_helpers import create_student
from test_classes_api import admin_login, user_login
from test_exams_api import create_exam, draft_payload
from test_papers_api import create_paper
from test_questions_api import question_payload


async def released_exam(client, *, audience_type="PUBLIC", question_payloads=None, **changes):
    headers = await admin_login(client)
    if question_payloads:
        teacher = await client.post(
            "/api/admin/teachers",
            headers=headers,
            json={
                "teacher_no": "T" + uuid4().hex[:12],
                "real_name": "作答测试阅卷教师",
                "email": "grader@example.com",
                "phone_number": "13800138002",
                "temporary_password": "TemporaryPass!123",
            },
        )
        assert teacher.status_code == 201, teacher.text
        questions = []
        for payload in question_payloads:
            response = await client.post("/api/staff/questions", headers=headers, json=payload)
            assert response.status_code == 201, response.text
            questions.append({"question_id": response.json()["id"], "score": "2.5"})
        response = await client.post(
            "/api/staff/papers",
            headers=headers,
            json={"title": "作答测试试卷", "questions": questions},
        )
        assert response.status_code == 201, response.text
        paper = response.json()
        changes.setdefault("grader_ids", [teacher.json()["user"]["id"]])
    else:
        paper, _ = await create_paper(client, headers)
    exam = await create_exam(client, headers, paper, audience_type=audience_type)
    url = f"/api/staff/exams/{exam['id']}"
    now = datetime.now(timezone.utc)
    response = await client.put(
        url,
        headers=headers,
        json=draft_payload(exam, start_at=(now - timedelta(minutes=1)).isoformat(), **changes),
    )
    assert response.status_code == 200, response.text
    response = await client.post(
        url + "/publish", headers=headers, json={"version": response.json()["version"]}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def student_login(client, number):
    client.cookies.clear()
    return await user_login(client, number, "ValidPassword!123")


@pytest.mark.asyncio
async def test_student_browses_eligible_exams_without_consuming_attempt_or_reading_answers(client):
    student, number = await create_student(client)
    title = "学生可浏览公开考试" + uuid4().hex
    public = await released_exam(client, title=title)
    restricted = await released_exam(client, audience_type="RESTRICTED", title="未补入不可见考试")
    await student_login(client, number)
    response = await client.get("/api/student/exams", params={"q": title, "page_size": 1})
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    item = response.json()["items"][0]
    assert item["id"] == public["id"]
    assert item["used_attempts"] == 0
    assert item["participant_status"] is None
    assert item["can_start"] is True
    detail = await client.get(f"/api/student/exams/{public['id']}")
    assert detail.status_code == 200
    assert "questions" not in detail.json()
    assert "standard_answer" not in detail.text
    assert "explanation" not in detail.text
    hidden = await client.get(f"/api/student/exams/{restricted['id']}")
    assert hidden.status_code == 404
    await admin_login(client)
    participants = await client.get(f"/api/staff/exams/{public['id']}/participants")
    assert participants.json()["total"] == 0


@pytest.mark.asyncio
async def test_concurrent_start_resumes_one_attempt_and_preserves_deadline_and_display(client):
    _, number = await create_student(client)
    end_at = datetime.now(timezone.utc) + timedelta(minutes=20)
    exam = await released_exam(client, end_at=end_at.isoformat(), duration_seconds=3600)
    headers = await student_login(client, number)
    url = f"/api/student/exams/{exam['id']}/attempts"
    responses = await asyncio.gather(
        *[client.post(url, headers=headers, json={}) for _ in range(2)]
    )
    assert all(response.status_code == 200 for response in responses), [
        response.text for response in responses
    ]
    first, second = [response.json() for response in responses]
    assert first["id"] == second["id"]
    assert first["attempt_no"] == 1
    assert datetime.fromisoformat(first["deadline_at"]) == end_at
    assert first["questions"] == second["questions"]
    assert len(first["questions"]) == len(exam["questions"])
    assert first["questions"][0]["answer"]["answer_data"] is None
    assert first["questions"][0]["answer"]["version"] == 1
    assert "standard_answer" not in responses[0].text
    assert "explanation" not in responses[0].text
    assert "final_score" not in responses[0].text
    detail = await client.get(f"/api/student/exams/{exam['id']}")
    assert detail.json()["used_attempts"] == 1
    assert detail.json()["remaining_attempts"] == 1
    reread = await client.get(f"/api/student/attempts/{first['id']}")
    assert reread.status_code == 200, reread.text
    assert reread.json()["questions"] == first["questions"]


@pytest.mark.asyncio
async def test_page_activation_refresh_and_takeover_invalidates_old_page(client):
    _, number = await create_student(client)
    exam = await released_exam(client)
    headers = await student_login(client, number)
    started = await client.post(
        f"/api/student/exams/{exam['id']}/attempts", headers=headers, json={}
    )
    assert started.status_code == 200, started.text
    url = f"/api/student/attempts/{started.json()['id']}/activate"
    first = await client.post(url, headers=headers, json={})
    assert first.status_code == 200, first.text
    first = first.json()
    assert first["token_generation"] == 1
    assert "active_token_hash" not in first
    refreshed = await client.post(url, headers=headers, json={"page_token": first["page_token"]})
    assert refreshed.status_code == 200
    assert refreshed.json()["token_generation"] == 1
    assert refreshed.json()["page_token"] == first["page_token"]
    taken_over = await client.post(url, headers=headers, json={})
    assert taken_over.status_code == 200
    assert taken_over.json()["token_generation"] == 2
    assert taken_over.json()["page_token"] != first["page_token"]
    assert taken_over.json()["questions"] == first["questions"]
    stale = await client.post(url, headers=headers, json={"page_token": first["page_token"]})
    assert stale.status_code == 403
    assert stale.json()["detail"]["code"] == "PAGE_TAKEN_OVER"


@pytest.mark.asyncio
async def test_concurrent_initial_page_activation_does_not_take_over_the_winning_device(client):
    _, number = await create_student(client)
    exam = await released_exam(client)
    headers = await student_login(client, number)
    started = await client.post(
        f"/api/student/exams/{exam['id']}/attempts", headers=headers, json={}
    )
    assert started.status_code == 200, started.text
    url = f"/api/student/attempts/{started.json()['id']}"
    views = await asyncio.gather(client.get(url), client.get(url))
    assert [response.json()["token_generation"] for response in views] == [0, 0]
    responses = await asyncio.wait_for(
        asyncio.gather(
            *[
                client.post(url + "/activate", headers=headers, json={"expected_generation": 0})
                for _ in range(2)
            ]
        ),
        timeout=10,
    )
    assert sorted(response.status_code for response in responses) == [200, 403]
    winner = next(response.json() for response in responses if response.status_code == 200)
    loser = next(response.json() for response in responses if response.status_code == 403)
    assert loser["detail"]["code"] == "PAGE_TAKEN_OVER"
    refreshed = await client.post(
        url + "/activate", headers=headers, json={"page_token": winner["page_token"]}
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["page_token"] == winner["page_token"]
    assert refreshed.json()["token_generation"] == 1
    takeover = await client.post(url + "/activate", headers=headers, json={})
    assert takeover.status_code == 200, takeover.text
    assert takeover.json()["token_generation"] == 2
    stale = await client.post(
        url + "/activate", headers=headers, json={"page_token": winner["page_token"]}
    )
    assert stale.status_code == 403
    assert stale.json()["detail"]["code"] == "PAGE_TAKEN_OVER"


async def active_attempt(client, number, exam):
    headers = await student_login(client, number)
    response = await client.post(
        f"/api/student/exams/{exam['id']}/attempts", headers=headers, json={}
    )
    assert response.status_code == 200, response.text
    url = f"/api/student/attempts/{response.json()['id']}"
    response = await client.post(url + "/activate", headers=headers, json={})
    assert response.status_code == 200, response.text
    return response.json(), headers, url


def write_permission(attempt):
    return {"page_token": attempt["page_token"], "token_generation": attempt["token_generation"]}


@pytest.mark.asyncio
async def test_four_answer_types_save_strictly_with_versions_and_stable_options(client):
    _, number = await create_student(client)
    multiple_payload = question_payload(type="MULTIPLE_CHOICE")
    multiple_payload["standard_answer"] = [option["id"] for option in multiple_payload["options"]]
    exam = await released_exam(
        client,
        question_payloads=[
            question_payload(),
            multiple_payload,
            question_payload(type="TRUE_FALSE", options=[], standard_answer=False),
            question_payload(type="SHORT_ANSWER", options=[], standard_answer="参考内容"),
        ],
    )
    attempt, headers, url = await active_attempt(client, number, exam)
    questions = {question["type"]: question for question in attempt["questions"]}
    values = {
        "SINGLE_CHOICE": [questions["SINGLE_CHOICE"]["options"][0]["id"]],
        "MULTIPLE_CHOICE": [option["id"] for option in questions["MULTIPLE_CHOICE"]["options"][:2]],
        "TRUE_FALSE": False,
        "SHORT_ANSWER": "学生纯文本<script>不会执行</script>",
    }
    for kind, value in values.items():
        answer = questions[kind]["answer"]
        response = await client.put(
            url + f"/answers/{answer['id']}",
            headers=headers,
            json=write_permission(attempt) | {"version": 1, "answer_data": value},
        )
        assert response.status_code == 200, response.text
        assert response.json()["answer_data"] == value
        assert response.json()["version"] == 2
    reread = (await client.get(url)).json()
    assert {q["type"]: q["answer"]["answer_data"] for q in reread["questions"]} == values
    single = questions["SINGLE_CHOICE"]
    stale = await client.put(
        url + f"/answers/{single['answer']['id']}",
        headers=headers,
        json=write_permission(attempt) | {"version": 1, "answer_data": None},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "VERSION_CONFLICT"
    invalid = {
        "SINGLE_CHOICE": [single["options"][0]["id"], single["options"][1]["id"]],
        "MULTIPLE_CHOICE": [str(uuid4())],
        "TRUE_FALSE": "false",
        "SHORT_ANSWER": False,
    }
    for kind, value in invalid.items():
        response = await client.put(
            url + f"/answers/{questions[kind]['answer']['id']}",
            headers=headers,
            json=write_permission(attempt) | {"version": 2, "answer_data": value},
        )
        assert response.status_code == 400, response.text
        assert response.json()["detail"]["code"] == "INVALID_ANSWER"
    multiple = questions["MULTIPLE_CHOICE"]
    duplicate = await client.put(
        url + f"/answers/{multiple['answer']['id']}",
        headers=headers,
        json=write_permission(attempt)
        | {"version": 2, "answer_data": [multiple["options"][0]["id"]] * 2},
    )
    assert duplicate.status_code == 400
    taken_over = (await client.post(url + "/activate", headers=headers, json={})).json()
    old_page = await client.put(
        url + f"/answers/{single['answer']['id']}",
        headers=headers,
        json=write_permission(attempt) | {"version": 2, "answer_data": None},
    )
    assert old_page.status_code == 403
    assert old_page.json()["detail"]["code"] == "PAGE_TAKEN_OVER"
    assert taken_over["questions"] == reread["questions"]
    old_submit = await client.post(
        url + "/submit",
        headers=headers,
        json=write_permission(attempt) | {"confirm_unanswered": True},
    )
    assert old_submit.status_code == 403
    assert old_submit.json()["detail"]["code"] == "PAGE_TAKEN_OVER"
    submitted = await client.post(
        url + "/submit",
        headers=headers,
        json=write_permission(taken_over) | {"confirm_unanswered": False},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["questions"] == []


@pytest.mark.asyncio
async def test_manual_submission_confirms_empty_answers_and_repeats_without_new_attempt(client):
    _, number = await create_student(client)
    exam = await released_exam(client)
    attempt, headers, url = await active_attempt(client, number, exam)
    unconfirmed = await client.post(
        url + "/submit",
        headers=headers,
        json=write_permission(attempt) | {"confirm_unanswered": False},
    )
    assert unconfirmed.status_code == 409
    assert unconfirmed.json()["detail"]["code"] == "UNANSWERED_CONFIRMATION_REQUIRED"
    submitted = await client.post(
        url + "/submit",
        headers=headers,
        json=write_permission(attempt) | {"confirm_unanswered": True},
    )
    assert submitted.status_code == 200, submitted.text
    receipt = submitted.json()
    assert receipt["status"] == "SUBMITTED"
    assert receipt["submission_type"] == "MANUAL"
    assert receipt["grading_status"] == "PENDING"
    assert receipt["questions"] == []
    assert receipt["effective_submitted_at"] == receipt["submitted_at"]
    repeat = await client.post(
        url + "/submit",
        headers=headers,
        json=write_permission(attempt) | {"confirm_unanswered": False},
    )
    assert repeat.status_code == 200
    assert repeat.json()["submitted_at"] == receipt["submitted_at"]
    assert repeat.json()["version"] == receipt["version"]
    forbidden = await client.put(
        url + f"/answers/{attempt['questions'][0]['answer']['id']}",
        headers=headers,
        json=write_permission(attempt) | {"version": 1, "answer_data": None},
    )
    assert forbidden.status_code == 409
    assert forbidden.json()["detail"]["code"] == "ATTEMPT_SUBMITTED"
    assert (await client.get(url)).json()["questions"] == []
    summary = (await client.get(f"/api/student/exams/{exam['id']}")).json()
    assert summary["used_attempts"] == 1
    assert summary["current_attempt_id"] == attempt["id"]
    assert summary["current_attempt_status"] == "SUBMITTED"


def advance_server_clock(monkeypatch, value):
    from app.core import clock

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return value if tz is not None else value.replace(tzinfo=None)

    # 只控制系统时钟边界；业务锁、数据库和认证均使用真实实现。
    monkeypatch.setattr(clock, "datetime", FrozenDatetime)


@pytest.mark.asyncio
async def test_expired_attempt_rejects_offline_save_and_finishes_before_next_start(
    client, monkeypatch
):
    _, number = await create_student(client)
    exam = await released_exam(client, duration_seconds=60)
    attempt, headers, url = await active_attempt(client, number, exam)
    question = attempt["questions"][0]
    saved = await client.put(
        url + f"/answers/{question['answer']['id']}",
        headers=headers,
        json=write_permission(attempt)
        | {"version": 1, "answer_data": [question["options"][0]["id"]]},
    )
    assert saved.status_code == 200
    deadline = datetime.fromisoformat(attempt["deadline_at"])
    advance_server_clock(monkeypatch, deadline + timedelta(seconds=1))
    late = await client.put(
        url + f"/answers/{question['answer']['id']}",
        headers=headers,
        json=write_permission(attempt)
        | {"version": 2, "answer_data": [question["options"][1]["id"]]},
    )
    assert late.status_code == 409
    assert late.json()["detail"]["code"] == "ATTEMPT_EXPIRED"
    restarted = await client.post(
        f"/api/student/exams/{exam['id']}/attempts", headers=headers, json={}
    )
    assert restarted.status_code == 200, restarted.text
    assert restarted.json()["id"] != attempt["id"]
    assert restarted.json()["attempt_no"] == 2
    receipt = (await client.get(url)).json()
    assert receipt["status"] == "SUBMITTED"
    assert receipt["submission_type"] == "TIMEOUT"
    assert datetime.fromisoformat(receipt["effective_submitted_at"]) == deadline
    assert receipt["grading_status"] == "PENDING"
    assert receipt["questions"] == []
    summary = (await client.get(f"/api/student/exams/{exam['id']}")).json()
    assert summary["used_attempts"] == 2


@pytest.mark.asyncio
async def test_exam_cancellation_requires_reason_voids_all_attempts_and_cannot_restore(client):
    _, number = await create_student(client)
    exam = await released_exam(client)
    attempt, student_headers, url = await active_attempt(client, number, exam)
    staff_headers = await admin_login(client)
    staff_url = f"/api/staff/exams/{exam['id']}"
    invalid = await client.post(
        staff_url + "/cancel",
        headers=staff_headers,
        json={"version": exam["version"], "reason": "  "},
    )
    assert invalid.status_code == 422
    cancelled = await client.post(
        staff_url + "/cancel",
        headers=staff_headers,
        json={"version": exam["version"], "reason": "场次配置需要重建"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["cancelled_reason"] == "场次配置需要重建"
    participants = (await client.get(staff_url + "/participants")).json()["items"]
    assert participants[0]["used_attempts"] == 1
    assert participants[0]["voided_attempts"] == 1
    republish = await client.post(
        staff_url + "/publish", headers=staff_headers, json={"version": cancelled.json()["version"]}
    )
    assert republish.status_code == 409
    headers = await student_login(client, number)
    summary = (await client.get(f"/api/student/exams/{exam['id']}")).json()
    assert summary["unavailable_reason"] == "EXAM_CANCELLED"
    assert summary["cancelled_reason"] == "场次配置需要重建"
    assert summary["can_start"] is False
    forbidden = await client.put(
        url + f"/answers/{attempt['questions'][0]['answer']['id']}",
        headers=headers,
        json=write_permission(attempt) | {"version": 1, "answer_data": None},
    )
    assert forbidden.status_code == 409
    assert forbidden.json()["detail"]["code"] == "EXAM_CANCELLED"
    repeat_start = await client.post(
        f"/api/student/exams/{exam['id']}/attempts", headers=headers, json={}
    )
    assert repeat_start.status_code == 409


@pytest.mark.asyncio
async def test_revoked_public_qualification_cannot_recreate_or_restore_consumed_chances(client):
    student, number = await create_student(client)
    exam = await released_exam(client)
    first, headers, first_url = await active_attempt(client, number, exam)
    submitted = await client.post(
        first_url + "/submit",
        headers=headers,
        json=write_permission(first) | {"confirm_unanswered": True},
    )
    assert submitted.status_code == 200
    second, _, second_url = await active_attempt(client, number, exam)
    staff_headers = await admin_login(client)
    staff_url = f"/api/staff/exams/{exam['id']}"
    participant = (await client.get(staff_url + "/participants")).json()["items"][0]
    participant_url = staff_url + f"/participants/{participant['id']}"
    cancelled = await client.post(
        participant_url + "/cancel",
        headers=staff_headers,
        json={"version": participant["version"], "reason": "撤销所有参考记录"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["used_attempts"] == 2
    assert cancelled.json()["voided_attempts"] == 2
    headers = await student_login(client, number)
    summary = (await client.get(f"/api/student/exams/{exam['id']}")).json()
    assert summary["unavailable_reason"] == "PARTICIPANT_CANCELLED"
    assert summary["current_attempt_id"] is None
    for path in (first_url, second_url):
        denied = await client.get(path)
        assert denied.status_code == 403
        assert denied.json()["detail"]["code"] == "PARTICIPANT_CANCELLED"
    bypass = await client.post(
        f"/api/student/exams/{exam['id']}/attempts", headers=headers, json={}
    )
    assert bypass.status_code == 403
    assert bypass.json()["detail"]["code"] == "PARTICIPANT_CANCELLED"
    staff_headers = await admin_login(client)
    ordinary_add = await client.post(
        staff_url + "/participants", headers=staff_headers, json={"student_ids": [student["id"]]}
    )
    assert ordinary_add.json()["cancelled_user_ids"] == [student["id"]]
    restored = await client.post(
        participant_url + "/restore",
        headers=staff_headers,
        json={"version": cancelled.json()["version"], "reason": "显式恢复资格"},
    )
    assert restored.status_code == 200
    assert restored.json()["used_attempts"] == 2
    assert restored.json()["voided_attempts"] == 2
    headers = await student_login(client, number)
    assert (await client.get(second_url)).status_code == 404
    exhausted = await client.post(
        f"/api/student/exams/{exam['id']}/attempts", headers=headers, json={}
    )
    assert exhausted.status_code == 409
    assert exhausted.json()["detail"]["code"] == "ATTEMPTS_EXHAUSTED"


@pytest.mark.asyncio
async def test_attempt_is_finalized_when_a_new_start_is_rejected_after_exam_end(
    client, monkeypatch
):
    _, number = await create_student(client)
    end_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    exam = await released_exam(client, end_at=end_at.isoformat(), duration_seconds=3600)
    attempt, headers, url = await active_attempt(client, number, exam)
    advance_server_clock(monkeypatch, end_at + timedelta(seconds=1))
    rejected = await client.post(
        f"/api/student/exams/{exam['id']}/attempts", headers=headers, json={}
    )
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "EXAM_ENDED"
    summary = (await client.get(f"/api/student/exams/{exam['id']}")).json()
    assert summary["used_attempts"] == 1
    assert summary["current_attempt_status"] == "SUBMITTED"
    receipt = (await client.get(url)).json()
    assert receipt["status"] == "SUBMITTED"
    assert receipt["submission_type"] == "TIMEOUT"
    assert datetime.fromisoformat(receipt["effective_submitted_at"]) == end_at


@pytest.mark.asyncio
async def test_concurrent_saves_with_same_version_never_silently_overwrite(client):
    _, number = await create_student(client)
    exam = await released_exam(client)
    attempt, headers, url = await active_attempt(client, number, exam)
    question = attempt["questions"][0]
    responses = await asyncio.wait_for(
        asyncio.gather(
            *[
                client.put(
                    url + f"/answers/{question['answer']['id']}",
                    headers=headers,
                    json=write_permission(attempt) | {"version": 1, "answer_data": [option["id"]]},
                )
                for option in question["options"][:2]
            ]
        ),
        timeout=10,
    )
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response.json() for response in responses if response.status_code == 200)
    loser = next(response.json() for response in responses if response.status_code == 409)
    assert loser["detail"]["code"] == "VERSION_CONFLICT"
    saved = (await client.get(url)).json()["questions"][0]["answer"]
    assert saved["answer_data"] == winner["answer_data"]
    assert saved["version"] == 2


@pytest.mark.asyncio
async def test_save_competing_with_submission_cannot_modify_a_submitted_attempt(client):
    _, number = await create_student(client)
    exam = await released_exam(client)
    attempt, headers, url = await active_attempt(client, number, exam)
    question = attempt["questions"][0]
    save, submit = await asyncio.wait_for(
        asyncio.gather(
            client.put(
                url + f"/answers/{question['answer']['id']}",
                headers=headers,
                json=write_permission(attempt)
                | {"version": 1, "answer_data": [question["options"][0]["id"]]},
            ),
            client.post(
                url + "/submit",
                headers=headers,
                json=write_permission(attempt) | {"confirm_unanswered": True},
            ),
        ),
        timeout=10,
    )
    assert submit.status_code == 200, submit.text
    assert save.status_code in (200, 409), save.text
    if save.status_code == 409:
        assert save.json()["detail"]["code"] == "ATTEMPT_SUBMITTED"
    assert submit.json()["status"] == "SUBMITTED"
    assert submit.json()["questions"] == []
    subsequent = await client.put(
        url + f"/answers/{question['answer']['id']}",
        headers=headers,
        json=write_permission(attempt) | {"version": 2, "answer_data": None},
    )
    assert subsequent.status_code == 409
    assert subsequent.json()["detail"]["code"] == "ATTEMPT_SUBMITTED"
    assert (await client.get(f"/api/student/exams/{exam['id']}")).json()["used_attempts"] == 1


@pytest.mark.asyncio
async def test_concurrent_repeated_submissions_return_one_receipt_and_consume_one_chance(client):
    _, number = await create_student(client)
    exam = await released_exam(client)
    attempt, headers, url = await active_attempt(client, number, exam)
    responses = await asyncio.wait_for(
        asyncio.gather(
            *[
                client.post(
                    url + "/submit",
                    headers=headers,
                    json=write_permission(attempt) | {"confirm_unanswered": True},
                )
                for _ in range(2)
            ]
        ),
        timeout=10,
    )
    assert [response.status_code for response in responses] == [200, 200]
    first, second = [response.json() for response in responses]
    assert first["id"] == second["id"] == attempt["id"]
    assert first["submitted_at"] == second["submitted_at"]
    assert first["version"] == second["version"]
    assert first["grading_status"] == second["grading_status"] == "PENDING"
    assert (await client.get(f"/api/student/exams/{exam['id']}")).json()["used_attempts"] == 1
