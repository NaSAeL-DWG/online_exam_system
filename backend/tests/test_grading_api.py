import asyncio
from datetime import datetime, timedelta

import pytest

from content_helpers import create_student, create_teacher, teacher_login
from test_classes_api import admin_login, user_login
from test_questions_api import question_payload
from test_student_attempts_api import (
    active_attempt,
    advance_server_clock,
    released_exam,
    student_login,
    write_permission,
)


async def submit_values(client, number, exam, values):
    attempt, headers, url = await active_attempt(client, number, exam)
    for index, value in enumerate(values):
        question = next(
            row for row in attempt["questions"] if row["id"] == exam["questions"][index]["id"]
        )
        if value == "correct":
            value = exam["questions"][index]["standard_answer"]
        saved = await client.put(
            url + f"/answers/{question['answer']['id']}",
            headers=headers,
            json=write_permission(attempt) | {"version": 1, "answer_data": value},
        )
        assert saved.status_code == 200, saved.text
    submitted = await client.post(
        url + "/submit",
        headers=headers,
        json=write_permission(attempt) | {"confirm_unanswered": True},
    )
    assert submitted.status_code == 200, submitted.text
    assert "final_score" not in submitted.text
    return attempt, submitted.json()


@pytest.mark.asyncio
async def test_submitted_objective_attempt_is_scored_idempotently_without_student_score_leak(
    client,
):
    _, number = await create_student(client)
    exam = await released_exam(
        client,
        question_payloads=[
            question_payload(),
            question_payload(type="TRUE_FALSE", options=[], standard_answer=False),
        ],
    )
    attempt, receipt = await submit_values(client, number, exam, ["correct", False])
    assert receipt["grading_status"] == "PENDING"
    headers = await admin_login(client)
    refreshed = await client.post(
        f"/api/staff/exams/{exam['id']}/grading/refresh", headers=headers, json={}
    )
    assert refreshed.status_code == 200, refreshed.text
    detail = await client.get(f"/api/staff/attempts/{attempt['id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["grading_status"] == "GRADED"
    assert detail.json()["final_score"] == "5.0"
    assert [q["answer"]["is_correct"] for q in detail.json()["questions"]] == [True, True]
    answer_id = detail.json()["questions"][0]["answer"]["id"]
    history = await client.get(f"/api/staff/answers/{answer_id}/history")
    assert history.status_code == 200, history.text
    assert len(history.json()["items"]) == 1
    repeat = await client.post(
        f"/api/staff/exams/{exam['id']}/grading/refresh", headers=headers, json={}
    )
    assert repeat.status_code == 200, repeat.text
    assert len((await client.get(f"/api/staff/answers/{answer_id}/history")).json()["items"]) == 1
    await student_login(client, number)
    reread = await client.get(f"/api/student/attempts/{attempt['id']}")
    assert reread.json()["questions"] == []
    assert "final_score" not in reread.text
    assert (await client.get(f"/api/staff/attempts/{attempt['id']}")).status_code == 403


@pytest.mark.asyncio
async def test_ended_exam_assigns_every_nonempty_attempt_as_one_balanced_idempotent_task(
    client, monkeypatch
):
    first_teacher, _ = await create_teacher(client)
    second_teacher, _ = await create_teacher(client)
    _, first_no = await create_student(client)
    _, second_no = await create_student(client)
    exam = await released_exam(
        client,
        shuffle_questions=False,
        grader_ids=[first_teacher["id"], second_teacher["id"]],
        question_payloads=[
            question_payload(type="SHORT_ANSWER", options=[], standard_answer="依据一"),
            question_payload(type="SHORT_ANSWER", options=[], standard_answer="依据二"),
        ],
    )
    attempts = []
    for number, values in [
        (first_no, ["第一次", "一"]),
        (first_no, ["第二次", "二"]),
        (second_no, ["第三份", None]),
        (second_no, [None, "   "]),
    ]:
        attempt, _ = await submit_values(client, number, exam, values)
        attempts.append(attempt)
    headers = await admin_login(client)
    before = await client.post(
        f"/api/staff/exams/{exam['id']}/grading/refresh", headers=headers, json={}
    )
    assert before.status_code == 200, before.text
    tasks = await client.get("/api/staff/grading-tasks", params={"exam_id": exam["id"]})
    assert tasks.status_code == 200, tasks.text
    assert tasks.json()["total"] == 0
    advance_server_clock(monkeypatch, datetime.fromisoformat(exam["end_at"]) + timedelta(seconds=1))
    assigned = await client.post(
        f"/api/staff/exams/{exam['id']}/grading/refresh", headers=headers, json={}
    )
    assert assigned.status_code == 200, assigned.text
    tasks = (await client.get("/api/staff/grading-tasks", params={"exam_id": exam["id"]})).json()
    assert tasks["total"] == 3
    assert sorted(task["attempt_id"] for task in tasks["items"]) == sorted(
        attempt["id"] for attempt in attempts[:3]
    )
    assert sorted(
        sum(task["assigned_teacher"]["id"] == teacher["id"] for task in tasks["items"])
        for teacher in [first_teacher, second_teacher]
    ) == [1, 2]
    assert all(task["status"] == "PENDING" for task in tasks["items"])
    first_ids = sorted(task["id"] for task in tasks["items"])
    await client.post(f"/api/staff/exams/{exam['id']}/grading/refresh", headers=headers, json={})
    assert (
        sorted(
            task["id"]
            for task in (
                await client.get("/api/staff/grading-tasks", params={"exam_id": exam["id"]})
            ).json()["items"]
        )
        == first_ids
    )
    empty = (await client.get(f"/api/staff/attempts/{attempts[-1]['id']}")).json()
    assert empty["grading_status"] == "GRADED"
    assert empty["final_score"] == "0.0"
    assert empty["task"] is None


async def manual_case(client, monkeypatch):
    first, first_no = await create_teacher(client)
    second, second_no = await create_teacher(client)
    await teacher_login(client, first_no)
    await teacher_login(client, second_no)
    _, student_no = await create_student(client)
    exam = await released_exam(
        client,
        shuffle_questions=False,
        grader_ids=[first["id"]],
        question_payloads=[
            question_payload(type="SHORT_ANSWER", options=[], standard_answer="第一题依据"),
            question_payload(type="SHORT_ANSWER", options=[], standard_answer="第二题依据"),
        ],
    )
    attempt, _ = await submit_values(client, student_no, exam, ["学生一", "学生二"])
    headers = await admin_login(client)
    advance_server_clock(monkeypatch, datetime.fromisoformat(exam["end_at"]) + timedelta(seconds=1))
    response = await client.post(
        f"/api/staff/exams/{exam['id']}/grading/refresh", headers=headers, json={}
    )
    assert response.status_code == 200, response.text
    detail = (await client.get(f"/api/staff/attempts/{attempt['id']}")).json()
    return exam, detail, first, first_no, second, second_no


def grade_payload(question, score, reason=None):
    return {
        "version": question["answer"]["version"],
        "grading_revision": question["grading_revision"],
        "score": score,
        "comment": "阅卷评语",
        "reason": reason,
    }


@pytest.mark.asyncio
async def test_first_review_is_exclusive_until_whole_attempt_finishes_then_other_teacher_can_correct(
    client, monkeypatch
):
    exam, detail, first, first_no, second, second_no = await manual_case(client, monkeypatch)
    url = f"/api/staff/attempts/{detail['id']}"
    headers = await user_login(client, second_no, "TeacherChanged!123")
    question = detail["questions"][0]
    forbidden = await client.post(
        f"/api/staff/answers/{question['answer']['id']}/grade",
        headers=headers,
        json=grade_payload(question, "2.0"),
    )
    assert forbidden.status_code == 403, forbidden.text
    assert forbidden.json()["detail"]["code"] == "GRADING_FORBIDDEN"
    client.cookies.clear()
    headers = await user_login(client, first_no, "TeacherChanged!123")
    first_grade = await client.post(
        f"/api/staff/answers/{question['answer']['id']}/grade",
        headers=headers,
        json=grade_payload(question, "2.0"),
    )
    assert first_grade.status_code == 200, first_grade.text
    detail = first_grade.json()
    assert detail["task"]["status"] == "IN_PROGRESS"
    assert detail["task"]["first_review_completed_at"] is None
    assert detail["final_score"] is None
    client.cookies.clear()
    headers = await user_login(client, second_no, "TeacherChanged!123")
    other_question = detail["questions"][1]
    assert (
        await client.post(
            f"/api/staff/answers/{other_question['answer']['id']}/grade",
            headers=headers,
            json=grade_payload(other_question, "1.0"),
        )
    ).status_code == 403
    client.cookies.clear()
    headers = await user_login(client, first_no, "TeacherChanged!123")
    finished = await client.post(
        f"/api/staff/answers/{other_question['answer']['id']}/grade",
        headers=headers,
        json=grade_payload(other_question, "1.0"),
    )
    assert finished.status_code == 200, finished.text
    detail = finished.json()
    assert detail["task"]["status"] == "COMPLETED"
    assert detail["task"]["first_review_completed_at"] is not None
    assert detail["final_score"] == "3.0"
    client.cookies.clear()
    headers = await user_login(client, second_no, "TeacherChanged!123")
    current = (await client.get(url)).json()
    assert current["can_grade"] is True
    question = current["questions"][0]
    no_reason = await client.post(
        f"/api/staff/answers/{question['answer']['id']}/grade",
        headers=headers,
        json=grade_payload(question, "2.5"),
    )
    assert no_reason.status_code == 400
    corrected = await client.post(
        f"/api/staff/answers/{question['answer']['id']}/grade",
        headers=headers,
        json=grade_payload(question, "2.5", "补计正确要点"),
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["final_score"] == "3.5"
    assert (
        corrected.json()["task"]["first_review_completed_at"]
        == detail["task"]["first_review_completed_at"]
    )
    history = (await client.get(f"/api/staff/answers/{question['answer']['id']}/history")).json()[
        "items"
    ]
    assert [(item["old_score"], item["new_score"]) for item in history] == [
        (None, "2.0"),
        ("2.0", "2.5"),
    ]
    assert history[-1]["actor"]["id"] == second["id"]


@pytest.mark.asyncio
async def test_deactivated_grader_waits_for_admin_reassignment_and_preserves_completed_question(
    client, monkeypatch
):
    _, detail, first, first_no, second, second_no = await manual_case(client, monkeypatch)
    client.cookies.clear()
    headers = await user_login(client, first_no, "TeacherChanged!123")
    question = detail["questions"][0]
    graded = await client.post(
        f"/api/staff/answers/{question['answer']['id']}/grade",
        headers=headers,
        json=grade_payload(question, "1.5"),
    )
    assert graded.status_code == 200, graded.text
    headers = await admin_login(client)
    deactivated = await client.patch(
        f"/api/admin/users/{first['id']}", headers=headers, json={"status": "DEACTIVATED"}
    )
    assert deactivated.status_code == 200, deactivated.text
    detail = (await client.get(f"/api/staff/attempts/{detail['id']}")).json()
    assert detail["task"]["status"] == "UNASSIGNED"
    task = detail["task"]
    reassigned = await client.post(
        f"/api/admin/grading-tasks/{task['id']}/reassign",
        headers=headers,
        json={"version": task["version"], "teacher_id": second["id"], "reason": "原教师停用后交接"},
    )
    assert reassigned.status_code == 200, reassigned.text
    detail = reassigned.json()
    assert detail["task"]["assigned_teacher"]["id"] == second["id"]
    assert detail["questions"][0]["answer"]["score"] == "1.5"
    assert detail["task"]["first_review_completed_at"] is None
    client.cookies.clear()
    headers = await user_login(client, second_no, "TeacherChanged!123")
    remaining = detail["questions"][1]
    finished = await client.post(
        f"/api/staff/answers/{remaining['answer']['id']}/grade",
        headers=headers,
        json=grade_payload(remaining, "2.0"),
    )
    assert finished.status_code == 200, finished.text
    assert finished.json()["final_score"] == "3.5"


@pytest.mark.asyncio
async def test_final_result_chooses_last_valid_submission_before_checking_if_it_is_graded(
    client, monkeypatch
):
    teacher, teacher_no = await create_teacher(client)
    await teacher_login(client, teacher_no)
    student, number = await create_student(client)
    exam = await released_exam(
        client,
        shuffle_questions=False,
        grader_ids=[teacher["id"]],
        question_payloads=[
            question_payload(type="SHORT_ANSWER", options=[], standard_answer="评分依据")
        ],
    )
    first, _ = await submit_values(client, number, exam, ["第一次答案"])
    second, _ = await submit_values(client, number, exam, ["第二次答案"])
    headers = await admin_login(client)
    advance_server_clock(monkeypatch, datetime.fromisoformat(exam["end_at"]) + timedelta(seconds=1))
    await client.post(f"/api/staff/exams/{exam['id']}/grading/refresh", headers=headers, json={})
    results_url = f"/api/staff/exams/{exam['id']}/final-results"
    initial = await client.get(results_url)
    assert initial.status_code == 200, initial.text
    assert initial.json()["items"][0]["attempt_id"] == second["id"]
    client.cookies.clear()
    headers = await user_login(client, teacher_no, "TeacherChanged!123")
    first_detail = (await client.get(f"/api/staff/attempts/{first['id']}")).json()
    first_question = first_detail["questions"][0]
    assert (
        await client.post(
            f"/api/staff/answers/{first_question['answer']['id']}/grade",
            headers=headers,
            json=grade_payload(first_question, "2.5"),
        )
    ).status_code == 200
    pending = (await client.get(results_url)).json()["items"][0]
    assert pending["attempt_id"] == second["id"]
    assert pending["grading_status"] == "GRADING"
    assert pending["final_score"] is None
    second_detail = (await client.get(f"/api/staff/attempts/{second['id']}")).json()
    second_question = second_detail["questions"][0]
    assert (
        await client.post(
            f"/api/staff/answers/{second_question['answer']['id']}/grade",
            headers=headers,
            json=grade_payload(second_question, "1.0"),
        )
    ).status_code == 200
    final = (await client.get(results_url, params={"q": number, "page_size": 1})).json()
    assert final["total"] == 1
    assert final["items"][0]["student"]["id"] == student["id"]
    assert final["items"][0]["final_score"] == "1.0"
    attempts = await client.get(f"/api/staff/exams/{exam['id']}/attempts", params={"q": number})
    assert attempts.status_code == 200, attempts.text
    assert attempts.json()["total"] == 2


@pytest.mark.asyncio
async def test_short_answer_standard_correction_reopens_only_affected_question_and_preserves_first_review(
    client, monkeypatch
):
    exam, detail, _, first_no, _, second_no = await manual_case(client, monkeypatch)
    client.cookies.clear()
    headers = await user_login(client, first_no, "TeacherChanged!123")
    for index, score in enumerate(["2.0", "1.5"]):
        question = detail["questions"][index]
        graded = await client.post(
            f"/api/staff/answers/{question['answer']['id']}/grade",
            headers=headers,
            json=grade_payload(question, score),
        )
        assert graded.status_code == 200, graded.text
        detail = graded.json()
    completed_at = detail["task"]["first_review_completed_at"]
    unaffected = detail["questions"][1]["answer"]
    headers = await admin_login(client)
    question = detail["questions"][0]
    correction = await client.post(
        f"/api/staff/exams/{exam['id']}/questions/{question['id']}/correct-standard",
        headers=headers,
        json={
            "version": exam["version"],
            "grading_revision": question["grading_revision"],
            "standard_answer": "增加一个必需论据",
            "explanation": "评分依据更正说明",
            "reason": "原参考依据漏列论据",
        },
    )
    assert correction.status_code == 200, correction.text
    assert correction.json()["grading_revision"] == 2
    headers = await user_login(client, second_no, "TeacherChanged!123")
    refreshed = await client.post(
        f"/api/staff/exams/{exam['id']}/grading/refresh", headers=headers, json={}
    )
    assert refreshed.status_code == 200, refreshed.text
    current = (await client.get(f"/api/staff/attempts/{detail['id']}")).json()
    assert current["final_score"] is None
    assert current["task"]["first_review_completed_at"] == completed_at
    assert current["task"]["status"] == "PENDING"
    assert current["questions"][0]["answer"]["grading_status"] == "PENDING"
    assert current["questions"][1]["answer"] == unaffected
    assert current["can_grade"] is True
    stale = await client.post(
        f"/api/staff/answers/{question['answer']['id']}/grade",
        headers=headers,
        json=grade_payload(question, "1.0", "依更正依据重判"),
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"]["code"] == "VERSION_CONFLICT"
    updated_question = current["questions"][0]
    judged = await client.post(
        f"/api/staff/answers/{updated_question['answer']['id']}/grade",
        headers=headers,
        json=grade_payload(updated_question, "1.0", "依更正依据重判"),
    )
    assert judged.status_code == 200, judged.text
    assert judged.json()["final_score"] == "2.5"
    assert judged.json()["grading_revision"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("corrected_type", ["TRUE_FALSE", "SHORT_ANSWER"])
async def test_automatic_standard_correction_waits_to_complete_task_without_reopening_other_manual_scores(
    client, monkeypatch, corrected_type
):
    teacher, teacher_no = await create_teacher(client)
    await teacher_login(client, teacher_no)
    _, number = await create_student(client)
    objective = corrected_type == "TRUE_FALSE"
    exam = await released_exam(
        client,
        shuffle_questions=False,
        grader_ids=[teacher["id"]],
        question_payloads=[
            question_payload(type="SHORT_ANSWER", options=[], standard_answer="简答评分依据"),
            question_payload(
                type=corrected_type,
                options=[],
                standard_answer=False if objective else "空答题评分依据",
            ),
        ],
    )
    attempt, _ = await submit_values(
        client, number, exam, ["非空简答", False if objective else None]
    )
    headers = await admin_login(client)
    advance_server_clock(monkeypatch, datetime.fromisoformat(exam["end_at"]) + timedelta(seconds=1))
    await client.post(f"/api/staff/exams/{exam['id']}/grading/refresh", headers=headers, json={})
    client.cookies.clear()
    headers = await user_login(client, teacher_no, "TeacherChanged!123")
    attempt_url = f"/api/staff/attempts/{attempt['id']}"
    detail = (await client.get(attempt_url)).json()
    manual_question = detail["questions"][0]
    finished = await client.post(
        f"/api/staff/answers/{manual_question['answer']['id']}/grade",
        headers=headers,
        json=grade_payload(manual_question, "2.0"),
    )
    assert finished.status_code == 200, finished.text
    detail = finished.json()
    assert detail["final_score"] == ("4.5" if objective else "2.0")
    assert detail["task"]["status"] == "COMPLETED"
    first_completed_at = detail["task"]["first_review_completed_at"]
    manual_answer = detail["questions"][0]["answer"]
    question = detail["questions"][1]
    headers = await admin_login(client)
    corrected = await client.post(
        f"/api/staff/exams/{exam['id']}/questions/{question['id']}/correct-standard",
        headers=headers,
        json={
            "version": exam["version"],
            "grading_revision": question["grading_revision"],
            "standard_answer": True if objective else "更正后的空答题依据",
            "reason": "更正自动评分依据",
        },
    )
    assert corrected.status_code == 200, corrected.text
    pending = (await client.get(attempt_url)).json()
    assert pending["grading_status"] == "PENDING"
    assert pending["final_score"] is None
    assert pending["task"]["status"] == "IN_PROGRESS"
    assert pending["task"]["completed_at"] is None
    assert pending["task"]["grading_revision"] == 2
    assert pending["task"]["first_review_completed_at"] == first_completed_at
    assert pending["questions"][0]["answer"] == manual_answer
    tasks = (await client.get("/api/staff/grading-tasks", params={"exam_id": exam["id"]})).json()
    assert tasks["items"][0]["status"] == "IN_PROGRESS"
    assert tasks["items"][0]["completed_at"] is None
    assert tasks["items"][0]["grading_revision"] == 2
    refreshed = await client.post(
        f"/api/staff/exams/{exam['id']}/grading/refresh", headers=headers, json={}
    )
    assert refreshed.status_code == 200, refreshed.text
    current = (await client.get(attempt_url)).json()
    assert current["grading_status"] == "GRADED"
    assert current["final_score"] == "2.0"
    assert current["task"]["status"] == "COMPLETED"
    assert current["task"]["completed_at"] is not None
    assert current["task"]["first_review_completed_at"] == first_completed_at
    assert current["questions"][0]["answer"] == manual_answer
    history = (await client.get(f"/api/staff/answers/{question['answer']['id']}/history")).json()[
        "items"
    ]
    assert [(row["old_score"], row["new_score"]) for row in history] == [
        (None, "2.5" if objective else "0.0"),
        ("2.5" if objective else "0.0", "0.0"),
    ]


@pytest.mark.asyncio
async def test_concurrent_grades_reject_stale_answer_version_and_record_only_winner(
    client, monkeypatch
):
    _, detail, _, first_no, _, _ = await manual_case(client, monkeypatch)
    client.cookies.clear()
    headers = await user_login(client, first_no, "TeacherChanged!123")
    question = detail["questions"][0]
    responses = await asyncio.wait_for(
        asyncio.gather(
            *[
                client.post(
                    f"/api/staff/answers/{question['answer']['id']}/grade",
                    headers=headers,
                    json=grade_payload(question, score),
                )
                for score in ["1.0", "2.0"]
            ]
        ),
        timeout=10,
    )
    assert sorted(response.status_code for response in responses) == [200, 409]
    loser = next(response for response in responses if response.status_code == 409)
    assert loser.json()["detail"]["code"] == "VERSION_CONFLICT"
    winner = next(response.json() for response in responses if response.status_code == 200)
    assert winner["task"]["first_review_completed_at"] is None
    history = (await client.get(f"/api/staff/answers/{question['answer']['id']}/history")).json()[
        "items"
    ]
    assert len(history) == 1
    assert history[0]["new_score"] in ["1.0", "2.0"]
    current = (await client.get(f"/api/staff/attempts/{detail['id']}")).json()
    assert current["questions"][0]["answer"]["score"] == history[0]["new_score"]


@pytest.mark.asyncio
async def test_exam_with_no_remaining_active_grader_creates_unassigned_task_for_admin(
    client, monkeypatch
):
    teacher, _ = await create_teacher(client)
    _, number = await create_student(client)
    exam = await released_exam(
        client,
        shuffle_questions=False,
        grader_ids=[teacher["id"]],
        question_payloads=[
            question_payload(type="SHORT_ANSWER", options=[], standard_answer="参考")
        ],
    )
    attempt, _ = await submit_values(client, number, exam, ["待阅卷"])
    headers = await admin_login(client)
    assert (
        await client.patch(
            f"/api/admin/users/{teacher['id']}", headers=headers, json={"status": "DEACTIVATED"}
        )
    ).status_code == 200
    advance_server_clock(monkeypatch, datetime.fromisoformat(exam["end_at"]) + timedelta(seconds=1))
    response = await client.post(
        f"/api/staff/exams/{exam['id']}/grading/refresh", headers=headers, json={}
    )
    assert response.status_code == 200, response.text
    detail = (await client.get(f"/api/staff/attempts/{attempt['id']}")).json()
    assert detail["task"]["status"] == "UNASSIGNED"
    assert detail["task"]["assigned_teacher"] is None
    assert detail["can_grade"] is False
    assert detail["can_reassign"] is True
