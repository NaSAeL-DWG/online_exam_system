import json
import subprocess
import sys
from pathlib import Path


def test_cleanup_command_exposes_retry_and_pending_counts():
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "retry-session-cleanups"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert set(report) == {"attempted", "completed", "pending", "failed"}
    assert report["pending"] == 0


def test_cli_reports_business_code_without_python_traceback():
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "reset-admin", "--login-name", "missing-cli-account"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode != 0
    assert "USER_NOT_FOUND" in result.stderr
    assert "Traceback" not in result.stderr


def test_cleanup_limit_must_be_positive():
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "retry-session-cleanups", "--limit", "0"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 2
