from uuid import uuid4

from test_classes_api import admin_login, user_login


async def create_teacher(client):
    headers = await admin_login(client)
    number = "T" + uuid4().hex[:12]
    response = await client.post(
        "/api/admin/teachers",
        headers=headers,
        json={
            "teacher_no": number,
            "real_name": "共享教师",
            "email": f"{number}@example.com",
            "phone_number": "13800138000",
            "temporary_password": "TemporaryPass!123",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["user"], number


async def teacher_login(client, number):
    client.cookies.clear()
    headers = await user_login(client, number, "TemporaryPass!123")
    assert (
        await client.put(
            "/api/auth/password",
            headers=headers,
            json={"current_password": "TemporaryPass!123", "new_password": "TeacherChanged!123"},
        )
    ).status_code == 204
    client.cookies.clear()
    return await user_login(client, number, "TeacherChanged!123")


async def create_student(client):
    headers = await admin_login(client)
    number = "S" + uuid4().hex[:12]
    registered = await client.post(
        "/api/auth/register",
        headers=headers,
        json={
            "student_no": number,
            "real_name": "考试学生",
            "email": f"{number}@example.com",
            "phone_number": "13800138001",
            "password": "ValidPassword!123",
        },
    )
    assert registered.status_code == 201, registered.text
    response = await client.post(
        f"/api/staff/reviews/{registered.json()['application']['id']}/decision",
        headers=headers,
        json={"decision": "APPROVED"},
    )
    assert response.status_code == 200
    return registered.json()["user"], number
