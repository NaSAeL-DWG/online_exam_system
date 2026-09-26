import pytest

from content_helpers import create_student
from test_classes_api import admin_login
from test_papers_api import create_paper
from test_exams_api import create_exam


@pytest.mark.asyncio
async def test_audience_expands_classes_once_deduplicates_and_never_silently_restores(client):
    student, _ = await create_student(client)
    headers = await admin_login(client)
    paper, _ = await create_paper(client, headers)
    exam = await create_exam(client, headers, paper)
    classes = []
    for name in ("一班", "二班"):
        created = await client.post(
            "/api/classes", headers=headers, json={"name": name, "teacher_ids": []}
        )
        class_id = created.json()["class_info"]["id"]
        await client.put(
            f"/api/classes/{class_id}/members/{student['id']}",
            headers=headers,
            json={"role": "STUDENT"},
        )
        classes.append(class_id)
    url = f"/api/staff/exams/{exam['id']}/participants"
    added = await client.post(
        url, headers=headers, json={"class_ids": classes, "student_ids": [student["id"]]}
    )
    assert added.status_code == 200, added.text
    assert added.json() == {"added": 1, "existing": 0, "cancelled_user_ids": []}
    for class_id in classes:
        await client.delete(f"/api/classes/{class_id}/members/{student['id']}", headers=headers)
    listed = (await client.get(url)).json()
    assert listed["total"] == 1
    participant = listed["items"][0]
    assert participant["user"]["id"] == student["id"]
    cancelled = await client.post(
        f"{url}/{participant['id']}/cancel",
        headers=headers,
        json={"version": 1, "reason": "取消参考"},
    )
    assert cancelled.status_code == 200, cancelled.text
    repeated = await client.post(url, headers=headers, json={"student_ids": [student["id"]]})
    assert repeated.json()["cancelled_user_ids"] == [student["id"]]
    assert (await client.get(url)).json()["items"][0]["status"] == "CANCELLED"
    restored = await client.post(
        f"{url}/{participant['id']}/restore",
        headers=headers,
        json={"version": 2, "reason": "恢复参考"},
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "ASSIGNED"
    await client.patch(f"/api/classes/{classes[0]}", headers=headers, json={"status": "ARCHIVED"})
    archived = await client.post(url, headers=headers, json={"class_ids": [classes[0]]})
    assert archived.status_code == 409
    assert archived.json()["detail"]["code"] == "CLASS_ARCHIVED"


@pytest.mark.asyncio
async def test_participants_filter_by_student_login_name_and_paginate(client):
    first, _ = await create_student(client)
    second, _ = await create_student(client)
    headers = await admin_login(client)
    paper, _ = await create_paper(client, headers)
    exam = await create_exam(client, headers, paper)
    url = f"/api/staff/exams/{exam['id']}/participants"
    await client.post(url, headers=headers, json={"student_ids": [first["id"], second["id"]]})
    response = await client.get(url, params={"q": second["login_name"], "page_size": 1})
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["user"]["id"] == second["id"]
