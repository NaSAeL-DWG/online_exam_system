"""迭代 5 独立 HTTP 验收：真实 PostgreSQL／Redis，断言仅来自公开响应。"""

from datetime import datetime, timedelta

import pytest

from content_helpers import create_student, create_teacher, teacher_login
from iteration5_acceptance_helpers import (
    exam_action,
    image_asset,
    refresh_grading,
    wrong_attempt_case,
)
from test_classes_api import admin_login, user_login
from test_grading_api import grade_payload, submit_values
from test_questions_api import question_payload
from test_student_attempts_api import advance_server_clock, released_exam, student_login


@pytest.mark.asyncio
async def test_withdrawal_revokes_snapshot_review_and_its_image_immediately(client, monkeypatch):
    _, number, exam, attempt, image, image_bytes = await wrong_attempt_case(client, monkeypatch)
    review_url = f"/api/student/attempts/{attempt['id']}/review"
    await student_login(client, number)
    assert (await client.get(review_url)).status_code in {403, 404, 409}
    assert (await client.get(image["url"])).status_code == 403

    published = await exam_action(client, exam, "publish-results")
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "RESULTS_PUBLISHED"
    await student_login(client, number)
    reviewed = await client.get(review_url)
    assert reviewed.status_code == 200, reviewed.text
    assert "独立验收隐藏解析" in reviewed.text
    assert "standard_answer" in reviewed.text
    assert reviewed.headers["cache-control"] == "private, no-store"
    visible_image = await client.get(image["url"])
    assert visible_image.status_code == 200, visible_image.text
    assert visible_image.content == image_bytes

    withdrawn = await exam_action(client, exam, "withdraw-results", reason="独立验收撤回")
    assert withdrawn.status_code == 200, withdrawn.text
    await student_login(client, number)
    assert (await client.get(review_url)).status_code in {403, 404, 409}
    assert (await client.get(image["url"])).status_code == 403


@pytest.mark.asyncio
async def test_mistake_notes_require_current_visibility_and_owner_and_survive_republication(
    client, monkeypatch
):
    _, number, exam, attempt, image, _ = await wrong_attempt_case(client, monkeypatch)
    answer_id = attempt["questions"][0]["answer"]["id"]
    result_url = f"/api/student/results/{exam['id']}"
    mistake_url = f"/api/student/mistakes/{answer_id}"
    annotation_url = mistake_url + "/annotation"
    annotation = {"note": "独立验收备注", "mastered": True}
    headers = await student_login(client, number)
    hidden_result = await client.get(result_url)
    assert hidden_result.status_code == 200, hidden_result.text
    assert hidden_result.json()["result_state"] == "NOT_PUBLISHED"
    assert hidden_result.json()["final_score"] is None
    assert all(row["final_score"] is None for row in hidden_result.json()["attempts"])
    hidden = await client.put(annotation_url, headers=headers, json=annotation)
    assert hidden.status_code == 404, hidden.text

    published = await exam_action(client, exam, "publish-results")
    assert published.status_code == 200, published.text
    headers = await student_login(client, number)
    listed = await client.get("/api/student/mistakes", params={"q": exam["title"]})
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["answer_id"] == answer_id
    updated = await client.put(annotation_url, headers=headers, json=annotation)
    assert updated.status_code == 200, updated.text
    assert updated.json() == annotation
    detail = await client.get(mistake_url)
    assert detail.status_code == 200, detail.text
    assert detail.json()["note"] == annotation["note"]
    assert detail.json()["mastered"] is True

    # 他人即使持有答卷、答案和资源标识，也不能取得反馈或修改学习标记。
    _, other_number = await create_student(client)
    other_headers = await student_login(client, other_number)
    for url in [result_url, mistake_url, f"/api/student/attempts/{attempt['id']}/review"]:
        response = await client.get(url)
        assert response.status_code == 404, response.text
    denied_annotation = await client.put(annotation_url, headers=other_headers, json=annotation)
    assert denied_annotation.status_code == 404, denied_annotation.text
    assert (await client.get(image["url"])).status_code == 403

    withdrawn = await exam_action(client, exam, "withdraw-results", reason="隐藏所有学习反馈")
    assert withdrawn.status_code == 200, withdrawn.text
    headers = await student_login(client, number)
    correcting = await client.get(result_url)
    assert correcting.status_code == 200, correcting.text
    assert correcting.json()["result_state"] == "CORRECTING"
    assert correcting.json()["final_score"] is None
    assert correcting.json()["can_review"] is False
    assert all(row["final_score"] is None for row in correcting.json()["attempts"])
    assert (await client.get("/api/student/mistakes")).json()["total"] == 0
    assert (await client.get(mistake_url)).status_code == 404
    assert (await client.put(annotation_url, headers=headers, json=annotation)).status_code == 404

    republished = await exam_action(client, exam, "publish-results")
    assert republished.status_code == 200, republished.text
    await student_login(client, number)
    result = await client.get(result_url)
    assert result.json()["final_score"] == "0.0"
    assert result.json()["result_state"] == "PUBLISHED"
    restored_note = await client.get(mistake_url)
    assert restored_note.json()["note"] == annotation["note"]
    assert restored_note.json()["mastered"] is True
    assert restored_note.headers["cache-control"] == "private, no-store"


@pytest.mark.asyncio
async def test_each_partial_or_blank_error_keeps_snapshot_and_rejudged_full_score_disappears(
    client, monkeypatch
):
    _, number = await create_student(client)
    multiple = question_payload(
        type="MULTIPLE_CHOICE",
        content="验收部分分快照",
        knowledge_tags=["验收标签一", "验收标签二"],
    )
    multiple["standard_answer"] = [row["id"] for row in multiple["options"]]
    judgement = question_payload(
        type="TRUE_FALSE",
        options=[],
        standard_answer=True,
        content="验收判断快照",
        knowledge_tags=["验收标签一", "验收标签二"],
    )
    exam = await released_exam(
        client,
        question_payloads=[multiple, judgement],
        allow_review=True,
        max_attempts=3,
        shuffle_questions=False,
        shuffle_options=False,
    )
    partial = [multiple["options"][0]["id"]]
    first, _ = await submit_values(client, number, exam, [partial, False])
    second, _ = await submit_values(client, number, exam, [partial, None])
    last, _ = await submit_values(client, number, exam, ["correct", True])
    advance_server_clock(monkeypatch, datetime.fromisoformat(exam["end_at"]) + timedelta(seconds=1))
    await refresh_grading(client, exam)
    published = await exam_action(client, exam, "publish-results")
    assert published.status_code == 200, published.text
    await student_login(client, number)
    mistakes = await client.get("/api/student/mistakes")
    assert mistakes.status_code == 200, mistakes.text
    assert mistakes.json()["total"] == 4
    rows = mistakes.json()["items"]
    assert sorted(row["score"] for row in rows) == ["0.0", "0.0", "1.3", "1.3"]
    assert {row["attempt_id"] for row in rows} == {first["id"], second["id"]}
    empty_id = second["questions"][1]["answer"]["id"]
    first_wrong_id = first["questions"][1]["answer"]["id"]
    blank_detail = await client.get(f"/api/student/mistakes/{empty_id}")
    assert blank_detail.json()["question"]["answer"]["answer_data"] is None
    result = await client.get(f"/api/student/results/{exam['id']}")
    assert result.json()["final_attempt_id"] == last["id"]
    assert result.json()["final_score"] == "5.0"
    analytics = await client.get("/api/student/analytics")
    assert analytics.json()["trend"][0]["score_rate"] == "1.0000"
    assert analytics.json()["knowledge_mistakes"] == [
        {"knowledge_tag": "验收标签一", "count": 4},
        {"knowledge_tag": "验收标签二", "count": 4},
    ]
    assert {row["score_rate"] for row in analytics.json()["type_performance"]} == {"1.0000"}

    # 修改题库和原试卷之后，已创建考试的回看与错题仍使用原快照。
    headers = await admin_login(client)
    source_id = exam["questions"][1]["source_question_id"]
    changed_source = await client.put(
        f"/api/staff/questions/{source_id}",
        headers=headers,
        json=question_payload(
            type="TRUE_FALSE", options=[], standard_answer=False, content="修改后的题库内容"
        )
        | {"version": 1},
    )
    assert changed_source.status_code == 200, changed_source.text
    changed_paper = await client.put(
        f"/api/staff/papers/{exam['source_paper_id']}",
        headers=headers,
        json={"version": 1, "title": "来源已更改", "questions": []},
    )
    assert changed_paper.status_code == 200, changed_paper.text
    await student_login(client, number)
    original = await client.get(f"/api/student/mistakes/{first_wrong_id}")
    assert original.json()["content"] == "验收判断快照"
    assert original.json()["question"]["standard_answer"] is True

    withdrawn = await exam_action(client, exam, "withdraw-results", reason="更正判断依据")
    assert withdrawn.status_code == 200, withdrawn.text
    headers = await admin_login(client)
    corrected = await client.post(
        f"/api/staff/exams/{exam['id']}/questions/{exam['questions'][1]['id']}/correct-standard",
        headers=headers,
        json={
            "version": withdrawn.json()["version"],
            "grading_revision": exam["questions"][1]["grading_revision"],
            "standard_answer": False,
            "reason": "判断依据应为假",
        },
    )
    assert corrected.status_code == 200, corrected.text
    await refresh_grading(client, exam)
    republished = await exam_action(client, exam, "publish-results")
    assert republished.status_code == 200, republished.text
    await student_login(client, number)
    assert (await client.get(f"/api/student/mistakes/{first_wrong_id}")).status_code == 404
    assert (await client.get(f"/api/student/mistakes/{empty_id}")).status_code == 200
    refreshed_result = await client.get(f"/api/student/results/{exam['id']}")
    assert refreshed_result.json()["final_score"] == "2.5"
    review = await client.get(f"/api/student/attempts/{last['id']}/review")
    assert review.json()["questions"][1]["standard_answer"] is False
    assert review.json()["questions"][1]["answer"]["score"] == "0.0"
    latest_analytics = await client.get("/api/student/analytics")
    assert latest_analytics.json()["trend"][0]["score_rate"] == "0.5000"
    by_type = {row["type"]: row for row in latest_analytics.json()["type_performance"]}
    assert by_type["MULTIPLE_CHOICE"]["score_rate"] == "1.0000"
    assert by_type["TRUE_FALSE"]["score_rate"] == "0.0000"


@pytest.mark.asyncio
async def test_public_analytics_never_replaces_pending_last_submission_with_old_graded_score(
    client, monkeypatch
):
    teacher, teacher_number = await create_teacher(client)
    await teacher_login(client, teacher_number)
    _, number = await create_student(client)
    exam = await released_exam(
        client,
        grader_ids=[teacher["id"]],
        question_payloads=[
            question_payload(type="SHORT_ANSWER", options=[], standard_answer="参考")
        ],
        shuffle_questions=False,
        allow_review=True,
    )
    first, _ = await submit_values(client, number, exam, ["较早提交"])
    last, _ = await submit_values(client, number, exam, ["最后待评提交"])
    advance_server_clock(monkeypatch, datetime.fromisoformat(exam["end_at"]) + timedelta(seconds=1))
    await refresh_grading(client, exam)
    # 第一份满分，最后一份仍待人工评分，统计必须没有完成样本。
    client.cookies.clear()
    headers = await user_login(client, teacher_number, "TeacherChanged!123")
    first_detail = await client.get(f"/api/staff/attempts/{first['id']}")
    first_graded = await client.post(
        f"/api/staff/answers/{first_detail.json()['questions'][0]['answer']['id']}/grade",
        headers=headers,
        json=grade_payload(first_detail.json()["questions"][0], "2.5"),
    )
    assert first_graded.status_code == 200, first_graded.text
    analytics_url = f"/api/staff/exams/{exam['id']}/analytics"
    pending = await client.get(analytics_url)
    assert pending.status_code == 200, pending.text
    body = pending.json()
    assert body["expected_count"] is None
    assert body["absent_count"] is None
    assert body["participation_rate"] is None
    assert body["participated_count"] == 1
    assert body["submitted_count"] == 1
    assert body["attempts_count"] == 2
    assert body["submitted_attempts_count"] == 2
    assert body["pending_grading_count"] == 1
    assert body["graded_count"] == 0
    for key in ["average_score", "highest_score", "lowest_score", "pass_rate"]:
        assert body[key] is None, (key, body[key])
    assert body["question_rates"][0]["sample_count"] == 0
    assert body["question_rates"][0]["score_rate"] is None
    blocked = await exam_action(client, exam, "publish-results")
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["code"] == "RESULTS_NOT_READY"

    client.cookies.clear()
    headers = await user_login(client, teacher_number, "TeacherChanged!123")
    last_detail = await client.get(f"/api/staff/attempts/{last['id']}")
    last_graded = await client.post(
        f"/api/staff/answers/{last_detail.json()['questions'][0]['answer']['id']}/grade",
        headers=headers,
        json=grade_payload(last_detail.json()["questions"][0], "0.5"),
    )
    assert last_graded.status_code == 200, last_graded.text
    completed = await client.get(analytics_url)
    assert completed.status_code == 200, completed.text
    body = completed.json()
    assert body["graded_count"] == 1
    assert body["pending_grading_count"] == 0
    assert body["average_score"] == "0.5"
    assert body["highest_score"] == "0.5"
    assert body["lowest_score"] == "0.5"
    assert body["pass_rate"] == "0.0000"
    assert body["question_rates"][0]["sample_count"] == 1
    assert body["question_rates"][0]["score_sum"] == "0.5"
    assert body["question_rates"][0]["score_rate"] == "0.2000"


@pytest.mark.asyncio
async def test_restricted_statistics_exclude_revoked_history_and_restoring_never_revives_it(
    client, monkeypatch
):
    first_student, first_number = await create_student(client)
    second_student, second_number = await create_student(client)
    absent_student, _ = await create_student(client)
    image, _ = await image_asset(client, "green")
    multiple = question_payload(type="MULTIPLE_CHOICE")
    multiple["standard_answer"] = [row["id"] for row in multiple["options"]]
    exam = await released_exam(
        client,
        audience_type="RESTRICTED",
        allow_review=True,
        shuffle_questions=False,
        question_payloads=[
            multiple,
            question_payload(
                type="TRUE_FALSE",
                options=[],
                standard_answer=True,
                explanation=f"资格受限解析 ![图]({image['url']})",
            ),
        ],
    )
    headers = await admin_login(client)
    participant_url = f"/api/staff/exams/{exam['id']}/participants"
    added = await client.post(
        participant_url,
        headers=headers,
        json={"student_ids": [first_student["id"], second_student["id"], absent_student["id"]]},
    )
    assert added.status_code == 200, added.text
    first_attempt, _ = await submit_values(client, first_number, exam, ["correct", True])
    last_attempt, _ = await submit_values(
        client, first_number, exam, [[multiple["options"][0]["id"]], True]
    )
    second_attempt, _ = await submit_values(client, second_number, exam, ["correct", False])
    advance_server_clock(monkeypatch, datetime.fromisoformat(exam["end_at"]) + timedelta(seconds=1))
    await refresh_grading(client, exam)
    published = await exam_action(client, exam, "publish-results")
    assert published.status_code == 200, published.text
    analytics_url = f"/api/staff/exams/{exam['id']}/analytics"
    initial = await client.get(analytics_url)
    assert initial.status_code == 200, initial.text
    body = initial.json()
    assert body["expected_count"] == 3
    assert body["participated_count"] == 2
    assert body["submitted_count"] == 2
    assert body["absent_count"] == 1
    assert body["attempts_count"] == 3
    assert body["graded_count"] == 2
    assert body["participation_rate"] == "0.6667"
    assert body["average_score"] == "3.2"
    assert body["highest_score"] == "3.8"
    assert body["lowest_score"] == "2.5"
    assert body["pass_rate"] == "0.5000"
    assert [row["score_rate"] for row in body["question_rates"]] == ["0.7600", "0.5000"]
    assert [row["count"] for row in body["score_distribution"]] == [0, 0, 1, 1, 0]

    participants = (await client.get(participant_url)).json()["items"]
    first_participant = next(
        row for row in participants if row["user"]["id"] == first_student["id"]
    )
    cancelled = await client.post(
        f"{participant_url}/{first_participant['id']}/cancel",
        headers=await admin_login(client),
        json={"version": first_participant["version"], "reason": "撤销已公布资格"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["used_attempts"] == 2
    assert cancelled.json()["voided_attempts"] == 2
    after_revoke = (await client.get(analytics_url)).json()
    assert after_revoke["expected_count"] == 2
    assert after_revoke["submitted_count"] == 1
    assert after_revoke["graded_count"] == 1
    assert after_revoke["average_score"] == "2.5"
    assert after_revoke["absent_count"] == 1
    headers = await student_login(client, first_number)
    invalid_result = await client.get(f"/api/student/results/{exam['id']}")
    assert invalid_result.json()["result_state"] == "PARTICIPANT_CANCELLED"
    assert invalid_result.json()["attempts"] == []
    assert invalid_result.json()["final_attempt_id"] is None
    assert invalid_result.json()["final_score"] is None
    for attempt in [first_attempt, last_attempt]:
        assert (
            await client.get(f"/api/student/attempts/{attempt['id']}/review")
        ).status_code == 403
    assert (await client.get(image["url"])).status_code == 403
    assert (await client.get("/api/student/mistakes")).json()["total"] == 0
    assert (await client.get("/api/student/analytics")).json()["sample_exam_count"] == 0
    wrong_answer_id = last_attempt["questions"][0]["answer"]["id"]
    assert (
        await client.put(
            f"/api/student/mistakes/{wrong_answer_id}/annotation",
            headers=headers,
            json={"note": "被撤销后不可写", "mastered": False},
        )
    ).status_code == 404

    restored = await client.post(
        f"{participant_url}/{first_participant['id']}/restore",
        headers=await admin_login(client),
        json={"version": cancelled.json()["version"], "reason": "恢复仅资格"},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["used_attempts"] == 2
    assert restored.json()["voided_attempts"] == 2
    after_restore = (await client.get(analytics_url)).json()
    assert after_restore["expected_count"] == 3
    assert after_restore["participated_count"] == 1
    assert after_restore["absent_count"] == 2
    assert after_restore["average_score"] == "2.5"
    await student_login(client, first_number)
    restored_result = (await client.get(f"/api/student/results/{exam['id']}")).json()
    assert restored_result["attempts"] == []
    assert restored_result["final_score"] is None
    assert (
        await client.get(f"/api/student/attempts/{first_attempt['id']}/review")
    ).status_code == 403
    assert (await client.get(image["url"])).status_code == 403

    cancelled_exam = await exam_action(client, exam, "cancel", reason="整场取消")
    assert cancelled_exam.status_code == 200, cancelled_exam.text
    cancelled_statistics = (await client.get(analytics_url)).json()
    assert cancelled_statistics["expected_count"] == 0
    assert cancelled_statistics["submitted_count"] == 0
    assert cancelled_statistics["graded_count"] == 0
    assert cancelled_statistics["average_score"] is None
    await student_login(client, second_number)
    cancelled_result = (await client.get(f"/api/student/results/{exam['id']}")).json()
    assert cancelled_result["result_state"] == "CANCELLED"
    assert cancelled_result["attempts"] == []
    assert (
        await client.get(f"/api/student/attempts/{second_attempt['id']}/review")
    ).status_code == 403
    assert (await client.get("/api/student/mistakes")).json()["total"] == 0
    assert (await client.get("/api/student/analytics")).json()["trend"] == []
    assert (await client.get(image["url"])).status_code == 403
    assert (await exam_action(client, exam, "publish-results")).status_code == 409


@pytest.mark.asyncio
async def test_published_score_without_review_never_exposes_snapshot_details_or_mistake_writes(
    client, monkeypatch
):
    _, number, exam, attempt, image, _ = await wrong_attempt_case(
        client, monkeypatch, allow_review=False
    )
    published = await exam_action(client, exam, "publish-results")
    assert published.status_code == 200, published.text
    headers = await student_login(client, number)
    result_response = await client.get(f"/api/student/results/{exam['id']}")
    assert result_response.status_code == 200, result_response.text
    body = result_response.json()
    assert body["final_score"] == "0.0"
    assert body["can_review"] is False
    assert set(body) == {
        "exam_id",
        "title",
        "exam_status",
        "result_state",
        "participant_status",
        "end_at",
        "total_score",
        "allow_review",
        "can_review",
        "attempts_count",
        "final_attempt_id",
        "final_attempt_no",
        "grading_status",
        "final_score",
        "submitted_at",
        "attempts",
    }
    assert set(body["attempts"][0]) == {
        "id",
        "attempt_no",
        "status",
        "started_at",
        "submitted_at",
        "grading_status",
        "final_score",
        "can_review",
    }
    review = await client.get(f"/api/student/attempts/{attempt['id']}/review")
    assert review.status_code == 403, review.text
    assert review.json()["detail"]["code"] == "REVIEW_FORBIDDEN"
    answer_id = attempt["questions"][0]["answer"]["id"]
    assert (await client.get(f"/api/student/mistakes/{answer_id}")).status_code == 404
    annotation = await client.put(
        f"/api/student/mistakes/{answer_id}/annotation",
        headers=headers,
        json={"note": "不允许回看时不得标记", "mastered": True},
    )
    assert annotation.status_code == 404, annotation.text
    mistakes = await client.get("/api/student/mistakes")
    assert mistakes.json()["total"] == 0
    assert mistakes.json()["items"] == []
    assert (await client.get(image["url"])).status_code == 403
    analytics = await client.get("/api/student/analytics")
    assert analytics.status_code == 200, analytics.text
    assert analytics.json()["sample_exam_count"] == 1
    assert analytics.json()["review_exam_count"] == 0
    assert analytics.json()["trend"][0]["score_rate"] == "0.0000"
    assert analytics.json()["type_performance"] == []
    assert analytics.json()["knowledge_mistakes"] == []
    assert analytics.headers["cache-control"] == "private, no-store"

    # 既有考试详情与提交收据也不因为公布总分而自动附加题目评分依据。
    for url in [f"/api/student/exams/{exam['id']}", f"/api/student/attempts/{attempt['id']}"]:
        response = await client.get(url)
        assert response.status_code == 200, response.text
        for forbidden in [
            "standard_answer",
            "explanation",
            "grader_comment",
            "is_correct",
            "password_hash",
            "active_token_hash",
            "独立验收隐藏解析",
            image["url"],
        ]:
            assert forbidden not in response.text


@pytest.mark.asyncio
async def test_publishing_checks_unfinished_older_attempt_even_when_final_attempt_is_graded(
    client, monkeypatch
):
    teacher, teacher_number = await create_teacher(client)
    await teacher_login(client, teacher_number)
    _, number = await create_student(client)
    exam = await released_exam(
        client,
        grader_ids=[teacher["id"]],
        question_payloads=[
            question_payload(type="SHORT_ANSWER", options=[], standard_answer="依据")
        ],
        allow_review=True,
        shuffle_questions=False,
    )
    first, _ = await submit_values(client, number, exam, ["旧次仍需人工判分"])
    last, _ = await submit_values(client, number, exam, [None])
    advance_server_clock(monkeypatch, datetime.fromisoformat(exam["end_at"]) + timedelta(seconds=1))
    await refresh_grading(client, exam)
    headers = await admin_login(client)
    ready_final = await client.get(f"/api/staff/attempts/{last['id']}")
    assert ready_final.json()["grading_status"] == "GRADED"
    assert ready_final.json()["final_score"] == "0.0"
    blocked = await exam_action(client, exam, "publish-results")
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["code"] == "RESULTS_NOT_READY"

    client.cookies.clear()
    headers = await user_login(client, teacher_number, "TeacherChanged!123")
    pending_old = await client.get(f"/api/staff/attempts/{first['id']}")
    graded = await client.post(
        f"/api/staff/answers/{pending_old.json()['questions'][0]['answer']['id']}/grade",
        headers=headers,
        json=grade_payload(pending_old.json()["questions"][0], "2.5"),
    )
    assert graded.status_code == 200, graded.text
    published = await exam_action(client, exam, "publish-results")
    assert published.status_code == 200, published.text
    await student_login(client, number)
    final = (await client.get(f"/api/student/results/{exam['id']}")).json()
    assert final["final_attempt_id"] == last["id"]
    assert final["final_score"] == "0.0"
    assert [row["final_score"] for row in final["attempts"]] == ["2.5", "0.0"]
