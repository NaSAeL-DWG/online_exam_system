import asyncio
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import event

from app.modules.exam.models import Exam
from app.modules.question.models import Question
from content_helpers import create_teacher, teacher_login
from test_classes_api import admin_login, save_cookies
from test_exams_api import create_exam, draft_payload
from test_papers_api import create_paper


@pytest.mark.asyncio
async def test_teachers_publishing_with_each_other_as_graders_do_not_deadlock(client):
    first, first_no = await create_teacher(client)
    second, second_no = await create_teacher(client)
    headers = await admin_login(client)
    paper, _ = await create_paper(client, headers, short_answer=True)
    exam = await create_exam(client, headers, paper)
    url = f"/api/staff/exams/{exam['id']}"
    exam = (
        await client.put(
            url, headers=headers, json=draft_payload(exam, grader_ids=[first["id"], second["id"]])
        )
    ).json()
    first_headers = await teacher_login(client, first_no)
    first_cookies = save_cookies(client)
    second_headers = await teacher_login(client, second_no)
    second_cookies = save_cookies(client)
    resources = client._transport.app.state.resources
    ready = asyncio.Event()
    arrivals = 0

    def observe_exam_lock(connection, cursor, statement, parameters, context, executemany):
        nonlocal arrivals
        if "FROM exam" in statement and "FOR UPDATE" in statement:
            arrivals += 1
            if arrivals == 2:
                ready.set()

    # 事务fixture暂持考试锁，让两位教师均已通过身份锁后同时竞争公开发布接口。
    async with resources.session_factory() as blocker:
        async with blocker.begin():
            await blocker.get(Exam, UUID(exam["id"]), with_for_update=True)
            event.listen(resources.engine.sync_engine, "before_cursor_execute", observe_exam_lock)
            try:
                async with (
                    AsyncClient(
                        transport=client._transport,
                        base_url="http://testserver",
                        cookies=first_cookies,
                    ) as one,
                    AsyncClient(
                        transport=client._transport,
                        base_url="http://testserver",
                        cookies=second_cookies,
                    ) as two,
                ):
                    tasks = [
                        asyncio.create_task(
                            one.post(
                                url + "/publish",
                                headers=first_headers,
                                json={"version": exam["version"]},
                            )
                        ),
                        asyncio.create_task(
                            two.post(
                                url + "/publish",
                                headers=second_headers,
                                json={"version": exam["version"]},
                            )
                        ),
                    ]
                    await asyncio.wait_for(ready.wait(), timeout=10)
                    await blocker.commit()
                    responses = await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)
            finally:
                event.remove(
                    resources.engine.sync_engine, "before_cursor_execute", observe_exam_lock
                )
    assert sorted(response.status_code for response in responses) == [200, 409]
    loser = next(response for response in responses if response.status_code == 409)
    assert loser.json()["detail"]["code"] == "VERSION_CONFLICT"


@pytest.mark.asyncio
async def test_two_papers_can_add_each_others_questions_without_lock_inversion(client):
    headers = await admin_login(client)
    first, first_question = await create_paper(client, headers)
    second, second_question = await create_paper(client, headers)
    cookies = save_cookies(client)
    resources = client._transport.app.state.resources
    ready = asyncio.Event()
    arrivals = 0

    def observe_question_lock(connection, cursor, statement, parameters, context, executemany):
        nonlocal arrivals
        if "FROM question" in statement and "FOR UPDATE" in statement:
            arrivals += 1
            if arrivals == 2:
                ready.set()

    async with resources.session_factory() as blocker:
        async with blocker.begin():
            for value in sorted([first_question["id"], second_question["id"]]):
                await blocker.get(Question, UUID(value), with_for_update=True)
            event.listen(
                resources.engine.sync_engine, "before_cursor_execute", observe_question_lock
            )
            try:
                async with (
                    AsyncClient(
                        transport=client._transport, base_url="http://testserver", cookies=cookies
                    ) as one,
                    AsyncClient(
                        transport=client._transport, base_url="http://testserver", cookies=cookies
                    ) as two,
                ):
                    tasks = []
                    for connection, paper, question_ids in [
                        (one, first, [first_question["id"], second_question["id"]]),
                        (two, second, [second_question["id"], first_question["id"]]),
                    ]:
                        tasks.append(
                            asyncio.create_task(
                                connection.put(
                                    f"/api/staff/papers/{paper['id']}",
                                    headers=headers,
                                    json={
                                        "version": 1,
                                        "title": "并发调序",
                                        "questions": [
                                            {"question_id": value, "score": "1.0"}
                                            for value in question_ids
                                        ],
                                    },
                                )
                            )
                        )
                    await asyncio.wait_for(ready.wait(), timeout=10)
                    await blocker.commit()
                    responses = await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)
            finally:
                event.remove(
                    resources.engine.sync_engine, "before_cursor_execute", observe_question_lock
                )
    assert [response.status_code for response in responses] == [200, 200]
    assert all(response.json()["total_score"] == "2.0" for response in responses)
