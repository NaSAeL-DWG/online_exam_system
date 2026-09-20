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


def save_cookies(client):
    return {cookie.name: cookie.value for cookie in client.cookies.jar}


def restore_cookies(client, values):
    client.cookies.clear()
    for name, value in values.items():
        client.cookies.set(name, value)


@pytest.mark.asyncio
async def test_deactivation_and_password_reset_revoke_old_sessions(client):
    suffix = uuid.uuid4().hex[:8]
    teacher_no = f"X{suffix}"
    old_password = "TemporaryPass!123"
    admin_headers = await login_admin(client)
    created = await client.post(
        "/api/admin/teachers",
        headers=admin_headers,
        json={
            "teacher_no": teacher_no,
            "real_name": "停用教师",
            "email": f"disabled-{suffix}@example.com",
            "phone_number": "13800138010",
            "temporary_password": old_password,
        },
    )
    teacher_id = created.json()["user"]["id"]
    admin_cookies = save_cookies(client)

    client.cookies.clear()
    await login(client, teacher_no, old_password)
    teacher_cookies = save_cookies(client)
    restore_cookies(client, admin_cookies)
    disabled = await client.patch(
        f"/api/admin/users/{teacher_id}",
        headers=admin_headers,
        json={"status": "DEACTIVATED"},
    )
    assert disabled.status_code == 200

    restore_cookies(client, teacher_cookies)
    old_session = await client.get("/api/auth/me")
    assert old_session.status_code == 401
    assert old_session.json()["detail"]["code"] == "SESSION_INVALID"
    client.cookies.clear()
    blocked_login = await client.post(
        "/api/auth/login",
        headers=await csrf_headers(client),
        json={"login_name": teacher_no, "password": old_password},
    )
    assert blocked_login.status_code == 403

    restore_cookies(client, admin_cookies)
    restored = await client.patch(
        f"/api/admin/users/{teacher_id}", headers=admin_headers, json={"status": "ACTIVATED"}
    )
    assert restored.status_code == 200
    reset = await client.post(
        f"/api/admin/users/{teacher_id}/reset-password",
        headers=admin_headers,
        json={"temporary_password": "ResetPassword!123"},
    )
    assert reset.status_code == 204
    client.cookies.clear()
    old_login = await client.post(
        "/api/auth/login",
        headers=await csrf_headers(client),
        json={"login_name": teacher_no, "password": old_password},
    )
    assert old_login.status_code == 401
    client.cookies.clear()
    await login(client, teacher_no, "ResetPassword!123")
    assert (await client.get("/api/auth/me")).json()["user"]["must_change_password"] is True


@pytest.mark.asyncio
async def test_identity_correction_conflict_is_409_and_keeps_original_login(client):
    suffix = uuid.uuid4().hex[:8]
    headers = await login_admin(client)
    users = []
    for marker in ("P", "Q"):
        response = await client.post(
            "/api/admin/teachers",
            headers=headers,
            json={
                "teacher_no": f"{marker}{suffix}",
                "real_name": f"更正教师{marker}",
                "email": f"identity-{marker.lower()}-{suffix}@example.com",
                "phone_number": f"13800138{30 if marker == 'P' else 31}",
                "temporary_password": "TemporaryPass!123",
            },
        )
        assert response.status_code == 201
        users.append(response.json()["user"])
    conflict = await client.patch(
        f"/api/admin/users/{users[1]['id']}",
        headers=headers,
        json={"login_name": users[0]["login_name"]},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "LOGIN_NAME_EXISTS"
    listed = await client.get("/api/admin/teachers")
    current = next(item for item in listed.json()["items"] if item["id"] == users[1]["id"])
    assert current["login_name"] == users[1]["login_name"]


@pytest.mark.asyncio
async def test_admin_and_teacher_status_transitions_are_restricted(client):
    suffix = uuid.uuid4().hex[:8]
    headers = await login_admin(client)
    admin_id = (await client.get("/api/auth/me")).json()["user"]["id"]
    teacher = await client.post(
        "/api/admin/teachers",
        headers=headers,
        json={
            "teacher_no": f"Z{suffix}",
            "real_name": "状态教师",
            "email": f"status-{suffix}@example.com",
            "phone_number": "13800138032",
            "temporary_password": "TemporaryPass!123",
        },
    )
    teacher_id = teacher.json()["user"]["id"]
    cases = [
        (admin_id, "DEACTIVATED", 409, "ADMIN_DEACTIVATION_FORBIDDEN"),
        (admin_id, "WAITING_ACTIVATE", 422, "VALIDATION_ERROR"),
        (teacher_id, "WAITING_ACTIVATE", 422, "VALIDATION_ERROR"),
    ]
    for user_id, status, expected_status, expected_code in cases:
        response = await client.patch(
            f"/api/admin/users/{user_id}", headers=headers, json={"status": status}
        )
        assert response.status_code == expected_status
        assert response.json()["detail"]["code"] == expected_code


@pytest.mark.asyncio
async def test_deactivated_rejected_student_restores_to_waiting_without_bypassing_review(client):
    suffix = uuid.uuid4().hex[:8]
    student_no = f"V{suffix}"
    password = "ValidPassword!123"
    headers = await csrf_headers(client)
    registered = await client.post(
        "/api/auth/register",
        headers=headers,
        json={
            "student_no": student_no,
            "real_name": "恢复审核学生",
            "email": f"restore-{suffix}@example.com",
            "phone_number": "13800138033",
            "password": password,
        },
    )
    student_id = registered.json()["user"]["id"]
    review_id = registered.json()["application"]["id"]
    client.cookies.clear()
    admin_headers = await login_admin(client)
    direct_activation = await client.patch(
        f"/api/admin/users/{student_id}",
        headers=admin_headers,
        json={"status": "ACTIVATED"},
    )
    assert direct_activation.status_code == 409
    assert direct_activation.json()["detail"]["code"] == "REVIEW_REQUIRED"
    rejected = await client.post(
        f"/api/staff/reviews/{review_id}/decision",
        headers=admin_headers,
        json={"decision": "REJECTED", "reason": "资料需更正"},
    )
    assert rejected.status_code == 200
    disabled = await client.patch(
        f"/api/admin/users/{student_id}",
        headers=admin_headers,
        json={"status": "DEACTIVATED"},
    )
    assert disabled.status_code == 200
    restored = await client.patch(
        f"/api/admin/users/{student_id}",
        headers=admin_headers,
        json={"status": "ACTIVATED"},
    )
    assert restored.status_code == 200
    assert restored.json()["user"]["status"] == "WAITING_ACTIVATE"
    client.cookies.clear()
    student_headers = await login(client, student_no, password)
    assert (await client.get("/api/classes")).status_code == 403
    resubmitted = await client.put(
        "/api/student/application",
        headers=student_headers,
        json={
            "student_no": student_no,
            "real_name": "恢复审核学生（已更正）",
            "email": f"restore-fixed-{suffix}@example.com",
            "phone_number": "13800138034",
        },
    )
    assert resubmitted.status_code == 200
    assert resubmitted.json()["application"]["status"] == "PENDING"
