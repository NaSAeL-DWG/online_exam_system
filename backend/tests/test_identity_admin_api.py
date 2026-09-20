import uuid

import pytest

from app.config import get_settings


async def csrf_headers(client):
    token = (await client.get("/api/auth/csrf")).json()["csrf_token"]
    return {"X-CSRF-Token": token}


async def login(client, login_name: str, password: str):
    headers = await csrf_headers(client)
    response = await client.post(
        "/api/auth/login", headers=headers, json={"login_name": login_name, "password": password}
    )
    assert response.status_code == 200, response.text
    return headers


async def login_admin(client):
    settings = get_settings()
    assert settings.admin_login_name and settings.admin_password
    return await login(client, settings.admin_login_name, settings.admin_password)


@pytest.mark.asyncio
async def test_rejected_student_can_resubmit_and_be_approved(client):
    suffix = uuid.uuid4().hex[:8]
    student_no = f"A{suffix}"
    password = "ValidPassword!123"
    headers = await csrf_headers(client)
    registered = await client.post(
        "/api/auth/register",
        headers=headers,
        json={
            "student_no": student_no,
            "real_name": "审核学生",
            "email": f"review-{suffix}@example.com",
            "phone_number": "13800138005",
            "password": password,
        },
    )
    review_id = registered.json()["application"]["id"]
    client.cookies.clear()
    headers = await login_admin(client)
    rejected = await client.post(
        f"/api/staff/reviews/{review_id}/decision",
        headers=headers,
        json={"decision": "REJECTED", "reason": "学号资料不清晰"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["application"]["status"] == "REJECTED"

    client.cookies.clear()
    headers = await login(client, student_no, password)
    resubmitted = await client.put(
        "/api/student/application",
        headers=headers,
        json={
            "student_no": student_no,
            "real_name": "审核学生（已更正）",
            "email": f"review-fixed-{suffix}@example.com",
            "phone_number": "13800138006",
        },
    )
    assert resubmitted.status_code == 200
    assert resubmitted.json()["application"]["status"] == "PENDING"

    client.cookies.clear()
    headers = await login_admin(client)
    approved = await client.post(
        f"/api/staff/reviews/{resubmitted.json()['application']['id']}/decision",
        headers=headers,
        json={"decision": "APPROVED"},
    )
    assert approved.status_code == 200
    client.cookies.clear()
    await login(client, student_no, password)
    me = await client.get("/api/auth/me")
    assert me.json()["user"]["status"] == "ACTIVATED"
    assert (await client.get("/api/classes")).status_code == 403


@pytest.mark.asyncio
async def test_teacher_must_change_temporary_password_before_staff_access(client):
    suffix = uuid.uuid4().hex[:8]
    teacher_no = f"T{suffix}"
    temporary = "TemporaryPass!123"
    headers = await login_admin(client)
    created = await client.post(
        "/api/admin/teachers",
        headers=headers,
        json={
            "teacher_no": teacher_no,
            "real_name": "临时密码教师",
            "email": f"teacher-{suffix}@example.com",
            "phone_number": "13800138007",
            "temporary_password": temporary,
        },
    )
    assert created.status_code == 201
    assert created.json()["user"]["must_change_password"] is True
    client.cookies.clear()
    headers = await login(client, teacher_no, temporary)
    blocked = await client.get("/api/staff/students")
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "PASSWORD_CHANGE_REQUIRED"
    contacts = await client.put(
        "/api/auth/contacts",
        headers=headers,
        json={
            "current_password": temporary,
            "email": f"bypass-{suffix}@example.com",
            "phone_number": "13800138008",
        },
    )
    assert contacts.status_code == 403
    changed = await client.put(
        "/api/auth/password",
        headers=headers,
        json={"current_password": temporary, "new_password": "ChangedPassword!123"},
    )
    assert changed.status_code == 204
    client.cookies.clear()
    await login(client, teacher_no, "ChangedPassword!123")
    assert (await client.get("/api/staff/students")).status_code == 200
