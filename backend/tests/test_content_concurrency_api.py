import asyncio
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import event

from app.modules.exam.models import Exam
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
