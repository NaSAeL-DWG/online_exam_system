from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.modules.attempt.models import ExamAttempt
from app.modules.attempt.types import AttemptStatus
from content_helpers import create_student
from test_classes_api import admin_login
from test_exams_api import create_exam, draft_payload
from test_papers_api import create_paper


@pytest.mark.asyncio
@pytest.mark.parametrize("status", list(AttemptStatus))
async def test_any_started_history_blocks_withdrawal_and_restore_keeps_void_attempts(
    client, status
):
    student, _ = await create_student(client)
    headers = await admin_login(client)
    paper, _ = await create_paper(client, headers)
    exam = await create_exam(client, headers, paper, audience_type="PUBLIC")
    url = f"/api/staff/exams/{exam['id']}"
    exam = (await client.put(url, headers=headers, json=draft_payload(exam))).json()
    exam = (
        await client.post(url + "/publish", headers=headers, json={"version": exam["version"]})
    ).json()
    await client.post(url + "/participants", headers=headers, json={"student_ids": [student["id"]]})
    participant = (await client.get(url + "/participants")).json()["items"][0]
    resources = client._transport.app.state.resources
    # 学生开始HTTP在迭代3落地；仅通过持久化fixture安排历史，断言全部走公开HTTP。
    async with resources.session_factory() as session:
        async with session.begin():
            now = datetime.now(timezone.utc)
            session.add(
                ExamAttempt(
                    exam_participant_id=UUID(participant["id"]),
                    attempt_no=1,
                    status=status,
                    started_at=now,
                    deadline_at=now + timedelta(hours=1),
                    voided_at=now if status == AttemptStatus.VOID else None,
                    void_reason="历史废弃" if status == AttemptStatus.VOID else None,
                )
            )
    withdrawn = await client.post(
        url + "/withdraw", headers=headers, json={"version": exam["version"]}
    )
    assert withdrawn.status_code == 409
    assert withdrawn.json()["detail"]["code"] == "EXAM_ALREADY_STARTED"
    participant_url = f"{url}/participants/{participant['id']}"
    cancelled = await client.post(
        participant_url + "/cancel", headers=headers, json={"version": 1, "reason": "显式撤销"}
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["used_attempts"] == 1
    assert cancelled.json()["voided_attempts"] == 1
    assert cancelled.json()["status"] == "CANCELLED"
    readded = await client.post(
        url + "/participants", headers=headers, json={"student_ids": [student["id"]]}
    )
    assert readded.json()["cancelled_user_ids"] == [student["id"]]
    restored = await client.post(
        participant_url + "/restore",
        headers=headers,
        json={"version": 2, "reason": "恢复但不重置次数"},
    )
    assert restored.status_code == 200
    assert restored.json()["used_attempts"] == 1
    assert restored.json()["voided_attempts"] == 1
    assert restored.json()["status"] == "ASSIGNED"
    still_blocked = await client.post(
        url + "/withdraw", headers=headers, json={"version": exam["version"]}
    )
    assert still_blocked.json()["detail"]["code"] == "EXAM_ALREADY_STARTED"
