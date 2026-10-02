import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from arq.connections import ArqRedis
from arq.jobs import Job
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from content_helpers import create_student
from test_classes_api import admin_login, user_login
from test_exams_api import create_exam, draft_payload
from test_papers_api import create_paper


async def start_unqueued_attempt(client, *, duration_seconds=3):
    """通过公开接口建立作答；仅 ARQ 地址故障，认证 Redis 仍真实可用。"""

    student, number = await create_student(client)
    headers = await admin_login(client)
    paper, _ = await create_paper(client, headers)
    exam = await create_exam(client, headers, paper, audience_type="PUBLIC")
    url = f"/api/staff/exams/{exam['id']}"
    now = datetime.now(timezone.utc)
    configured = await client.put(
        url,
        headers=headers,
        json=draft_payload(
            exam,
            start_at=(now - timedelta(minutes=1)).isoformat(),
            end_at=(now + timedelta(minutes=5)).isoformat(),
            duration_seconds=duration_seconds,
            shuffle_questions=False,
            shuffle_options=False,
        ),
    )
    assert configured.status_code == 200, configured.text
    published = await client.post(
        url + "/publish", headers=headers, json={"version": configured.json()["version"]}
    )
    assert published.status_code == 200, published.text
    client.cookies.clear()
    headers = await user_login(client, number, "ValidPassword!123")
    started = await client.post(
        f"/api/student/exams/{exam['id']}/attempts", headers=headers, json={}
    )
    assert started.status_code == 200, started.text
    return started.json(), headers, student, published.json()


async def wait_until_due(attempt):
    deadline = datetime.fromisoformat(attempt["deadline_at"])
    delay = (deadline - datetime.now(timezone.utc)).total_seconds()
    await asyncio.sleep(max(delay, 0) + 0.05)


async def run_recovery_command(database_url, redis_url, queue_name):
    """运维恢复入口不依赖 API 进程，也不要求队列 Redis 可用。"""

    environment = os.environ.copy()
    environment.update(
        DATABASE_URL=database_url,
        REDIS_URL=redis_url,
        ARQ_REDIS_URL="redis://127.0.0.1:1/15",
        ARQ_QUEUE_NAME=queue_name,
    )
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.workers",
        "recover-attempts",
        "--limit",
        "100",
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=20)
    assert process.returncode == 0, stderr.decode("utf-8")
    return json.loads(stdout)


async def run_worker_burst(database_url, redis_url, queue_name):
    """通过独立 ARQ 进程启动恢复，队列中没有截止任务也能处理。"""

    environment = os.environ.copy()
    environment.update(
        DATABASE_URL=database_url,
        REDIS_URL=redis_url,
        ARQ_REDIS_URL=redis_url,
        ARQ_QUEUE_NAME=queue_name,
    )
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.workers",
        "worker",
        "--burst",
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=20)
    assert process.returncode == 0, stderr.decode("utf-8")
    return json.loads(stdout)


@pytest.fixture
async def unavailable_queue_client(database_url, redis_url):
    from app.main import create_app

    settings = get_settings().model_copy(
        update={
            "arq_redis_url": "redis://127.0.0.1:1/15",
            "arq_queue_name": "arq:recovery:" + uuid4().hex,
        }
    )
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://testserver"
        ) as client:
            yield client, settings.arq_queue_name


@pytest.fixture
async def available_queue_client(database_url, redis_url):
    from app.main import create_app

    settings = get_settings().model_copy(
        update={
            "arq_redis_url": redis_url,
            "arq_queue_name": "arq:recovery:" + uuid4().hex,
        }
    )
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://testserver"
        ) as client:
            yield client, settings.arq_queue_name


@pytest.mark.asyncio
async def test_committed_attempt_recovers_when_queue_is_unavailable(
    unavailable_queue_client, database_url, redis_url
):
    client, queue_name = unavailable_queue_client
    attempt, headers, _, exam = await start_unqueued_attempt(client)
    activated = await client.post(
        f"/api/student/attempts/{attempt['id']}/activate", headers=headers, json={}
    )
    assert activated.status_code == 200, activated.text
    activation = activated.json()
    question = activation["questions"][0]
    saved = await client.put(
        f"/api/student/attempts/{attempt['id']}/answers/{question['answer']['id']}",
        headers=headers,
        json={
            "page_token": activation["page_token"],
            "token_generation": activation["token_generation"],
            "version": question["answer"]["version"],
            "answer_data": [question["options"][0]["id"]],
        },
    )
    assert saved.status_code == 200, saved.text
    persisted = await client.get(f"/api/student/attempts/{attempt['id']}")
    assert persisted.status_code == 200, persisted.text
    assert persisted.json()["questions"][0]["answer"]["answer_data"] == saved.json()["answer_data"]
    await wait_until_due(attempt)

    worker_result = await run_worker_burst(database_url, redis_url, queue_name)
    recovered = worker_result["startup_recovery"]
    assert attempt["id"] in recovered["submitted_attempt_ids"]
    detail = await client.get(f"/api/student/attempts/{attempt['id']}")
    assert detail.status_code == 200, detail.text
    submitted = detail.json()
    assert submitted["status"] == "SUBMITTED"
    assert submitted["submission_type"] == "TIMEOUT"
    assert submitted["effective_submitted_at"] == attempt["deadline_at"]
    assert submitted["grading_status"] == "PENDING"
    assert submitted["questions"] == []

    repeated = await run_recovery_command(database_url, redis_url, queue_name)
    assert repeated["submitted"] == 0
    unchanged = (await client.get(f"/api/student/attempts/{attempt['id']}")).json()
    assert unchanged["submitted_at"] == submitted["submitted_at"]
    summary = (await client.get(f"/api/student/exams/{exam['id']}")).json()
    assert summary["used_attempts"] == 1


@pytest.mark.asyncio
async def test_scheduled_timeout_and_duplicate_jobs_preserve_one_submission(
    available_queue_client, database_url, redis_url
):
    client, queue_name = available_queue_client
    attempt, _, _, exam = await start_unqueued_attempt(client, duration_seconds=5)

    # 进程在截止前启动，禁用新 cron 的一次性模式只消费真实截止任务。
    scheduled = await run_worker_burst(database_url, redis_url, queue_name)
    assert attempt["id"] not in scheduled["startup_recovery"]["submitted_attempt_ids"]
    assert scheduled["jobs_complete"] == 1
    redis = ArqRedis.from_url(redis_url)
    redis.default_queue_name = queue_name
    try:
        deadline_job = Job(f"attempt-timeout:{attempt['id']}", redis, _queue_name=queue_name)
        assert await deadline_job.result(timeout=5) is True
        submitted = (await client.get(f"/api/student/attempts/{attempt['id']}")).json()
        assert submitted["status"] == "SUBMITTED"
        assert submitted["submission_type"] == "TIMEOUT"
        assert submitted["effective_submitted_at"] == attempt["deadline_at"]
        assert submitted["questions"] == []

        duplicates = []
        for _ in range(2):
            job = await redis.enqueue_job(
                "timeout_attempt_job", attempt["id"], _job_id="duplicate:" + uuid4().hex
            )
            duplicates.append(job)
        repeated = await run_worker_burst(database_url, redis_url, queue_name)
        assert repeated["jobs_complete"] == 2
        for job in duplicates:
            assert await job.result(timeout=5) is False
        unchanged = (await client.get(f"/api/student/attempts/{attempt['id']}")).json()
        assert unchanged["submitted_at"] == submitted["submitted_at"]
        summary = (await client.get(f"/api/student/exams/{exam['id']}")).json()
        assert summary["used_attempts"] == 1
    finally:
        await redis.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("cancellation", ["participant", "exam"])
async def test_late_deadline_job_never_revives_void_attempt(
    available_queue_client, database_url, redis_url, cancellation
):
    client, queue_name = available_queue_client
    attempt, _, student, exam = await start_unqueued_attempt(client, duration_seconds=5)
    headers = await admin_login(client)
    url = f"/api/staff/exams/{exam['id']}"
    participants = (await client.get(url + "/participants")).json()["items"]
    participant = next(item for item in participants if item["user"]["id"] == student["id"])
    if cancellation == "participant":
        participant_url = f"{url}/participants/{participant['id']}"
        cancelled = await client.post(
            participant_url + "/cancel",
            headers=headers,
            json={"version": participant["version"], "reason": "迟到任务不能复活"},
        )
        assert cancelled.status_code == 200, cancelled.text
        restored = await client.post(
            participant_url + "/restore",
            headers=headers,
            json={"version": cancelled.json()["version"], "reason": "仅恢复后续资格"},
        )
        assert restored.status_code == 200, restored.text
    else:
        cancelled = await client.post(
            url + "/cancel",
            headers=headers,
            json={"version": exam["version"], "reason": "整场取消保留审计"},
        )
        assert cancelled.status_code == 200, cancelled.text
    await wait_until_due(attempt)

    worker_result = await run_worker_burst(database_url, redis_url, queue_name)
    assert attempt["id"] not in worker_result["startup_recovery"]["submitted_attempt_ids"]
    redis = ArqRedis.from_url(redis_url)
    try:
        deadline_job = Job(f"attempt-timeout:{attempt['id']}", redis, _queue_name=queue_name)
        assert await deadline_job.result(timeout=5) is False
    finally:
        await redis.aclose()
    participants = (await client.get(url + "/participants")).json()["items"]
    unchanged = next(item for item in participants if item["id"] == participant["id"])
    assert unchanged["used_attempts"] == 1
    assert unchanged["voided_attempts"] == 1


@pytest.mark.asyncio
async def test_deactivated_student_times_out_and_recovers_receipt_after_reactivation(
    available_queue_client, database_url, redis_url
):
    client, queue_name = available_queue_client
    attempt, _, student, exam = await start_unqueued_attempt(client, duration_seconds=5)
    headers = await admin_login(client)
    user_url = f"/api/admin/users/{student['id']}"
    deactivated = await client.patch(user_url, headers=headers, json={"status": "DEACTIVATED"})
    assert deactivated.status_code == 200, deactivated.text

    worker_result = await run_worker_burst(database_url, redis_url, queue_name)
    assert worker_result["jobs_complete"] == 1
    redis = ArqRedis.from_url(redis_url)
    try:
        deadline_job = Job(f"attempt-timeout:{attempt['id']}", redis, _queue_name=queue_name)
        assert await deadline_job.result(timeout=5) is True
    finally:
        await redis.aclose()
    reactivated = await client.patch(user_url, headers=headers, json={"status": "ACTIVATED"})
    assert reactivated.status_code == 200, reactivated.text
    client.cookies.clear()
    await user_login(client, student["login_name"], "ValidPassword!123")
    receipt = await client.get(f"/api/student/attempts/{attempt['id']}")
    assert receipt.status_code == 200, receipt.text
    assert receipt.json()["status"] == "SUBMITTED"
    assert receipt.json()["submission_type"] == "TIMEOUT"
    assert receipt.json()["grading_status"] == "PENDING"
    assert receipt.json()["deadline_at"] == attempt["deadline_at"]
    assert receipt.json()["effective_submitted_at"] == attempt["deadline_at"]
    summary = (await client.get(f"/api/student/exams/{exam['id']}")).json()
    assert summary["used_attempts"] == 1
    assert summary["remaining_attempts"] == 1


@pytest.mark.asyncio
async def test_running_worker_periodically_recovers_missing_deadline_job(
    unavailable_queue_client, database_url, redis_url
):
    client, queue_name = unavailable_queue_client
    attempt, _, _, _ = await start_unqueued_attempt(client, duration_seconds=5)
    environment = os.environ.copy()
    environment.update(
        DATABASE_URL=database_url,
        REDIS_URL=redis_url,
        ARQ_REDIS_URL=redis_url,
        ARQ_QUEUE_NAME=queue_name,
    )
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.workers",
        "worker",
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    redis = ArqRedis.from_url(redis_url)
    try:
        # 只认可真实 cron 的公开结果，随后 HTTP 自动收尾不能替代该证据。
        async with asyncio.timeout(40):
            while True:
                assert process.returncode is None, "常驻 worker 在周期恢复前退出"
                results = await redis.all_job_results()
                recovered = any(
                    result.function == "cron:scan_due_attempts_job"
                    and result.success
                    and attempt["id"] in result.result["submitted_attempt_ids"]
                    for result in results
                )
                if recovered:
                    break
                await asyncio.sleep(0.25)
        receipt = await client.get(f"/api/student/attempts/{attempt['id']}")
        assert receipt.status_code == 200, receipt.text
        assert receipt.json()["status"] == "SUBMITTED"
        assert receipt.json()["submission_type"] == "TIMEOUT"
        assert receipt.json()["effective_submitted_at"] == attempt["deadline_at"]
    finally:
        await redis.aclose()
        if process.returncode is None:
            process.terminate()
        await asyncio.wait_for(process.wait(), timeout=5)
