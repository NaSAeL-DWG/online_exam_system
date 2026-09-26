from uuid import uuid4

import pytest

from test_classes_api import admin_login


def question_payload(**changes):
    options = [{"id": str(uuid4()), "content": value} for value in ("甲", "乙")]
    payload = {
        "type": "SINGLE_CHOICE",
        "content": f"题干-{uuid4()}：$x^2$\n```python\nprint(1)\n```",
        "options": options,
        "standard_answer": [options[0]["id"]],
        "explanation": "**解析**",
        "subject": "数学",
        "knowledge_tags": ["代数"],
        "difficulty": "MEDIUM",
    }
    return payload | changes


@pytest.mark.asyncio
async def test_create_question_preserves_markdown_stable_options_and_retrievable_answer(client):
    headers = await admin_login(client)
    payload = question_payload()
    created = await client.post("/api/staff/questions", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    question = created.json()
    detail = await client.get(f"/api/staff/questions/{question['id']}")
    assert detail.status_code == 200
    assert {key: detail.json()[key] for key in payload} == payload
    assert question["version"] == 1


@pytest.mark.asyncio
async def test_four_question_types_validate_answer_structure_and_false_is_valid(client):
    headers = await admin_login(client)
    for kind, answer in [("TRUE_FALSE", False), ("SHORT_ANSWER", None)]:
        response = await client.post(
            "/api/staff/questions",
            headers=headers,
            json=question_payload(type=kind, options=[], standard_answer=answer),
        )
        assert response.status_code == 201, response.text
        assert response.json()["standard_answer"] == answer
    multiple = question_payload(type="MULTIPLE_CHOICE")
    invalid = await client.post("/api/staff/questions", headers=headers, json=multiple)
    assert invalid.status_code == 422
    multiple["standard_answer"] = [option["id"] for option in multiple["options"]]
    assert (
        await client.post("/api/staff/questions", headers=headers, json=multiple)
    ).status_code == 201
    for changes in [
        {"options": []},
        {"standard_answer": [str(uuid4())]},
        {"type": "TRUE_FALSE", "options": [], "standard_answer": "false"},
        {"subject": "   "},
    ]:
        invalid = await client.post(
            "/api/staff/questions", headers=headers, json=question_payload(**changes)
        )
        assert invalid.status_code == 422, invalid.text


@pytest.mark.asyncio
async def test_question_filters_version_conflict_and_close(client):
    headers = await admin_login(client)
    payload = question_payload()
    question = (await client.post("/api/staff/questions", headers=headers, json=payload)).json()
    listed = await client.get(
        "/api/staff/questions",
        params={
            "q": payload["content"].split("：")[0],
            "subject": "数学",
            "tag": "代数",
            "difficulty": "MEDIUM",
            "page_size": 1,
        },
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == question["id"]
    url = f"/api/staff/questions/{question['id']}"
    update = await client.put(
        url, headers=headers, json=payload | {"version": 1, "content": "更新题干"}
    )
    assert update.status_code == 200
    assert update.json()["version"] == 2
    conflict = await client.put(url, headers=headers, json=payload | {"version": 1})
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "VERSION_CONFLICT"
    closed = await client.post(url + "/close", headers=headers, json={"version": 2})
    assert closed.status_code == 200
    assert closed.json()["status"] == "CLOSED"
    assert (await client.get(url)).json()["content"] == "更新题干"
