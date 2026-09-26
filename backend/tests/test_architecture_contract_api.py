import uuid

import pytest

from app.modules.identity.models import RegistrationReview


@pytest.mark.asyncio
async def test_registration_uses_explicit_application_contract(client):
    suffix = uuid.uuid4().hex[:8]
    csrf = (await client.get("/api/auth/csrf")).json()["csrf_token"]
    response = await client.post(
        "/api/auth/register",
        headers={"X-CSRF-Token": csrf},
        json={
            "student_no": f"DTO{suffix}",
            "real_name": "响应契约学生",
            "email": f"dto-{suffix}@example.com",
            "phone_number": "13800138000",
            "password": "ValidPassword!123",
        },
    )
    assert response.status_code == 201
    assert set(response.json()["application"]) == {
        "id",
        "status",
        "reason",
        "submitted_profile",
        "submitted_at",
        "reviewed_at",
        "reviewer_id",
    }
    assert set(response.json()["application"]["submitted_profile"]) == {
        "student_no",
        "real_name",
        "email",
        "phone_number",
    }
    schema = (await client.get("/openapi.json")).json()
    success = schema["paths"]["/api/auth/register"]["post"]["responses"]["201"]
    assert success["content"]["application/json"]["schema"].get("$ref")
    for path, operations in schema["paths"].items():
        for operation in operations.values():
            for code, contract in operation.get("responses", {}).items():
                if code.startswith("2") and code != "204":
                    content = contract["content"]
                    if "application/json" in content:
                        assert content["application/json"]["schema"].get("$ref"), path
                    else:
                        assert path == "/api/assets/{asset_id}"
                        assert set(content) == {"image/png", "image/jpeg", "image/webp"}
                        assert all(
                            value["schema"] == {"type": "string", "format": "binary"}
                            for value in content.values()
                        )
    submitted = schema["components"]["schemas"]["SubmittedProfile"]
    assert set(submitted["properties"]) == {"student_no", "real_name", "email", "phone_number"}
    # 模拟 JSONB 增加内部字段，公开申请 DTO 仍只输出四个资料字段。
    resources = client._transport.app.state.resources
    async with resources.session_factory() as session:
        async with session.begin():
            review = await session.get(
                RegistrationReview, uuid.UUID(response.json()["application"]["id"])
            )
            review.submitted_profile = {**review.submitted_profile, "internal_note": "不应公开"}
    login = await client.post(
        "/api/auth/login",
        headers={"X-CSRF-Token": csrf},
        json={"login_name": f"DTO{suffix}", "password": "ValidPassword!123"},
    )
    assert login.status_code == 200
    application = await client.get("/api/student/application")
    assert application.status_code == 200
    assert set(application.json()["application"]["submitted_profile"]) == {
        "student_no",
        "real_name",
        "email",
        "phone_number",
    }
