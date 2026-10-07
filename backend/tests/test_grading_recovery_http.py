import asyncio
from uuid import uuid4

import pytest
from arq.connections import ArqRedis
from arq.jobs import Job
from httpx import AsyncClient

import grading_reliability_helpers as reliability


prepare_integration_environment = reliability.prepare_integration_environment
recovery_runtime = reliability.recovery_runtime


@pytest.mark.asyncio
async def test_committed_submission_is_graded_by_cli_without_redis(recovery_runtime):
    created = await reliability.make_submitted_attempt(recovery_runtime)
    attempt = created["attempt"]
    assert attempt["status"] == "SUBMITTED"
    assert attempt["grading_status"] == "PENDING"

    recovered = await recovery_runtime.command(
        "recover-grading", "--limit", "100", redis_available=False
    )
    assert attempt["id"] in recovered["graded_attempt_ids"]
    graded = await reliability.staff_attempt(recovery_runtime, attempt["id"])
    assert graded["grading_status"] == "GRADED"
    assert graded["final_score"] == "2.5"

    repeated = await recovery_runtime.command(
        "recover-grading", "--limit", "100", redis_available=False
    )
    assert repeated["graded"] == 0
    assert await reliability.staff_attempt(recovery_runtime, attempt["id"]) == graded


@pytest.mark.asyncio
@pytest.mark.parametrize("recovery_runtime", ["available"], indirect=True)
async def test_submission_enqueues_real_grading_job_and_startup_recovery_is_idempotent(
    recovery_runtime,
):
    created = await reliability.make_submitted_attempt(recovery_runtime)
    attempt = created["attempt"]
    redis = ArqRedis.from_url(recovery_runtime.environment["REDIS_URL"])
    try:
        job = Job(
            f"attempt-grade:{attempt['id']}:1", redis, _queue_name=recovery_runtime.queue_name
        )
        queued = await job.info()
        assert queued is not None, "数据库提交成功后应投递真实判分任务"
        assert queued.function == "grade_attempt_job"
        assert queued.args == (attempt["id"], 1)

        recovered = await recovery_runtime.command("worker", "--burst", queue_available=True)
        assert attempt["id"] in recovered["startup_grading_recovery"]["graded_attempt_ids"]
        assert await job.result(timeout=5) is False
        graded = await reliability.staff_attempt(recovery_runtime, attempt["id"])
        assert graded["grading_status"] == "GRADED"
        assert graded["final_score"] == "2.5"
        repeated = await recovery_runtime.command("worker", "--burst", queue_available=True)
        assert repeated["startup_grading_recovery"]["graded"] == 0
        assert await reliability.staff_attempt(recovery_runtime, attempt["id"]) == graded
    finally:
        await redis.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("recovery_runtime", ["available"], indirect=True)
@pytest.mark.parametrize("cancellation", ["participant", "exam"])
async def test_late_grading_jobs_never_revive_void_attempts_or_tasks(
    recovery_runtime, cancellation
):
    created = await reliability.make_exam(recovery_runtime, short_answers=1, teachers=1)
    exam = created["exam"]
    submitted = await reliability.submit_student(
        recovery_runtime, exam, short_values=["保留审计答案"]
    )
    attempt_id = submitted["attempt"]["id"]
    await reliability.end_exam(recovery_runtime, exam["id"])
    recovered = await recovery_runtime.command("recover-grading", "--limit", "100")
    assert recovered["assigned"] == 1
    assert (await reliability.staff_attempt(recovery_runtime, attempt_id))["task"][
        "status"
    ] == "PENDING"

    async with AsyncClient(base_url=recovery_runtime.base_url) as client:
        headers = await reliability.admin_login(client)
        url = f"/api/staff/exams/{exam['id']}"
        participants = (await client.get(url + "/participants")).json()["items"]
        participant = next(
            item for item in participants if item["user"]["id"] == submitted["student"]["id"]
        )
        if cancellation == "participant":
            participant_url = f"{url}/participants/{participant['id']}"
            cancelled = await client.post(
                participant_url + "/cancel",
                headers=headers,
                json={"version": participant["version"], "reason": "补偿不得复活废弃答卷"},
            )
            assert cancelled.status_code == 200, cancelled.text
            restored = await client.post(
                participant_url + "/restore",
                headers=headers,
                json={"version": cancelled.json()["version"], "reason": "仅恢复新资格"},
            )
            assert restored.status_code == 200, restored.text
        else:
            current = (await client.get(url)).json()
            cancelled = await client.post(
                url + "/cancel",
                headers=headers,
                json={"version": current["version"], "reason": "取消整场保留任务审计"},
            )
            assert cancelled.status_code == 200, cancelled.text

        worker = await recovery_runtime.command("worker", "--burst", queue_available=True)
        assert attempt_id not in worker["startup_grading_recovery"]["graded_attempt_ids"]
        redis = ArqRedis.from_url(recovery_runtime.environment["REDIS_URL"])
        try:
            old = Job(
                f"attempt-grade:{attempt_id}:1", redis, _queue_name=recovery_runtime.queue_name
            )
            assert await old.result(timeout=5) is False
        finally:
            await redis.aclose()
        assert (await client.get(f"/api/staff/attempts/{attempt_id}")).status_code == 404
        assert (await client.get(url + "/attempts")).json()["items"] == []
        assert (await client.get("/api/staff/grading-tasks")).json()["items"] == []
        unchanged = next(
            item
            for item in (await client.get(url + "/participants")).json()["items"]
            if item["id"] == participant["id"]
        )
        assert unchanged["used_attempts"] == 1
        assert unchanged["voided_attempts"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("recovery_runtime", ["lost"], indirect=True)
async def test_running_worker_recovers_submission_after_grading_queue_loss(recovery_runtime):
    redis = ArqRedis.from_url(recovery_runtime.environment["REDIS_URL"])
    redis.default_queue_name = recovery_runtime.queue_name
    process = await recovery_runtime.start_worker()
    try:
        # 先消费一次公开扫描任务，确保学生交卷发生在独立 worker 启动恢复之后。
        ready = await redis.enqueue_job("scan_grading_job", _job_id="ready:" + uuid4().hex)
        assert (await ready.result(timeout=15))["graded"] == 0
        created = await reliability.make_submitted_attempt(recovery_runtime)
        attempt = created["attempt"]
        missing = Job(
            f"attempt-grade:{attempt['id']}:1",
            redis,
            _queue_name=recovery_runtime.environment["ARQ_QUEUE_NAME"],
        )
        assert await missing.info() is not None
        # 模拟 Redis 丢失已入队任务，仅移除此例的队列成员和任务载荷。
        await redis.zrem(recovery_runtime.environment["ARQ_QUEUE_NAME"], missing.job_id)
        await redis.delete(f"arq:job:{missing.job_id}")
        assert await missing.info() is None

        # 只认可真实 ARQ cron 结果；HTTP 查询不代替后台补偿已执行的证据。
        async with asyncio.timeout(40):
            while True:
                assert process.returncode is None, "独立常驻 worker 提前退出"
                results = await redis.all_job_results()
                recovered = any(
                    result.function == "cron:scan_grading_job"
                    and result.success
                    and attempt["id"] in result.result["graded_attempt_ids"]
                    for result in results
                )
                if recovered:
                    break
                await asyncio.sleep(0.25)
        graded = await reliability.staff_attempt(recovery_runtime, attempt["id"])
        assert graded["grading_status"] == "GRADED"
        assert graded["final_score"] == "2.5"
    finally:
        await redis.aclose()
        if process.returncode is None:
            process.terminate()
        await asyncio.wait_for(process.wait(), timeout=10)


@pytest.mark.asyncio
async def test_cli_assigns_whole_attempts_evenly_after_end_and_skips_empty_short_answers(
    recovery_runtime,
):
    created = await reliability.make_exam(recovery_runtime, short_answers=2, teachers=2)
    exam = created["exam"]
    attempts = []
    for _ in range(5):
        submitted = await reliability.submit_student(
            recovery_runtime, exam, short_values=["非空第一题", "非空第二题"]
        )
        attempts.append(submitted["attempt"])
    empty = await reliability.submit_student(recovery_runtime, exam, short_values=["  ", ""])

    before_end = await recovery_runtime.command("recover-grading", "--limit", "100")
    assert before_end["assigned"] == 0
    for attempt in attempts:
        assert (await reliability.staff_attempt(recovery_runtime, attempt["id"]))["task"] is None
    await reliability.end_exam(recovery_runtime, exam["id"])
    recovered = await recovery_runtime.command("recover-grading", "--limit", "100")
    assert recovered["assigned"] == 5

    details = [
        await reliability.staff_attempt(recovery_runtime, attempt["id"]) for attempt in attempts
    ]
    task_ids = [detail["task"]["id"] for detail in details]
    assert len(set(task_ids)) == 5
    counts = [
        sum(detail["task"]["assigned_teacher"]["id"] == teacher["id"] for detail in details)
        for teacher in created["teachers"]
    ]
    assert sorted(counts) == [2, 3]
    for detail in details:
        assert detail["task"]["status"] == "PENDING"
        assert detail["final_score"] is None
        assert [question["answer"]["score"] for question in detail["questions"]] == [
            "2.5",
            None,
            None,
        ]
    blank = await reliability.staff_attempt(recovery_runtime, empty["attempt"]["id"])
    assert blank["task"] is None
    assert blank["grading_status"] == "GRADED"
    assert blank["final_score"] == "2.5"
    repeated = await recovery_runtime.command("recover-grading", "--limit", "100")
    assert repeated["assigned"] == 0
    assert [
        (await reliability.staff_attempt(recovery_runtime, attempt["id"]))["task"]["id"]
        for attempt in attempts
    ] == task_ids


@pytest.mark.asyncio
@pytest.mark.parametrize("recovery_runtime", ["available"], indirect=True)
async def test_late_old_revision_and_duplicate_jobs_cannot_overwrite_regraded_result(
    recovery_runtime,
):
    created = await reliability.make_submitted_attempt(recovery_runtime)
    attempt_id = created["attempt"]["id"]
    await recovery_runtime.command("recover-grading", "--limit", "100")
    first = await reliability.staff_attempt(recovery_runtime, attempt_id)
    assert first["final_score"] == "2.5"
    async with AsyncClient(base_url=recovery_runtime.base_url) as client:
        headers = await reliability.admin_login(client)
        exam = (await client.get(f"/api/staff/exams/{created['exam']['id']}")).json()
        question = exam["questions"][0]
        correction = await client.post(
            f"/api/staff/exams/{exam['id']}/questions/{question['id']}/correct-standard",
            headers=headers,
            json={
                "version": exam["version"],
                "grading_revision": question["grading_revision"],
                "standard_answer": [question["options"][1]["id"]],
                "reason": "更正单选评分依据",
            },
        )
        assert correction.status_code == 200, correction.text

    redis = ArqRedis.from_url(recovery_runtime.environment["REDIS_URL"])
    redis.default_queue_name = recovery_runtime.queue_name
    try:
        old = Job(f"attempt-grade:{attempt_id}:1", redis, _queue_name=recovery_runtime.queue_name)
        assert await old.info() is not None
        startup = await recovery_runtime.command("worker", "--burst", queue_available=True)
        assert attempt_id in startup["startup_grading_recovery"]["graded_attempt_ids"]
        assert await old.result(timeout=5) is False
        corrected = await reliability.staff_attempt(recovery_runtime, attempt_id)
        assert corrected["grading_revision"] == 2
        assert corrected["final_score"] == "0.0"

        duplicates = [
            await redis.enqueue_job(
                "grade_attempt_job", attempt_id, revision, _job_id="duplicate:" + uuid4().hex
            )
            for revision in [1, 2, 2]
        ]
        await recovery_runtime.command("worker", "--burst", queue_available=True)
        for job in duplicates:
            assert await job.result(timeout=5) is False
        assert await reliability.staff_attempt(recovery_runtime, attempt_id) == corrected
        async with AsyncClient(base_url=recovery_runtime.base_url) as client:
            await reliability.admin_login(client)
            history = await client.get(
                f"/api/staff/answers/{corrected['questions'][0]['answer']['id']}/history"
            )
            assert history.status_code == 200, history.text
            assert [item["new_score"] for item in history.json()["items"]] == ["2.5", "0.0"]
    finally:
        await redis.aclose()


@pytest.mark.asyncio
async def test_cli_preserves_partial_manual_scores_while_admin_reassigns_disabled_teacher(
    recovery_runtime,
):
    created = await reliability.make_exam(recovery_runtime, short_answers=2, teachers=2)
    exam = created["exam"]
    submitted = await reliability.submit_student(
        recovery_runtime, exam, short_values=["人工第一题", "人工第二题"]
    )
    attempt_id = submitted["attempt"]["id"]
    await reliability.end_exam(recovery_runtime, exam["id"])
    await recovery_runtime.command("recover-grading", "--limit", "100")
    detail = await reliability.staff_attempt(recovery_runtime, attempt_id)
    assigned = detail["task"]["assigned_teacher"]
    other = next(teacher for teacher in created["teachers"] if teacher["id"] != assigned["id"])
    async with AsyncClient(base_url=recovery_runtime.base_url) as teacher_client:
        headers = await reliability.login(
            teacher_client, assigned["login_name"], "TemporaryPass!123"
        )
        changed = await teacher_client.put(
            "/api/auth/password",
            headers=headers,
            json={"current_password": "TemporaryPass!123", "new_password": "TeacherChanged!123"},
        )
        assert changed.status_code == 204, changed.text
        headers = await reliability.login(
            teacher_client, assigned["login_name"], "TeacherChanged!123"
        )
        answer = detail["questions"][1]["answer"]
        first = await teacher_client.post(
            f"/api/staff/answers/{answer['id']}/grade",
            headers=headers,
            json={
                "version": answer["version"],
                "grading_revision": answer["grading_revision"],
                "score": "1.2",
                "comment": "保留已评内容",
            },
        )
        assert first.status_code == 200, first.text
        assert first.json()["task"]["status"] == "IN_PROGRESS"

        async with AsyncClient(base_url=recovery_runtime.base_url) as admin_client:
            admin_headers = await reliability.admin_login(admin_client)
            disabled = await admin_client.patch(
                f"/api/admin/users/{assigned['id']}",
                headers=admin_headers,
                json={"status": "DEACTIVATED"},
            )
            assert disabled.status_code == 200, disabled.text
            await recovery_runtime.command("recover-grading", "--limit", "100")
            waiting = await reliability.staff_attempt(recovery_runtime, attempt_id)
            assert waiting["task"]["status"] == "UNASSIGNED"
            assert waiting["questions"][1]["answer"]["score"] == "1.2"
            assert waiting["questions"][1]["answer"]["grader_comment"] == "保留已评内容"
            reassigned = await admin_client.post(
                f"/api/admin/grading-tasks/{waiting['task']['id']}/reassign",
                headers=admin_headers,
                json={
                    "version": waiting["task"]["version"],
                    "teacher_id": other["id"],
                    "reason": "停用任务人工改派",
                },
            )
            assert reassigned.status_code == 200, reassigned.text
        second_answer = waiting["questions"][2]["answer"]
        rejected = await teacher_client.post(
            f"/api/staff/answers/{second_answer['id']}/grade",
            headers=headers,
            json={
                "version": second_answer["version"],
                "grading_revision": second_answer["grading_revision"],
                "score": "2.0",
            },
        )
        assert rejected.status_code in {401, 403}, rejected.text

    async with AsyncClient(base_url=recovery_runtime.base_url) as teacher_client:
        headers = await reliability.login(teacher_client, other["login_name"], "TemporaryPass!123")
        changed = await teacher_client.put(
            "/api/auth/password",
            headers=headers,
            json={"current_password": "TemporaryPass!123", "new_password": "TeacherChanged!123"},
        )
        assert changed.status_code == 204, changed.text
        headers = await reliability.login(teacher_client, other["login_name"], "TeacherChanged!123")
        remaining = await teacher_client.get(f"/api/staff/attempts/{attempt_id}")
        assert remaining.status_code == 200, remaining.text
        answer = remaining.json()["questions"][2]["answer"]
        completed = await teacher_client.post(
            f"/api/staff/answers/{answer['id']}/grade",
            headers=headers,
            json={
                "version": answer["version"],
                "grading_revision": answer["grading_revision"],
                "score": "2.0",
            },
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["task"]["status"] == "COMPLETED"
        assert completed.json()["final_score"] == "5.7"
    await recovery_runtime.command("recover-grading", "--limit", "100")
    assert (await reliability.staff_attempt(recovery_runtime, attempt_id))["final_score"] == "5.7"


@pytest.mark.asyncio
async def test_limited_scan_skips_already_assigned_exams_and_attempts_waiting_manual_grading(
    recovery_runtime,
):
    first_exam = await reliability.make_exam(recovery_runtime, short_answers=1, teachers=1)
    first = await reliability.submit_student(
        recovery_runtime, first_exam["exam"], short_values=["旧卷"]
    )
    await reliability.end_exam(recovery_runtime, first_exam["exam"]["id"])
    await recovery_runtime.command("recover-grading", "--limit", "1")
    older = await reliability.staff_attempt(recovery_runtime, first["attempt"]["id"])
    assert older["grading_status"] == "GRADING"
    assert older["task"]["status"] == "PENDING"

    second_exam = await reliability.make_exam(recovery_runtime, short_answers=1, teachers=1)
    second = await reliability.submit_student(
        recovery_runtime, second_exam["exam"], short_values=["新卷"]
    )
    await reliability.end_exam(recovery_runtime, second_exam["exam"]["id"])
    recovered = await recovery_runtime.command("recover-grading", "--limit", "1")
    assert recovered["graded_attempt_ids"] == [second["attempt"]["id"]]
    assert recovered["assigned_exam_ids"] == [second_exam["exam"]["id"]]
    latest = await reliability.staff_attempt(recovery_runtime, second["attempt"]["id"])
    assert latest["task"]["status"] == "PENDING"
    assert (await reliability.staff_attempt(recovery_runtime, first["attempt"]["id"])) == older
