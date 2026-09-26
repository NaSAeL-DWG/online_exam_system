import pytest
from content_helpers import create_teacher
from test_classes_api import admin_login
from test_papers_api import create_paper
from test_exams_api import create_exam, draft_payload


@pytest.mark.asyncio
async def test_publish_requires_complete_configuration_and_active_grader_then_locks_draft(client):
    teacher, _ = await create_teacher(client)
    headers = await admin_login(client)
    paper, _ = await create_paper(client, headers, short_answer=True)
    exam = await create_exam(client, headers, paper)
    url = f"/api/staff/exams/{exam['id']}"
    incomplete = await client.post(url + "/publish", headers=headers, json={"version": 1})
    assert incomplete.status_code == 409
    assert incomplete.json()["detail"]["code"] == "EXAM_INCOMPLETE"
    configured = await client.put(url, headers=headers, json=draft_payload(exam))
    exam = configured.json()
    missing = await client.post(
        url + "/publish", headers=headers, json={"version": exam["version"]}
    )
    assert missing.status_code == 409
    assert missing.json()["detail"]["code"] == "GRADER_REQUIRED"
    exam = (
        await client.put(url, headers=headers, json=draft_payload(exam, grader_ids=[teacher["id"]]))
    ).json()
    published = await client.post(
        url + "/publish", headers=headers, json={"version": exam["version"]}
    )
    assert published.status_code == 200, published.text
    exam = published.json()
    assert exam["status"] == "RELEASED"
    locked = await client.put(url, headers=headers, json=draft_payload(exam))
    assert locked.status_code == 409
    assert locked.json()["detail"]["code"] == "EXAM_LOCKED"
    withdrawn = await client.post(
        url + "/withdraw", headers=headers, json={"version": exam["version"]}
    )
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "DRAFT"


@pytest.mark.asyncio
async def test_publish_uses_current_active_graders_but_keeps_inactive_assignment_history(client):
    first, _ = await create_teacher(client)
    second, _ = await create_teacher(client)
    headers = await admin_login(client)
    paper, _ = await create_paper(client, headers, short_answer=True)
    exam = await create_exam(client, headers, paper)
    url = f"/api/staff/exams/{exam['id']}"
    exam = (
        await client.put(
            url, headers=headers, json=draft_payload(exam, grader_ids=[first["id"], second["id"]])
        )
    ).json()
    assert (
        await client.patch(
            f"/api/admin/users/{first['id']}", headers=headers, json={"status": "DEACTIVATED"}
        )
    ).status_code == 200
    published = await client.post(
        url + "/publish", headers=headers, json={"version": exam["version"]}
    )
    assert published.status_code == 200, published.text
    assert set(published.json()["grader_ids"]) == {first["id"], second["id"]}
    exam = (
        await client.post(
            url + "/withdraw", headers=headers, json={"version": published.json()["version"]}
        )
    ).json()
    await client.patch(
        f"/api/admin/users/{second['id']}", headers=headers, json={"status": "DEACTIVATED"}
    )
    blocked = await client.post(
        url + "/publish", headers=headers, json={"version": exam["version"]}
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "GRADER_REQUIRED"
