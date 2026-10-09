async def test_registration_validation_returns_chinese_field_reasons_without_raw_input(client):
    """公开 HTTP 错误保留 fields 契约，非法资料不会泄露输入或英文解析细节。"""

    token = (await client.get("/api/auth/csrf")).json()["csrf_token"]
    response = await client.post(
        "/api/auth/register",
        headers={"X-CSRF-Token": token},
        json={
            "student_no": "validation-student",
            "real_name": "字段校验学生",
            "email": "private-invalid-email",
            "phone_number": "123",
            "password": "Secret9!",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "VALIDATION_ERROR",
        "message": "请检查填写内容",
        "fields": {
            "body.email": "请输入有效的邮箱地址",
            "body.phone_number": "至少需要5个字符",
            "body.password": "至少需要10个字符",
        },
    }
    assert "private-invalid-email" not in response.text
    assert "Secret9!" not in response.text


async def test_nested_validation_keeps_field_paths_with_chinese_constraint_reasons(client):
    """嵌套题目字段仍可定位，UUID和小数错误不携带原始诊断文本。"""

    from test_classes_api import admin_login

    headers = await admin_login(client)
    response = await client.post(
        "/api/staff/papers",
        headers=headers,
        json={
            "title": "字段校验试卷",
            "questions": [{"question_id": "private-invalid-id", "score": "1.234"}],
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["fields"] == {
        "body.questions.0.question_id": "请选择有效对象",
        "body.questions.0.score": "最多保留1位小数",
    }
    assert "private-invalid-id" not in response.text


async def test_unrecognized_model_validation_has_chinese_fallback_without_raw_message(client):
    """自定义模型错误使用受控兜底，不能直接回显 Value error 或内部异常。"""

    from uuid import uuid4
    from test_classes_api import admin_login

    headers = await admin_login(client)
    response = await client.post(
        f"/api/staff/reviews/{uuid4()}/decision",
        headers=headers,
        json={"decision": "REJECTED", "reason": ""},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["fields"] == {"body": "内容不符合要求，请检查后重试"}
    assert "Value error" not in response.text
