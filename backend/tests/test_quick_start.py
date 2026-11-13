import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows cmd.exe")
@pytest.mark.parametrize("missing", ["python", "vite", "env", "node"])
def test_quick_start_missing_environment_never_runs_installer(tmp_path, missing):
    # 快速启动必须提示首次安装，不能偷偷进入安装流程或创建配置。
    root = Path(__file__).resolve().parents[2]
    folder = tmp_path / "QFO test & space"
    folder.mkdir()
    shutil.copyfile(root / "run_quick_start.bat", folder / "run_quick_start.bat")
    (folder / "run_first_time.bat").write_text(
        "@echo off\necho INSTALLER_WAS_CALLED\nexit /b 99\n", encoding="ascii"
    )
    prerequisites = {
        "python": "backend/.venv/Scripts/python.exe",
        "vite": "frontend/node_modules/vite/bin/vite.js",
        "env": "backend/.env",
    }
    for name, relative in prerequisites.items():
        if name != missing:
            path = folder / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
    env = dict(os.environ)
    if missing == "node":
        env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    result = subprocess.run(
        [os.environ["COMSPEC"], "/d", "/c", "run_quick_start.bat"],
        cwd=folder, env=env, input="\n", capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=15,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "run_first_time.bat" in result.stdout
    assert "INSTALLER_WAS_CALLED" not in result.stdout
    if missing in prerequisites:
        assert not (folder / prerequisites[missing]).exists()


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows cmd.exe")
@pytest.mark.parametrize("service,limit", [("backend", 30), ("frontend", 20)])
@pytest.mark.parametrize("failed_checks", [0, 2, None])
def test_wait_progress_reports_success_or_failure(tmp_path, service, limit, failed_checks):
    # 执行真实等待分支；仅替换外部 HTTP 检测、延时与启动进程，避免干扰本机服务。
    root = Path(__file__).resolve().parents[2]
    launcher = (root / "run_quick_start.bat").read_text(encoding="utf-8")
    body = launcher.split(f":wait_{service}\n", 1)[1]
    body = f":wait_{service}\n" + body.split("\n:backend_http_ready\n", 1)[0]
    body = re.sub(r"^start .*?$", "rem test: do not launch processes", body, flags=re.M)
    body = body.replace(
        'powershell -NoProfile -Command "Start-Sleep -Seconds 1"',
        "rem test: skip the polling delay",
    )
    probes = ""
    for name in ("backend", "frontend"):
        probes += f"\n:{name}_http_ready\n"
        if name != service:
            probes += "exit /b 0\n"
        elif failed_checks is None:
            probes += "exit /b 1\n"
        else:
            probes += (
                'set /a CHECKS+=1 >nul\n'
                f'if %CHECKS% leq {failed_checks} exit /b 1\n'
                'exit /b 0\n'
            )
    (tmp_path / "wait-test.bat").write_text(
        '@echo off\nsetlocal\nset "TRIES=0"\nset "CHECKS=0"\n' + body + probes,
        encoding="ascii",
    )
    result = subprocess.run(
        [os.environ["COMSPEC"], "/d", "/c", "wait-test.bat"],
        cwd=tmp_path, input="\n", capture_output=True, text=True, timeout=10,
    )
    label = service.capitalize()
    count = limit if failed_checks is None else failed_checks
    progress = re.findall(rf"\[WAIT\] {label} \[(\d+)/{limit}\]", result.stdout)
    assert progress == [str(i) for i in range(1, count + 1)], result.stdout
    if failed_checks is None:
        assert result.returncode == 1
        assert f"[FAIL] {label}" in result.stdout
        assert "[OK] Backend and frontend are responding." not in result.stdout
    else:
        assert result.returncode == 0
        assert f"[OK] {label} is ready." in result.stdout
        assert "[FAIL]" not in result.stdout
