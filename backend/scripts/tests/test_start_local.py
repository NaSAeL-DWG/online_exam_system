"""通过 PowerShell 命令入口验证本地启动与配置反馈。"""

import os
import shutil
import subprocess
from pathlib import Path
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "start-local.ps1"
pytestmark = pytest.mark.skipif(os.name != "nt", reason="此启动入口面向 Windows/WSL")


def invoke(script):
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


def test_missing_config_explains_setup_without_starting_services(tmp_path):
    shutil.copyfile(SCRIPT, tmp_path / SCRIPT.name)
    result = invoke(tmp_path / SCRIPT.name)
    assert result.returncode == 1
    assert "backend/.env" in result.stdout + result.stderr
    assert "docs/quick-start.md" in result.stdout + result.stderr
    assert "STARTED" not in result.stdout


def test_running_services_are_reused_and_frontend_proxy_remains_ready():
    for _ in range(2):
        result = invoke(SCRIPT)
        assert result.returncode == 0, result.stdout + result.stderr
        for service in ("postgres", "redis", "api", "worker", "frontend"):
            assert f"REUSED {service}" in result.stdout
        assert "STARTED" not in result.stdout
    with urlopen("http://127.0.0.1:5173/api/health", timeout=5) as response:
        assert response.status == 200
