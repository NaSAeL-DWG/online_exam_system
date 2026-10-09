"""真实 HTTP 并发验证入口；只创建和保留隔离库，不清空已有业务数据。"""

import argparse
import asyncio
import json
import math
import os
import platform
import secrets
import shlex
import socket
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import asyncpg
from httpx import AsyncClient, Limits
from redis.asyncio import Redis
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

from load_resources import ResourceSampler


BACKEND = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = BACKEND.parent / ".local" / "iteration6" / "load"


class UnsafeTarget(ValueError):
    """隔离目标不满足本机压测约束。"""


class HttpFailure(RuntimeError):
    """只保留状态及稳定错误码，避免响应里的令牌进入日志。"""


class Measurements:
    def __init__(self):
        self.requests = []
        self.active = Counter()
        self.max_active = Counter()

    async def request(self, client, method, path, *, phase, operation, expected=200, **kwargs):
        started = time.perf_counter()
        self.active[phase] += 1
        self.max_active[phase] = max(self.max_active[phase], self.active[phase])
        try:
            response = await client.request(method, path, **kwargs)
        except Exception as exc:
            self.requests.append(
                {
                    "phase": phase,
                    "operation": operation,
                    "status": 0,
                    "elapsed_ms": (time.perf_counter() - started) * 1000,
                    "error": type(exc).__name__,
                }
            )
            raise HttpFailure(type(exc).__name__) from None
        finally:
            self.active[phase] -= 1
        self.requests.append(
            {
                "phase": phase,
                "operation": operation,
                "status": response.status_code,
                "elapsed_ms": (time.perf_counter() - started) * 1000,
            }
        )
        if expected is not None and response.status_code != expected:
            try:
                code = response.json().get("detail", {}).get("code", "HTTP_ERROR")
            except Exception:
                code = "HTTP_ERROR"
            raise HttpFailure(f"{operation}:{response.status_code}:{code}")
        return response

    def summary(self, phase):
        rows = [row for row in self.requests if row["phase"] == phase]

        def summarize(selected):
            values = sorted(row["elapsed_ms"] for row in selected)

            def percentile(fraction):
                # 最近秩百分位：定义固定，便于与其他工具的插值口径区分。
                if not values:
                    return None
                return round(values[math.ceil(len(values) * fraction) - 1], 3)

            return {
                "requests": len(selected),
                "successes": sum(200 <= row["status"] < 300 for row in selected),
                "server_errors": sum(row["status"] >= 500 for row in selected),
                "transport_errors": sum(row["status"] == 0 for row in selected),
                "status_counts": dict(Counter(str(row["status"]) for row in selected)),
                "p50_ms": percentile(0.50),
                "p95_ms": percentile(0.95),
                "p99_ms": percentile(0.99),
                "max_ms": round(max(values), 3) if values else None,
            }

        result = summarize(rows)
        result["max_in_flight_requests"] = self.max_active[phase]
        result["operations"] = {
            operation: summarize([row for row in rows if row["operation"] == operation])
            for operation in sorted({row["operation"] for row in rows})
        }
        return result


def isolated_environment(args):
    """派生专用库和 Redis DB，绝不打印或复用开发库作为写入目标。"""

    source = dotenv_values(args.source_env)
    database = make_url(source["TEST_DATABASE_URL"])
    redis = urlsplit(source["TEST_REDIS_URL"])
    if database.host not in {"127.0.0.1", "localhost", "::1"}:
        raise UnsafeTarget()
    if redis.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise UnsafeTarget()
    if args.database_name != "exam_test_iteration6_load" or args.port != 18001:
        raise UnsafeTarget()
    if database.drivername != "postgresql+asyncpg" or redis.scheme != "redis":
        raise UnsafeTarget()
    output = args.output_dir.resolve()
    if not output.is_relative_to(DEFAULT_OUTPUT.resolve()):
        raise UnsafeTarget()
    return {
        "DATABASE_URL": database.set(database=args.database_name).render_as_string(
            hide_password=False
        ),
        "REDIS_URL": redis._replace(path="/13").geturl(),
    }


async def run_setup(environment, log_path, *arguments):
    with log_path.open("ab") as log:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            *arguments,
            cwd=BACKEND,
            env=environment,
            stdout=log,
            stderr=log,
        )
        try:
            await asyncio.wait_for(process.wait(), timeout=45)
        except TimeoutError:
            await stop_process(process)
            raise
    if process.returncode != 0:
        raise RuntimeError("ISOLATED_SETUP_FAILED")


async def login(client, metrics, name, password, *, phase="sessions"):
    csrf = await metrics.request(client, "GET", "/api/auth/csrf", phase=phase, operation="csrf")
    headers = {"X-CSRF-Token": csrf.json()["csrf_token"]}
    await metrics.request(
        client,
        "POST",
        "/api/auth/login",
        headers=headers,
        json={"login_name": name, "password": password},
        phase=phase,
        operation="login",
    )
    return headers


async def prepare_exam(client, metrics, headers, count, run_id, duration):
    """经公开 HTTP 创建客观题混合试卷；正确与错误答案来自已知题目语料。"""

    question_ids = []
    for index in range(count):
        kind = ("SINGLE_CHOICE", "MULTIPLE_CHOICE", "TRUE_FALSE")[index % 3]
        options = [{"id": str(uuid4()), "content": text} for text in ("甲", "乙", "丙")]
        answer = (
            [options[0]["id"]] if kind == "SINGLE_CHOICE" else [options[0]["id"], options[1]["id"]]
        )
        if kind == "TRUE_FALSE":
            options, answer = [], False
        question = await metrics.request(
            client,
            "POST",
            "/api/staff/questions",
            headers=headers,
            expected=201,
            phase="provision",
            operation="create_question",
            json={
                "type": kind,
                "content": f"并发验证 {run_id} 第 {index + 1} 题",
                "options": options,
                "standard_answer": answer,
                "explanation": "独立压测题目依据",
                "subject": "并发验证",
                "knowledge_tags": ["隔离数据"],
                "difficulty": "MEDIUM",
            },
        )
        question_ids.append({"question_id": question.json()["id"], "score": "2.5"})
    paper = await metrics.request(
        client,
        "POST",
        "/api/staff/papers",
        headers=headers,
        expected=201,
        phase="provision",
        operation="create_paper",
        json={"title": f"并发验证 {run_id}", "questions": question_ids},
    )
    created = await metrics.request(
        client,
        "POST",
        "/api/staff/exams",
        headers=headers,
        expected=201,
        phase="provision",
        operation="create_exam",
        json={
            "source_paper_id": paper.json()["id"],
            "title": f"并发验证 {run_id}",
            "audience_type": "PUBLIC",
        },
    )
    exam = created.json()
    now = datetime.now(timezone.utc)
    configured = await metrics.request(
        client,
        "PUT",
        f"/api/staff/exams/{exam['id']}",
        headers=headers,
        phase="provision",
        operation="configure_exam",
        json={
            "version": exam["version"],
            "title": exam["title"],
            "description": "隔离HTTP负载",
            "audience_type": "PUBLIC",
            "start_at": (now - timedelta(minutes=1)).isoformat(),
            "end_at": (now + timedelta(hours=1)).isoformat(),
            "duration_seconds": duration,
            "max_attempts": 1,
            "allow_review": True,
            "shuffle_questions": False,
            "shuffle_options": False,
            "multiple_choice_mode": "EXACT",
            "pass_percentage": "60.00",
            "grader_ids": [],
            "questions": exam["questions"],
        },
    )
    published = await metrics.request(
        client,
        "POST",
        f"/api/staff/exams/{exam['id']}/publish",
        headers=headers,
        phase="provision",
        operation="publish_exam",
        json={"version": configured.json()["version"]},
    )
    return published.json()


async def provision_students(client, metrics, headers, count, run_id, password):
    students = []
    for index in range(count):
        number = f"L{run_id}{index:03d}"
        registered = await metrics.request(
            client,
            "POST",
            "/api/auth/register",
            headers=headers,
            expected=201,
            phase="provision",
            operation="register",
            json={
                "student_no": number,
                "real_name": f"压测学生{index + 1}",
                "email": f"{number}@example.com",
                "phone_number": "13800138001",
                "password": password,
            },
        )
        application_id = registered.json()["application"]["id"]
        await metrics.request(
            client,
            "POST",
            f"/api/staff/reviews/{application_id}/decision",
            headers=headers,
            phase="provision",
            operation="approve",
            json={"decision": "APPROVED"},
        )
        students.append(number)
    return students


async def student_workload(client, headers, metrics, exam, index, args, barrier):
    """每名学生用独立 Cookie 会话和页面令牌，按顺序保存并读取服务器答案。"""

    await barrier.wait()
    if args.mode == "steady":
        # 固定种子的确定性错峰便于重跑；不制造同一毫秒的全部页面操作。
        await asyncio.sleep((index / args.students) * args.ramp_seconds)
    phase = "workload"

    async def request(method, path, operation, **kwargs):
        return await metrics.request(
            client, method, path, phase=phase, operation=operation, **kwargs
        )

    await request("GET", "/api/student/exams", "exam_list", params={"q": exam["title"]})
    await request("GET", f"/api/student/exams/{exam['id']}", "exam_detail")
    started = await request(
        "POST", f"/api/student/exams/{exam['id']}/attempts", "start", headers=headers, json={}
    )
    attempt = started.json()
    url = f"/api/student/attempts/{attempt['id']}"
    activated = await request(
        "POST",
        url + "/activate",
        "activate",
        headers=headers,
        json={"expected_generation": attempt["token_generation"]},
    )
    activation = activated.json()
    permission = {key: activation[key] for key in ("page_token", "token_generation")}
    expected_answers = {}
    for question in activation["questions"]:
        options = question["options"]
        # 奇数编号故意全部答错；两种已知语料能检测错绑答案或错误判分。
        if question["type"] == "TRUE_FALSE":
            value = bool(index % 2)
        elif index % 2:
            value = [options[2]["id"]]
        elif question["type"] == "SINGLE_CHOICE":
            value = [options[0]["id"]]
        else:
            value = [options[0]["id"], options[1]["id"]]
        if args.mode == "steady":
            await asyncio.sleep(args.think_seconds * (0.75 + (index % 11) / 20))
        answer = question["answer"]
        saved = await request(
            "PUT",
            url + f"/answers/{answer['id']}",
            "save",
            headers=headers,
            json=permission | {"version": answer["version"], "answer_data": value},
        )
        if saved.json()["answer_data"] != value:
            raise RuntimeError("SAVE_RESPONSE_MISMATCH")
        expected_answers[question["id"]] = value
        reread = await request("GET", url, "heartbeat_read")
        server_values = {q["id"]: q["answer"]["answer_data"] for q in reread.json()["questions"]}
        if any(server_values[key] != data for key, data in expected_answers.items()):
            raise RuntimeError("READ_AFTER_SAVE_MISMATCH")
    if args.submission == "manual":
        submitted = await request(
            "POST",
            url + "/submit",
            "submit",
            headers=headers,
            json=permission | {"confirm_unanswered": False},
        )
        if submitted.json()["status"] != "SUBMITTED":
            raise RuntimeError("SUBMISSION_STATE_MISMATCH")
        if submitted.json()["submission_type"] != "MANUAL":
            raise RuntimeError("SUBMISSION_TYPE_MISMATCH")
        receipt = await request("GET", url, "receipt")
        if receipt.json()["status"] != "SUBMITTED" or receipt.json()["questions"]:
            raise RuntimeError("RECEIPT_STATE_MISMATCH")
    return {
        "id": attempt["id"],
        "deadline_at": attempt["deadline_at"],
        "student_index": index,
        "answers": expected_answers,
        "score": str(Decimal("0.0") if index % 2 else Decimal("2.5") * args.questions),
    }


async def audit_attempts(admin, metrics, results, submission):
    consistent, graded = 0, 0
    for attempt in results:
        response = await metrics.request(
            admin,
            "GET",
            f"/api/staff/attempts/{attempt['id']}",
            phase="audit",
            operation="staff_attempt",
            expected=None if submission == "timeout" else 200,
        )
        if submission == "timeout" and response.status_code == 404:
            continue
        if response.status_code != 200:
            raise HttpFailure(f"staff_attempt:{response.status_code}")
        detail = response.json()
        values = {q["id"]: q["answer"]["answer_data"] for q in detail["questions"]}
        if detail["status"] != "SUBMITTED" or values != attempt["answers"]:
            raise RuntimeError("FINAL_ANSWER_OR_SUBMISSION_MISMATCH")
        if detail["grading_status"] == "GRADED":
            if Decimal(detail["final_score"]) != Decimal(attempt["score"]):
                raise RuntimeError("FINAL_SCORE_MISMATCH")
            graded += 1
        consistent += 1
    return {"consistent_attempts": consistent, "graded_attempts": graded}


async def start_process(environment, log_path, *arguments):
    with log_path.open("ab") as log:
        return await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            *arguments,
            cwd=BACKEND,
            env=environment,
            stdout=log,
            stderr=log,
        )


async def stop_process(process):
    if process is not None and process.returncode is None:
        process.terminate()
        await asyncio.wait_for(process.wait(), timeout=10)


async def database_information(environment):
    """这里只采样容量与连接信息；业务一致性始终通过 HTTP 查询验证。"""

    database = make_url(environment["DATABASE_URL"])
    connection = await asyncpg.connect(
        database.set(drivername="postgresql").render_as_string(hide_password=False)
    )
    try:
        counts = {}
        for table in (
            "user_account",
            "question",
            "paper",
            "exam",
            "exam_question",
            "exam_participant",
            "exam_attempt",
            "stu_answer",
            "grading_history",
        ):
            exists = await connection.fetchval("SELECT to_regclass($1)", '"' + table + '"')
            if exists:
                counts[table] = await connection.fetchval(f'SELECT count(*) FROM "{table}"')
        return {
            "postgres_version": await connection.fetchval("SHOW server_version"),
            "max_connections": int(await connection.fetchval("SHOW max_connections")),
            "database_bytes": await connection.fetchval(
                "SELECT pg_database_size(current_database())"
            ),
            "table_counts": counts,
        }
    finally:
        await connection.close()


async def software_information(environment):
    """报告实际安装版本，只读取 Redis 版本字段而不保存整份 INFO。"""

    redis = Redis.from_url(environment["REDIS_URL"], decode_responses=True)
    try:
        server = await redis.info("server")
    finally:
        await redis.aclose()
    return {
        "redis_server": server["redis_version"],
        **{
            name: version(name)
            for name in (
                "fastapi",
                "uvicorn",
                "sqlmodel",
                "sqlalchemy",
                "asyncpg",
                "httpx",
                "arq",
                "redis",
            )
        },
    }


async def run(args, environment):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + uuid4().hex[:6]
    output = args.output_dir / run_id
    output.mkdir(parents=True)
    environment = (
        os.environ
        | environment
        | {
            "ENVIRONMENT": "test",
            "COOKIE_SECURE": "false",
            "JWT_SECRET": secrets.token_urlsafe(40),
            "ARQ_QUEUE_NAME": f"arq:iteration6-load:{run_id}",
            "ADMIN_LOGIN_NAME": "iteration6-load-admin",
            "ADMIN_PASSWORD": secrets.token_urlsafe(20),
            "ADMIN_REAL_NAME": "隔离压测管理员",
            "ADMIN_EMAIL": "load-admin@example.com",
            "ADMIN_PHONE_NUMBER": "13800138000",
            "ASSET_STORAGE_DIR": str(output / "uploads"),
        }
    )
    environment["ARQ_REDIS_URL"] = environment["REDIS_URL"]
    private_keys = [
        "ENVIRONMENT",
        "DATABASE_URL",
        "REDIS_URL",
        "ARQ_REDIS_URL",
        "ARQ_QUEUE_NAME",
        "JWT_SECRET",
        "COOKIE_SECURE",
        "ADMIN_LOGIN_NAME",
        "ADMIN_PASSWORD",
        "ADMIN_REAL_NAME",
        "ADMIN_EMAIL",
        "ADMIN_PHONE_NUMBER",
        "ASSET_STORAGE_DIR",
    ]
    (output / "runtime.env").write_text(
        "\n".join(f"{key}={shlex.quote(environment[key])}" for key in private_keys) + "\n",
        encoding="utf-8",
    )
    # 验证端口未被占用，绝不停止或复用已有的未知 API。
    with socket.socket() as address:
        address.bind(("127.0.0.1", args.port))
    database = make_url(environment["DATABASE_URL"])
    connection = await asyncpg.connect(
        database.set(drivername="postgresql", database="postgres").render_as_string(
            hide_password=False
        )
    )
    try:
        exists = await connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname=$1", args.database_name
        )
        if not exists:
            await connection.execute('CREATE DATABASE "exam_test_iteration6_load"')
    finally:
        await connection.close()
    await run_setup(environment, output / "setup.log", "alembic", "upgrade", "head")
    await run_setup(environment, output / "setup.log", "app.cli", "prepare-test-admin")
    metrics = Measurements()
    api = worker = None
    sampler = ResourceSampler()
    sampler_task = None
    clients = []
    summary = {
        "run_id": run_id,
        "evidence_directory": str(output),
        "students_requested": args.students,
        "questions_per_attempt": args.questions,
        "mode": args.mode,
        "think_seconds": args.think_seconds if args.mode == "steady" else 0,
        "ramp_seconds": args.ramp_seconds if args.mode == "steady" else 0,
        "worker_policy": args.worker_policy,
        "submission": args.submission,
        "environment": {
            "os": platform.platform(),
            "python": platform.python_version(),
            "logical_cpus": os.cpu_count(),
            "api_processes": 1,
            "worker_processes": 1,
            "sqlalchemy_pool_size": 5,
            "sqlalchemy_max_overflow": 10,
            "arq_max_jobs": 10,
            "redis_db": 13,
            "api_port": args.port,
        },
        "services_stopped": False,
    }
    started_at = time.perf_counter()
    try:
        api = await start_process(
            environment,
            output / "api.log",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
            "--no-access-log",
        )
        sampler.processes["api"] = api
        sampler_task = asyncio.create_task(sampler.run())
        base_url = f"http://127.0.0.1:{args.port}"
        async with AsyncClient(base_url=base_url, timeout=30) as admin:
            async with asyncio.timeout(20):
                while True:
                    if api.returncode is not None:
                        raise RuntimeError("ISOLATED_API_EXITED")
                    try:
                        if (await admin.get("/api/auth/csrf")).status_code == 200:
                            break
                    except Exception:
                        pass
                    await asyncio.sleep(0.1)
            headers = await login(
                admin, metrics, environment["ADMIN_LOGIN_NAME"], environment["ADMIN_PASSWORD"]
            )
            summary["environment"]["software"] = await software_information(environment)
            exam = await prepare_exam(
                admin, metrics, headers, args.questions, run_id, args.deadline_seconds
            )
            password = secrets.token_urlsafe(20)
            students = await provision_students(
                admin, metrics, headers, args.students, run_id, password
            )
            summary["environment"]["database_before_workload"] = await database_information(
                environment
            )
            # 会话创建单列指标；默认仅5个并发密码验证，保留全部现有认证限流。
            semaphore = asyncio.Semaphore(5)

            async def prepare_student(number):
                # HTTP 客户端的 TLS/代理上下文初始化是同步操作，移出采样事件循环。
                client = await asyncio.to_thread(
                    AsyncClient,
                    base_url=base_url,
                    timeout=30,
                    limits=Limits(max_connections=2, max_keepalive_connections=2),
                )
                clients.append(client)
                async with semaphore:
                    student_headers = await login(client, metrics, number, password)
                return client, student_headers

            sessions_started = time.perf_counter()
            sampler.phase = "sessions"
            sessions = await asyncio.gather(*(prepare_student(number) for number in students))
            summary["session_preparation_seconds"] = round(
                time.perf_counter() - sessions_started, 3
            )
            # 同IP、同账号12次失败登录：保留10次/60秒限流，探针不计入考试请求成功率。
            probe_client = AsyncClient(base_url=base_url, timeout=30)
            clients.append(probe_client)
            csrf = await metrics.request(
                probe_client, "GET", "/api/auth/csrf", phase="login_limit_probe", operation="csrf"
            )
            probe_name = "missing-" + run_id
            probe_responses = await asyncio.gather(
                *[
                    metrics.request(
                        probe_client,
                        "POST",
                        "/api/auth/login",
                        expected=None,
                        phase="login_limit_probe",
                        operation="invalid_login",
                        headers={"X-CSRF-Token": csrf.json()["csrf_token"]},
                        json={"login_name": probe_name, "password": "InvalidLoadPassword!123"},
                    )
                    for _ in range(12)
                ]
            )
            summary["login_limit_probe"] = {
                "status_counts": dict(
                    Counter(str(response.status_code) for response in probe_responses)
                ),
                "scope": "same-loopback-IP-and-same-nonexistent-account",
                "attempts": 12,
            }
            if summary["login_limit_probe"]["status_counts"] != {"401": 10, "429": 2}:
                raise RuntimeError("LOGIN_RATE_PROBE_MISMATCH")
            if args.worker_policy == "running":
                worker = await start_process(
                    environment, output / "worker.log", "app.workers", "worker"
                )
                sampler.processes["worker"] = worker
                await asyncio.sleep(0.5)
            barrier = asyncio.Event()
            tasks = [
                asyncio.create_task(
                    student_workload(client, student_headers, metrics, exam, index, args, barrier)
                )
                for index, (client, student_headers) in enumerate(sessions)
            ]
            workload_started = time.perf_counter()
            sampler.phase = "workload"
            barrier.set()
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)
            summary["workload_seconds"] = round(time.perf_counter() - workload_started, 3)
            results = [result for result in outcomes if isinstance(result, dict)]
            summary["students_completed"] = len(results)
            summary["student_failures"] = [
                str(result) if isinstance(result, HttpFailure) else type(result).__name__
                for result in outcomes
                if isinstance(result, BaseException)
            ]
            if summary["student_failures"]:
                raise RuntimeError("STUDENT_WORKLOAD_FAILED")
            recovery_started = time.perf_counter()
            sampler.phase = "recovery"
            if args.submission == "timeout":
                if args.worker_policy != "recover":
                    raise UnsafeTarget()
                deadline = max(datetime.fromisoformat(result["deadline_at"]) for result in results)
                await asyncio.sleep(
                    max(0, (deadline - datetime.now(timezone.utc)).total_seconds()) + 0.05
                )
                recovery_started = time.perf_counter()
            elif args.worker_policy == "recover":
                before = await audit_attempts(admin, metrics, results, args.submission)
                summary["before_worker_recovery"] = before
            if args.worker_policy == "recover":
                worker = await start_process(
                    environment, output / "worker.log", "app.workers", "worker"
                )
                sampler.processes["worker"] = worker
            async with asyncio.timeout(args.recovery_timeout):
                while True:
                    audit = await audit_attempts(admin, metrics, results, args.submission)
                    if audit["graded_attempts"] == len(results):
                        summary["audit"] = audit
                        break
                    await asyncio.sleep(0.25)
            summary["worker_completion_seconds"] = round(time.perf_counter() - recovery_started, 3)
            final_results = await metrics.request(
                admin,
                "GET",
                f"/api/staff/exams/{exam['id']}/final-results",
                phase="audit",
                operation="final_results",
                params={"page_size": 100},
            )
            if final_results.json()["total"] != args.students:
                raise RuntimeError("FINAL_RESULT_COUNT_MISMATCH")
            expected_scores = {result["id"]: Decimal(result["score"]) for result in results}
            observed_scores = {
                row["attempt_id"]: Decimal(row["final_score"])
                for row in final_results.json()["items"]
            }
            if observed_scores != expected_scores:
                raise RuntimeError("FINAL_RESULT_BINDING_MISMATCH")
            if args.submission == "timeout":
                summary["audit"]["timeout_receipts"] = 0
                for result in results:
                    student_client = sessions[result["student_index"]][0]
                    receipt = await metrics.request(
                        student_client,
                        "GET",
                        f"/api/student/attempts/{result['id']}",
                        phase="audit",
                        operation="timeout_receipt",
                    )
                    if (
                        receipt.json()["submission_type"] != "TIMEOUT"
                        or receipt.json()["effective_submitted_at"] != result["deadline_at"]
                    ):
                        raise RuntimeError("TIMEOUT_RECEIPT_MISMATCH")
                    summary["audit"]["timeout_receipts"] += 1
            summary["environment"]["database_after_workload"] = await database_information(
                environment
            )
            summary["exam_id"] = exam["id"]
            summary["success"] = True
    except Exception as exc:
        summary["success"] = False
        summary["error"] = str(exc) if isinstance(exc, HttpFailure) else type(exc).__name__
    finally:
        for client in clients:
            await client.aclose()
        await stop_process(worker)
        await stop_process(api)
        sampler.stopped.set()
        if sampler_task is not None:
            await sampler_task
        summary["environment"]["cpu_name"] = sampler.cpu_name
        summary["environment"]["physical_memory_bytes"] = sampler.samples[0][
            "physical_memory_bytes"
        ]
        summary["resources"] = sampler.summary()
        (output / "resource_samples.jsonl").write_text(
            "\n".join(json.dumps(row) for row in sampler.samples) + "\n", encoding="utf-8"
        )
        summary["services_stopped"] = True
        summary["total_seconds"] = round(time.perf_counter() - started_at, 3)
        for phase in ("workload", "sessions", "provision", "audit"):
            summary[phase if phase != "audit" else "audit_requests"] = metrics.summary(phase)
        (output / "requests.jsonl").write_text(
            "\n".join(json.dumps(row) for row in metrics.requests) + "\n", encoding="utf-8"
        )
        (output / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-env", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--database-name", default="exam_test_iteration6_load")
    parser.add_argument("--port", type=int, default=18001)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument(
        "--students", type=int, choices=range(1, 101), default=100, metavar="1..100"
    )
    parser.add_argument(
        "--questions", type=int, choices=range(1, 101), default=20, metavar="1..100"
    )
    parser.add_argument("--mode", choices=("steady", "peak"), default="steady")
    parser.add_argument("--think-seconds", type=float, default=1.0)
    parser.add_argument("--ramp-seconds", type=float, default=5.0)
    parser.add_argument("--worker-policy", choices=("running", "recover"), default="running")
    parser.add_argument("--submission", choices=("manual", "timeout"), default="manual")
    parser.add_argument("--deadline-seconds", type=int, default=300)
    parser.add_argument("--recovery-timeout", type=float, default=60)
    args = parser.parse_args()
    try:
        environment = isolated_environment(args)
        if min(args.think_seconds, args.ramp_seconds) < 0:
            raise UnsafeTarget()
        if args.submission == "timeout" and args.worker_policy != "recover":
            raise UnsafeTarget()
    except UnsafeTarget:
        print(json.dumps({"error": "UNSAFE_TARGET"}))
        return 2
    except Exception as exc:
        print(json.dumps({"error": type(exc).__name__}))
        return 2
    if args.check_only:
        print(json.dumps({"safe": True, "database": args.database_name, "redis_db": 13}))
        return 0
    try:
        summary = asyncio.run(run(args, environment))
    except Exception as exc:
        print(json.dumps({"error": type(exc).__name__}))
        return 1
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
