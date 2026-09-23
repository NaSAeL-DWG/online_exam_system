import uuid

import pytest
from sqlalchemy import event

from test_classes_api import admin_login


@pytest.mark.asyncio
async def test_class_list_is_paginated_and_query_count_does_not_grow_per_class(client):
    marker = f"分页-{uuid.uuid4().hex[:8]}"
    headers = await admin_login(client)
    teacher = await client.post(
        "/api/admin/teachers",
        headers=headers,
        json={
            "teacher_no": marker,
            "real_name": marker,
            "email": f"{uuid.uuid4().hex}@example.com",
            "phone_number": "13800138000",
            "temporary_password": "TemporaryPass!123",
        },
    )
    assert teacher.status_code == 201
    teacher_id = teacher.json()["user"]["id"]
    for index in range(4):
        created = await client.post(
            "/api/classes",
            headers=headers,
            json={
                "name": f"{marker}-{index}",
                "teacher_ids": [teacher_id],
            },
        )
        assert created.status_code == 201
    engine = client._transport.app.state.resources.engine.sync_engine
    statements = []

    def count_queries(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", count_queries)
    try:
        first = await client.get("/api/classes", params={"q": marker, "page_size": 1})
        first_count = len(statements)
        statements.clear()
        all_four = await client.get("/api/classes", params={"q": marker, "page_size": 4})
        four_count = len(statements)
    finally:
        event.remove(engine, "before_cursor_execute", count_queries)
    assert first.status_code == all_four.status_code == 200
    assert first.json()["total"] == 4
    assert len(first.json()["items"]) == 1
    assert first.json()["page"] == 1
    assert first.json()["page_size"] == 1
    assert len(all_four.json()["items"]) == 4
    assert all(
        item["students"] is None and item["student_count"] == 0 for item in all_four.json()["items"]
    )
    assert all(item["teachers"][0]["id"] == teacher_id for item in all_four.json()["items"])
    assert first_count == four_count
    assert four_count == 6


@pytest.mark.asyncio
async def test_account_search_pagination_preserves_role_and_status_filters(client):
    await admin_login(client)
    response = await client.get(
        "/api/admin/users",
        params={
            "user_type": "ADMIN",
            "status": "ACTIVATED",
            "q": "integration-admin",
            "page_size": 1,
        },
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["login_name"] == "integration-admin"
    beyond = await client.get(
        "/api/admin/users", params={"user_type": "ADMIN", "page": 2, "page_size": 1}
    )
    assert beyond.json()["items"] == []
    invalid = await client.get("/api/classes", params={"page_size": 101})
    assert invalid.status_code == 422
