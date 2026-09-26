from datetime import datetime, timedelta, timezone
import pytest

from test_classes_api import admin_login
from test_papers_api import create_paper
from test_questions_api import question_payload


async def create_exam(client, headers, paper, **changes):
    response = await client.post(
        "/api/staff/exams",
        headers=headers,
        json={"source_paper_id": paper["id"], "title": "独立考试", "audience_type": "RESTRICTED"}
        | changes,
    )
    assert response.status_code == 201, response.text
    return response.json()


def draft_payload(exam, **changes):
    now = datetime.now(timezone.utc)
    return {
        "version": exam["version"],
        "title": exam["title"],
        "description": None,
        "audience_type": exam["audience_type"],
        "start_at": (now + timedelta(minutes=5)).isoformat(),
        "end_at": (now + timedelta(hours=2)).isoformat(),
        "duration_seconds": 3600,
        "max_attempts": 2,
        "allow_review": True,
        "shuffle_questions": True,
        "shuffle_options": True,
        "multiple_choice_mode": "PARTIAL",
        "pass_percentage": "60.00",
        "grader_ids": [],
        "questions": exam["questions"],
    } | changes


@pytest.mark.asyncio
async def test_exam_snapshots_are_created_immediately_and_never_follow_source_changes(client):
    headers = await admin_login(client)
    paper, question = await create_paper(client, headers)
    first = await create_exam(client, headers, paper)
    second = await create_exam(client, headers, paper)
    assert first["questions"][0]["id"] != second["questions"][0]["id"]
    assert first["questions"][0]["standard_answer"] == question["standard_answer"]
    changed = await client.put(
        f"/api/staff/questions/{question['id']}",
        headers=headers,
        json=question_payload(type="TRUE_FALSE", options=[], standard_answer=False)
        | {"version": 1},
    )
    assert changed.status_code == 200
    removed = await client.put(
        f"/api/staff/papers/{paper['id']}",
        headers=headers,
        json={"version": 1, "title": "移除来源题", "questions": []},
    )
    assert removed.status_code == 200
    for exam in (first, second):
        detail = (await client.get(f"/api/staff/exams/{exam['id']}")).json()
        assert detail["questions"][0]["content"] == question["content"]
        assert detail["questions"][0]["standard_answer"] == question["standard_answer"]
        assert detail["total_score"] == "2.5"


@pytest.mark.asyncio
async def test_draft_edits_are_independent_and_closed_sources_warn_without_allowing_new_use(client):
    headers = await admin_login(client)
    paper, question = await create_paper(client, headers)
    await client.post(
        f"/api/staff/questions/{question['id']}/close", headers=headers, json={"version": 1}
    )
    exam = await create_exam(client, headers, paper)
    assert exam["warnings"]
    url = f"/api/staff/exams/{exam['id']}"
    changed_question = exam["questions"][0] | {"content": "只改考试", "score": "4.5"}
    changed = await client.put(
        url, headers=headers, json=draft_payload(exam, questions=[changed_question])
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["total_score"] == "4.5"
    assert (await client.get(f"/api/staff/questions/{question['id']}")).json()[
        "content"
    ] == question["content"]
    stale = await client.put(url, headers=headers, json=draft_payload(exam))
    assert stale.status_code == 409
    exam = changed.json()
    removed = await client.put(url, headers=headers, json=draft_payload(exam, questions=[]))
    assert removed.status_code == 200
    readd = await client.put(
        url,
        headers=headers,
        json=draft_payload(
            removed.json(), questions=[{"source_question_id": question["id"], "score": "1.0"}]
        ),
    )
    assert readd.status_code == 409
    assert readd.json()["detail"]["code"] == "QUESTION_CLOSED"
