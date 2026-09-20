import uuid

import pytest

from app.config import get_settings


async def admin_login(client):
    settings = get_settings()
    csrf = (await client.get("/api/auth/csrf")).json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}
    response = await client.post(
        "/api/auth/login",
        headers=headers,
        json={"login_name": settings.admin_login_name, "password": settings.admin_password},
    )
    assert response.status_code == 200
    return headers


@pytest.mark.asyncio
async def test_archived_class_rejects_teacher_membership_changes(client):
    suffix = uuid.uuid4().hex[:8]
    headers = await admin_login(client)
    teacher = await client.post(
        "/api/admin/teachers",
        headers=headers,
        json={
            "teacher_no": f"C{suffix}",
            "real_name": "班级教师",
            "email": f"class-{suffix}@example.com",
            "phone_number": "13800138009",
            "temporary_password": "TemporaryPass!123",
        },
    )
    assert teacher.status_code == 201
    teacher_id = teacher.json()["user"]["id"]
    created = await client.post(
        "/api/classes",
        headers=headers,
        json={"name": f"归档测试班-{suffix}", "teacher_ids": [teacher_id]},
    )
    assert created.status_code == 201
    class_id = created.json()["class_info"]["id"]
    archived = await client.patch(
        f"/api/classes/{class_id}", headers=headers, json={"status": "ARCHIVED"}
    )
    assert archived.status_code == 200
    changed = await client.patch(
        f"/api/classes/{class_id}", headers=headers, json={"teacher_ids": []}
    )
    assert changed.status_code == 409
    assert changed.json()["detail"]["code"] == "CLASS_ARCHIVED"
