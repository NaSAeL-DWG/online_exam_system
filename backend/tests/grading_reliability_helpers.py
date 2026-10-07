import asyncio
import json
import os
import socket
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from httpx import AsyncClient
from sqlalchemy.engine import make_url

from test_exams_api import draft_payload
from test_questions_api import question_payload


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
TEST_ADMIN_LOGIN = "grading-recovery-admin"
TEST_ADMIN_PASSWORD = "GradingRecoveryAdmin!123"


@pytest.fixture(scope="session", autouse=True)
def prepare_integration_environment():
    """此文件使用逐例隔离数据库，不运行共享测试库的会话初始化。"""


@dataclass
class RecoveryRuntime:
    environment: dict[str, str] = field(repr=False)
    base_url: str
    queue_name: str
    api_process: asyncio.subprocess.Process | None = None

    async def start_worker(self) -> asyncio.subprocess.Process:
        """常驻 worker 独立进程，只连接本例队列；测试结束关闭本例进程。"""

        environment = self.environment.copy()
        environment["ARQ_REDIS_URL"] = environment["REDIS_URL"]
        environment["ARQ_QUEUE_NAME"] = self.queue_name
        return await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "app.workers",
            "worker",
            cwd=BACKEND_DIRECTORY,
            env=environment,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

    async def command(
        self, *arguments: str, queue_available: bool = False, redis_available: bool = True
    ) -> dict:
        """执行独立 CLI/worker，输出只保留公开 JSON 运行结果。"""

        environment = self.environment.copy()
        environment["ARQ_REDIS_URL"] = (
            environment["REDIS_URL"] if queue_available else "redis://127.0.0.1:1/15"
        )
        if not redis_available:
            environment["REDIS_URL"] = "redis://127.0.0.1:1/15"
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "app.workers",
            *arguments,
            cwd=BACKEND_DIRECTORY,
            env=environment,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=35)
        except TimeoutError:
            process.terminate()
            await process.wait()
            raise
        assert process.returncode == 0, stderr.decode("utf-8", errors="replace")
        return json.loads(stdout.decode("utf-8"))


async def run_setup(environment: dict[str, str], *arguments: str) -> None:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        *arguments,
        cwd=BACKEND_DIRECTORY,
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        await asyncio.wait_for(process.communicate(), timeout=35)
    except TimeoutError:
        process.terminate()
        await process.wait()
        raise
    # 迁移失败只报告错误类型；不把可能含连接信息的驱动诊断写入测试日志。
    assert process.returncode == 0, f"隔离环境准备失败：{arguments[0]}"


@pytest.fixture
async def recovery_runtime(request):
    """真实 PostgreSQL、Redis 和独立 API；数据库与队列均逐例隔离。"""

    source_database = os.environ["TEST_DATABASE_URL"]
    source_redis = os.environ["TEST_REDIS_URL"]
    parsed = make_url(source_database)
    database_name = "exam_grading_recovery_" + uuid4().hex[:12]
    admin_url = parsed.set(drivername="postgresql", database="postgres")
    connection = await asyncpg.connect(admin_url.render_as_string(hide_password=False))
    await connection.execute(f'CREATE DATABASE "{database_name}"')
    environment = os.environ.copy()
    environment.update(
        ENVIRONMENT="test",
        DATABASE_URL=parsed.set(database=database_name).render_as_string(hide_password=False),
        REDIS_URL=source_redis,
        ARQ_REDIS_URL="redis://127.0.0.1:1/15",
        ARQ_QUEUE_NAME="arq:grading-recovery:" + uuid4().hex,
        ARQ_ENQUEUE_TIMEOUT_SECONDS="0.1",
        JWT_SECRET="grading-recovery-secret-at-least-32-bytes-long",
        COOKIE_SECURE="false",
        ADMIN_LOGIN_NAME=TEST_ADMIN_LOGIN,
        ADMIN_PASSWORD=TEST_ADMIN_PASSWORD,
        ADMIN_REAL_NAME="可靠性测试管理员",
        ADMIN_EMAIL="grading-recovery-admin@example.com",
        ADMIN_PHONE_NUMBER="13800000000",
    )
    queue_name = environment["ARQ_QUEUE_NAME"]
    if getattr(request, "param", None) in {"available", "lost"}:
        environment["ARQ_REDIS_URL"] = source_redis
    if getattr(request, "param", None) == "lost":
        # 将待丢失任务暂存独立队列，避免故障注入与 worker 消费之间的竞态。
        environment["ARQ_QUEUE_NAME"] += ":before-loss"
    with socket.socket() as address:
        address.bind(("127.0.0.1", 0))
        port = address.getsockname()[1]
    runtime = RecoveryRuntime(environment, f"http://127.0.0.1:{port}", queue_name)
    try:
        await run_setup(environment, "alembic", "upgrade", "head")
        await run_setup(environment, "app.cli", "prepare-test-admin")
        runtime.api_process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
            cwd=BACKEND_DIRECTORY,
            env=environment,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        async with AsyncClient(base_url=runtime.base_url) as client:
            async with asyncio.timeout(15):
                while True:
                    assert runtime.api_process.returncode is None, "隔离 API 启动失败"
                    try:
                        response = await client.get("/api/auth/csrf")
                    except Exception:
                        await asyncio.sleep(0.1)
                    else:
                        if response.status_code == 200:
                            break
                        await asyncio.sleep(0.1)
        yield runtime
    finally:
        if runtime.api_process is not None and runtime.api_process.returncode is None:
            runtime.api_process.terminate()
            await asyncio.wait_for(runtime.api_process.wait(), timeout=10)
        # 仅清理本例创建的随机数据库；从不截断共享 test/dev 库。
        assert database_name.startswith("exam_grading_recovery_")
        await connection.execute(f'DROP DATABASE "{database_name}" WITH (FORCE)')
        await connection.close()


async def login(client: AsyncClient, name: str, password: str) -> dict[str, str]:
    client.cookies.clear()
    csrf = (await client.get("/api/auth/csrf")).json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}
    response = await client.post(
        "/api/auth/login", headers=headers, json={"login_name": name, "password": password}
    )
    assert response.status_code == 200, response.text
    return headers


async def admin_login(client: AsyncClient) -> dict[str, str]:
    return await login(client, TEST_ADMIN_LOGIN, TEST_ADMIN_PASSWORD)


async def make_exam(runtime: RecoveryRuntime, *, short_answers=0, teachers=0) -> dict:
    """经 HTTP 配置考试及指定教师，单题统一为 2.5 分。"""
    async with AsyncClient(base_url=runtime.base_url) as client:
        headers = await admin_login(client)
        graders = []
        for _ in range(teachers):
            number = "T" + uuid4().hex[:12]
            created = await client.post(
                "/api/admin/teachers",
                headers=headers,
                json={
                    "teacher_no": number,
                    "real_name": "补判教师",
                    "email": f"{number}@example.com",
                    "phone_number": "13800138002",
                    "temporary_password": "TemporaryPass!123",
                },
            )
            assert created.status_code == 201, created.text
            graders.append(created.json()["user"])
        questions = []
        payloads = [question_payload()] + [
            question_payload(type="SHORT_ANSWER", options=[], standard_answer="参考依据")
            for _ in range(short_answers)
        ]
        for payload in payloads:
            question_response = await client.post(
                "/api/staff/questions", headers=headers, json=payload
            )
            assert question_response.status_code == 201, question_response.text
            questions.append(question_response.json())
        paper_response = await client.post(
            "/api/staff/papers",
            headers=headers,
            json={
                "title": "后台补判试卷",
                "questions": [
                    {"question_id": question["id"], "score": "2.5"} for question in questions
                ],
            },
        )
        assert paper_response.status_code == 201, paper_response.text
        exam_response = await client.post(
            "/api/staff/exams",
            headers=headers,
            json={
                "source_paper_id": paper_response.json()["id"],
                "title": "后台补判",
                "audience_type": "PUBLIC",
            },
        )
        assert exam_response.status_code == 201, exam_response.text
        exam = exam_response.json()
        url = f"/api/staff/exams/{exam['id']}"
        now = datetime.now(timezone.utc)
        configured = await client.put(
            url,
            headers=headers,
            json=draft_payload(
                exam,
                start_at=(now - timedelta(minutes=1)).isoformat(),
                end_at=(now + timedelta(minutes=5)).isoformat(),
                duration_seconds=5,
                shuffle_questions=False,
                shuffle_options=False,
                grader_ids=[teacher["id"] for teacher in graders],
            ),
        )
        assert configured.status_code == 200, configured.text
        published = await client.post(
            url + "/publish", headers=headers, json={"version": configured.json()["version"]}
        )
        assert published.status_code == 200, published.text
        return {"exam": published.json(), "teachers": graders}


async def submit_student(runtime: RecoveryRuntime, exam: dict, *, short_values=None) -> dict:
    """以新学生提交满分客观题和指定简答内容，所有写入均走 HTTP。"""
    async with AsyncClient(base_url=runtime.base_url) as client:
        headers = await admin_login(client)
        number = "S" + uuid4().hex[:12]
        registered = await client.post(
            "/api/auth/register",
            headers=headers,
            json={
                "student_no": number,
                "real_name": "补判学生",
                "email": f"{number}@example.com",
                "phone_number": "13800138001",
                "password": "ValidPassword!123",
            },
        )
        assert registered.status_code == 201, registered.text
        approved = await client.post(
            f"/api/staff/reviews/{registered.json()['application']['id']}/decision",
            headers=headers,
            json={"decision": "APPROVED"},
        )
        assert approved.status_code == 200, approved.text
        headers = await login(client, number, "ValidPassword!123")
        started = await client.post(
            f"/api/student/exams/{exam['id']}/attempts", headers=headers, json={}
        )
        assert started.status_code == 200, started.text
        attempt = started.json()
        activated = await client.post(
            f"/api/student/attempts/{attempt['id']}/activate", headers=headers, json={}
        )
        assert activated.status_code == 200, activated.text
        activation = activated.json()
        values = [exam["questions"][0]["standard_answer"]] + (short_values or [])
        for question, value in zip(activation["questions"], values, strict=False):
            answer = question["answer"]
            saved = await client.put(
                f"/api/student/attempts/{attempt['id']}/answers/{answer['id']}",
                headers=headers,
                json={
                    "page_token": activation["page_token"],
                    "token_generation": activation["token_generation"],
                    "version": answer["version"],
                    "answer_data": value,
                },
            )
            assert saved.status_code == 200, saved.text
        submitted = await client.post(
            f"/api/student/attempts/{attempt['id']}/submit",
            headers=headers,
            json={
                "page_token": activation["page_token"],
                "token_generation": activation["token_generation"],
                "confirm_unanswered": True,
            },
        )
        assert submitted.status_code == 200, submitted.text
        return {
            "attempt": submitted.json(),
            "exam": exam,
            "student": registered.json()["user"],
        }


async def make_submitted_attempt(runtime: RecoveryRuntime) -> dict:
    created = await make_exam(runtime)
    return await submit_student(runtime, created["exam"])


async def end_exam(runtime: RecoveryRuntime, exam_id: str) -> None:
    """仅控制已确认的时间边界；业务结果始终通过 HTTP/CLI 观察。"""
    parsed = make_url(runtime.environment["DATABASE_URL"])
    connection = await asyncpg.connect(
        parsed.set(drivername="postgresql").render_as_string(hide_password=False)
    )
    try:
        await connection.execute(
            "UPDATE exam SET end_at = $1 WHERE id = $2",
            datetime.now(timezone.utc) - timedelta(seconds=1),
            exam_id,
        )
    finally:
        await connection.close()


async def staff_attempt(runtime: RecoveryRuntime, attempt_id: str) -> dict:
    async with AsyncClient(base_url=runtime.base_url) as client:
        await admin_login(client)
        response = await client.get(f"/api/staff/attempts/{attempt_id}")
        assert response.status_code == 200, response.text
        return response.json()
