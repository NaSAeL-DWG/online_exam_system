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


async def user_login(client, login_name: str, password: str):
    csrf = (await client.get("/api/auth/csrf")).json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}
    response = await client.post(
        "/api/auth/login", headers=headers, json={"login_name": login_name, "password": password}
    )
    assert response.status_code == 200, response.text
    return headers


def save_cookies(client):
    return {cookie.name: cookie.value for cookie in client.cookies.jar}


def restore_cookies(client, values):
    client.cookies.clear()
    for name, value in values.items():
        client.cookies.set(name, value)


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


@pytest.mark.asyncio
async def test_only_associated_teacher_manages_students_and_student_can_join_multiple_classes(
    client,
):
    suffix = uuid.uuid4().hex[:8]
    admin_headers = await admin_login(client)
    teacher_ids = []
    teacher_numbers = []
    for marker in ("M", "N"):
        teacher_no = f"{marker}{suffix}"
        created = await client.post(
            "/api/admin/teachers",
            headers=admin_headers,
            json={
                "teacher_no": teacher_no,
                "real_name": f"教师{marker}",
                "email": f"teacher-{marker.lower()}-{suffix}@example.com",
                "phone_number": f"13800138{20 if marker == 'M' else 21}",
                "temporary_password": "TemporaryPass!123",
            },
        )
        assert created.status_code == 201
        teacher_ids.append(created.json()["user"]["id"])
        teacher_numbers.append(teacher_no)
    registered = await client.post(
        "/api/auth/register",
        headers=admin_headers,
        json={
            "student_no": f"S{suffix}",
            "real_name": "多班学生",
            "email": f"multi-class-{suffix}@example.com",
            "phone_number": "13800138022",
            "password": "ValidPassword!123",
        },
    )
    student_id = registered.json()["user"]["id"]
    review_id = registered.json()["application"]["id"]
    approved = await client.post(
        f"/api/staff/reviews/{review_id}/decision",
        headers=admin_headers,
        json={"decision": "APPROVED"},
    )
    assert approved.status_code == 200
    class_ids = []
    for marker in ("一", "二"):
        created = await client.post(
            "/api/classes",
            headers=admin_headers,
            json={"name": f"多班测试{marker}-{suffix}", "teacher_ids": [teacher_ids[0]]},
        )
        assert created.status_code == 201
        class_ids.append(created.json()["class_info"]["id"])
    admin_cookies = save_cookies(client)

    client.cookies.clear()
    first_headers = await user_login(client, teacher_numbers[0], "TemporaryPass!123")
    changed = await client.put(
        "/api/auth/password",
        headers=first_headers,
        json={"current_password": "TemporaryPass!123", "new_password": "TeacherChanged!123"},
    )
    assert changed.status_code == 204
    client.cookies.clear()
    first_headers = await user_login(client, teacher_numbers[0], "TeacherChanged!123")
    for class_id in class_ids:
        added = await client.put(
            f"/api/classes/{class_id}/members/{student_id}",
            headers=first_headers,
            json={"role": "STUDENT"},
        )
        assert added.status_code == 200
        assert added.json()["class_info"]["student_count"] == 1

    client.cookies.clear()
    second_headers = await user_login(client, teacher_numbers[1], "TemporaryPass!123")
    await client.put(
        "/api/auth/password",
        headers=second_headers,
        json={"current_password": "TemporaryPass!123", "new_password": "OtherTeacher!123"},
    )
    client.cookies.clear()
    second_headers = await user_login(client, teacher_numbers[1], "OtherTeacher!123")
    forbidden = await client.delete(
        f"/api/classes/{class_ids[0]}/members/{student_id}", headers=second_headers
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["code"] == "FORBIDDEN"

    restore_cookies(client, admin_cookies)
    detail = await client.get(f"/api/classes/{class_ids[1]}")
    assert detail.status_code == 200
    assert detail.json()["class_info"]["students"][0]["id"] == student_id
