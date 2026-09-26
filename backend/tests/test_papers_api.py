from uuid import uuid4
import pytest

from test_classes_api import admin_login
from test_questions_api import question_payload


async def create_paper(client, headers, *, short_answer=False):
    payload = (
        question_payload(type="SHORT_ANSWER", options=[], standard_answer=None)
        if short_answer
        else question_payload()
    )
    question = (await client.post("/api/staff/questions", headers=headers, json=payload)).json()
    response = await client.post(
        "/api/staff/papers",
        headers=headers,
        json={
            "title": f"试卷-{uuid4()}",
            "questions": [{"question_id": question["id"], "score": "2.5"}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json(), question


@pytest.mark.asyncio
async def test_manual_paper_orders_scores_and_rejects_duplicate_or_closed_questions(client):
    headers = await admin_login(client)
    paper, question = await create_paper(client, headers)
    assert paper["total_score"] == "2.5"
    assert paper["questions"][0]["order_no"] == 1
    assert paper["questions"][0]["question"]["id"] == question["id"]
    duplicate = await client.post(
        "/api/staff/papers",
        headers=headers,
        json={
            "title": "重复试卷",
            "questions": [{"question_id": question["id"], "score": "1.0"}] * 2,
        },
    )
    assert duplicate.status_code == 422
    invalid = await client.post(
        "/api/staff/papers",
        headers=headers,
        json={"title": "小数精度", "questions": [{"question_id": question["id"], "score": "1.25"}]},
    )
    assert invalid.status_code == 422
    await client.post(
        f"/api/staff/questions/{question['id']}/close", headers=headers, json={"version": 1}
    )
    closed = await client.post(
        "/api/staff/papers",
        headers=headers,
        json={"title": "关闭新增", "questions": [{"question_id": question["id"], "score": "1.0"}]},
    )
    assert closed.status_code == 409
    assert closed.json()["detail"]["code"] == "QUESTION_CLOSED"
    detail = await client.get(f"/api/staff/papers/{paper['id']}")
    assert detail.json()["questions"][0]["question"]["status"] == "CLOSED"


@pytest.mark.asyncio
async def test_paper_reorders_scores_detects_stale_edits_and_archives(client):
    headers = await admin_login(client)
    paper, first = await create_paper(client, headers)
    second = (
        await client.post("/api/staff/questions", headers=headers, json=question_payload())
    ).json()
    url = f"/api/staff/papers/{paper['id']}"
    updated = await client.put(
        url,
        headers=headers,
        json={
            "version": 1,
            "title": "重排试卷",
            "questions": [
                {"question_id": second["id"], "score": "3.0"},
                {"question_id": first["id"], "score": "4.5"},
            ],
        },
    )
    assert updated.status_code == 200, updated.text
    assert [item["question_id"] for item in updated.json()["questions"]] == [
        second["id"],
        first["id"],
    ]
    assert updated.json()["total_score"] == "7.5"
    stale = await client.put(
        url, headers=headers, json={"version": 1, "title": "旧版本", "questions": []}
    )
    assert stale.status_code == 409
    archived = await client.post(url + "/archive", headers=headers, json={"version": 2})
    assert archived.status_code == 200
    assert archived.json()["status"] == "ARCHIVED"
    listed = await client.get("/api/staff/papers", params={"q": "重排试卷", "status": "ARCHIVED"})
    assert paper["id"] in [row["id"] for row in listed.json()["items"]]
