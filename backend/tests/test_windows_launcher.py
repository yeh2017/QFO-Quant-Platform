import os
from pathlib import Path
import re
import subprocess
import sys

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows cmd.exe")
@pytest.mark.parametrize(
    ("available_source", "attempted_hosts"),
    [
        ("mirrors.aliyun.com", ["mirrors.aliyun.com"]),
        ("mirrors.cloud.tencent.com", ["mirrors.aliyun.com", "mirrors.cloud.tencent.com"]),
        ("pypi.org", ["mirrors.aliyun.com", "mirrors.cloud.tencent.com", "pypi.org"]),
        ("", ["mirrors.aliyun.com", "mirrors.cloud.tencent.com", "pypi.org"]),
    ],
)
def test_backend_dependency_source_fallback(tmp_path, available_source, attempted_hosts):
    # Run the real batch subroutine; stand in for pip's external network calls.
    root = Path(__file__).resolve().parents[2]
    launcher = (root / "run_first_time.bat").read_text(encoding="utf-8")
    subroutine = re.search(r"^:install_backend_deps\n.*?(?=^:\w+|\Z)", launcher, re.M | re.S)
    assert subroutine is not None
    script = tmp_path / "test-install.bat"
    script.write_text(
        "@echo off\ncall :install_backend_deps\nexit /b %errorlevel%\n\n"
        + subroutine.group(),
        encoding="ascii",
    )
    pip = tmp_path / "pip"
    pip.mkdir()
    (pip / "__init__.py").touch()
    (pip / "__main__.py").write_text(
        "import os, sys\n"
        "from urllib.parse import urlsplit\n"
        "host = urlsplit(sys.argv[sys.argv.index('-i') + 1]).hostname\n"
        "print('TEST_INDEX=' + host)\n"
        "raise SystemExit(0 if host == os.environ['QFO_TEST_INDEX'] else 1)\n",
        encoding="ascii",
    )
    result = subprocess.run(
        [os.environ["COMSPEC"], "/d", "/c", "test-install.bat"],
        cwd=tmp_path,
        env={
            **os.environ,
            "VENV_PYTHON": sys.executable,
            "BACKEND": str(root / "backend"),
            "PYTHONPATH": str(tmp_path),
            "QFO_TEST_INDEX": available_source,
        },
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert re.findall(r"^TEST_INDEX=(.+)$", result.stdout, re.M) == attempted_hosts
    assert result.returncode == (0 if available_source else 1)
    if not available_source:
        assert "DNS" in result.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows cmd.exe")
@pytest.mark.parametrize("installed_version,ready", [("1.18.91", True), ("1.20.37", False)])
def test_backend_readiness_requires_pinned_akshare(tmp_path, installed_version, ready):
    # 模拟安装元数据，执行真实就绪检查；旧环境不能跳过 requirements 中的版本调整。
    root = Path(__file__).resolve().parents[2]
    launcher = (root / "run_first_time.bat").read_text(encoding="utf-8")
    subroutine = re.search(r"^:backend_ready\n.*?(?=^:\w+|\Z)", launcher, re.M | re.S)
    assert subroutine is not None
    metadata = tmp_path / f"akshare-{installed_version}.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: akshare\nVersion: {installed_version}\n", encoding="utf-8"
    )
    (tmp_path / "check.bat").write_text(
        "@echo off\ncall :backend_ready\nexit /b %errorlevel%\n" + subroutine.group(), encoding="ascii"
    )
    result = subprocess.run(
        [os.environ["COMSPEC"], "/d", "/c", "check.bat"], cwd=tmp_path,
        env={**os.environ, "VENV_PYTHON": sys.executable, "PYTHONPATH": str(tmp_path)},
        capture_output=True, timeout=30,
    )
    assert (result.returncode == 0) == ready, result.stdout + result.stderr
