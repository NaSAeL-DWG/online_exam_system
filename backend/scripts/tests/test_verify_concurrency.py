import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "verify_concurrency.py"


def test_cli_refuses_remote_database_before_starting_services(tmp_path):
    """公开 CLI 必须先拒绝非本机目标，且错误不能回显连接凭据。"""

    source = tmp_path / "unsafe.env"
    source.write_text(
        "TEST_DATABASE_URL=postgresql+asyncpg://user:secret@example.com:55432/exam_test\n"
        "TEST_REDIS_URL=redis://:secret@127.0.0.1:16379/15\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source-env", str(source), "--check-only"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["error"] == "UNSAFE_TARGET"
    assert "secret" not in result.stdout + result.stderr


def test_cli_rejects_development_database_name(tmp_path):
    """即使源连接在本机，也不能把目标改成开发库。"""

    source = tmp_path / "local.env"
    source.write_text(
        "TEST_DATABASE_URL=postgresql+asyncpg://user:secret@127.0.0.1:55432/exam_test\n"
        "TEST_REDIS_URL=redis://:secret@127.0.0.1:16379/15\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-env",
            str(source),
            "--check-only",
            "--database-name",
            "exam_dev",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["error"] == "UNSAFE_TARGET"


@pytest.mark.skipif(
    not (SCRIPT.parents[2] / ".local" / "backend-test.env").exists(),
    reason="真实 HTTP 切片要求私有本机测试源配置",
)
def test_two_students_complete_real_http_attempts_and_worker_recovers_grading():
    """调用工具公开 CLI，验证独立会话、完整作答和独立 worker 补判。"""

    output = SCRIPT.parents[2] / ".local" / "iteration6" / "load" / "smoke"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-env",
            str(SCRIPT.parents[2] / ".local" / "backend-test.env"),
            "--output-dir",
            str(output),
            "--students",
            "2",
            "--questions",
            "4",
            "--think-seconds",
            "0.01",
            "--worker-policy",
            "recover",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["students_completed"] == 2
    assert summary["workload"]["server_errors"] == 0
    assert summary["audit"]["consistent_attempts"] == 2
    assert summary["audit"]["graded_attempts"] == 2
    assert summary["services_stopped"] is True
    assert summary["resources"]["workload"]["api_rss_peak_bytes"] > 0
    assert summary["resources"]["workload"]["api_cpu_one_core_peak_percent"] > 0
    assert summary["environment"]["physical_memory_bytes"] > 0
    assert summary["login_limit_probe"]["status_counts"] == {"401": 10, "429": 2}


@pytest.mark.skipif(
    not (SCRIPT.parents[2] / ".local" / "backend-test.env").exists(),
    reason="真实截止恢复要求私有本机测试源配置",
)
def test_expired_students_are_submitted_by_restarted_worker_with_saved_answers():
    """使用真实截止时钟与 worker 启动恢复，学生不重放开始或提交。"""

    output = SCRIPT.parents[2] / ".local" / "iteration6" / "load" / "timeout-smoke"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-env",
            str(SCRIPT.parents[2] / ".local" / "backend-test.env"),
            "--output-dir",
            str(output),
            "--students",
            "2",
            "--questions",
            "4",
            "--mode",
            "peak",
            "--worker-policy",
            "recover",
            "--submission",
            "timeout",
            "--deadline-seconds",
            "5",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["audit"]["timeout_receipts"] == 2
    assert summary["audit"]["consistent_attempts"] == 2
    assert summary["audit"]["graded_attempts"] == 2
    assert summary["services_stopped"] is True
