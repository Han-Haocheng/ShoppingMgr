"""run.py 在导入 app 之前加载 .env：用子进程真实跑一遍，不 mock 环境。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# 子进程只导入 run（会让 create_app 跑起来），最后打印生效的 SECRET_KEY
IMPORT_RUN_CODE = 'import run; print(run.app.config["SECRET_KEY"])'
# 子进程必须从零开始：清掉可能从本机/CI/shell 带进来的同名变量
CLEARED_ENV_VARS = ("SECRET_KEY", "FLASK_DEBUG", "DATABASE_URL", "HOST", "PORT")


def _child_env(**overrides: str) -> dict[str, str]:
    """干净的子进程环境：清掉相关变量，PYTHONPATH 指向仓库根，其余沿用当前进程。"""
    env = {key: value for key, value in os.environ.items() if key not in CLEARED_ENV_VARS}
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join([str(REPO_ROOT), existing]) if existing else str(REPO_ROOT)
    env.update(overrides)
    return env


def _run_in(tmp_path: Path, **overrides: str) -> subprocess.CompletedProcess[str]:
    """在 tmp_path 里以子进程执行 IMPORT_RUN_CODE（cwd=tmp_path 才可能读到 tmp 的 .env）。"""
    return subprocess.run(
        [sys.executable, "-c", IMPORT_RUN_CODE],
        cwd=tmp_path,
        env=_child_env(**overrides),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _write_dotenv(tmp_path: Path, *lines: str) -> None:
    """只写 tmp_path 下的 .env，绝不碰仓库根的 .env。"""
    (tmp_path / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_dotenv_file_supplies_secret_key(tmp_path):
    """tmp 的 .env 里有 SECRET_KEY → 子进程导入 run 成功，且读到的就是 .env 的值。"""
    _write_dotenv(
        tmp_path,
        "SECRET_KEY=from-dotenv-file",
        f"DATABASE_URL=sqlite:///{tmp_path / 'x.db'}",
    )

    result = _run_in(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "from-dotenv-file" in result.stdout


def test_missing_secret_key_still_refuses_to_start(tmp_path):
    """.env 不含 SECRET_KEY 且环境变量也清空 → 仍然拒绝启动（拒绝启动规则没被 dotenv 削弱）。"""
    _write_dotenv(tmp_path, f"DATABASE_URL=sqlite:///{tmp_path / 'x.db'}")

    result = _run_in(tmp_path)

    assert result.returncode != 0
    assert "SECRET_KEY" in result.stderr


def test_real_env_var_wins_over_dotenv(tmp_path):
    """真实环境变量优先于 .env（没有用 override=True），CI 与 shell export 不会被 .env 冲掉。"""
    _write_dotenv(tmp_path, "SECRET_KEY=from-dotenv-file")

    result = _run_in(tmp_path, SECRET_KEY="from-real-env")

    assert result.returncode == 0, result.stderr
    assert "from-real-env" in result.stdout
    assert "from-dotenv-file" not in result.stdout
