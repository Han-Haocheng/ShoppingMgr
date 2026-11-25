"""Alembic 迁移基线的用例（SPEC 第 10 节）。

三条断言各走一遍真实的 CLI：迁移是 CLI 行为，直接调 Alembic API 会绕过
`init-db` 里的 stamp，等于没验到「建库两条路径是否对齐」。
每个用例都用 tmp_path 下的独立 sqlite 文件，并通过 SECRET_KEY / DATABASE_URL
覆盖环境，绝不碰开发库 instance/shop.db。
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 迁移到 head 应当建出来的业务表：v1 基线 5 张 + v2 的 users（#14 引入）
BUSINESS_TABLES = {
    "categories",
    "products",
    "shopping_lists",
    "shopping_items",
    "expenses",
    "users",
}

# users 表的列（SPEC 第 3 节）：防止只把表名加进期望集合、迁移却漏了列
USERS_COLUMNS = {
    "id",
    "username",
    "password_hash",
    "display_name",
    "is_active",
    "last_login_at",
    "created_at",
}

# init-db 的示例数据规模（app/utils.py seed_sample_data / README 快速开始）
SEED_COUNTS = {
    "categories": 5,
    "products": 8,
    "shopping_lists": 1,
    "shopping_items": 3,
    "expenses": 6,
    "users": 0,  # 种子数据不造用户；首个用户由注册流程产生
}


def _env(db_path: Path) -> dict[str, str]:
    """子进程环境：清掉可能干扰的变量，指向临时库。

    FLASK_DEBUG 必须去掉，否则 create_app() 会开调试模式（子进程里无意义且掩盖报错）。
    """
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"FLASK_DEBUG", "DATABASE_URL", "SECRET_KEY"}
    }
    env["SECRET_KEY"] = "migrations-test-secret-key"
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["PYTHONPATH"] = str(ROOT)
    return env


def _run(db_path: Path, *args: str) -> subprocess.CompletedProcess:
    """跑一次 `.venv/bin/python -m flask --app run:app <args>`（禁网络）。"""
    return subprocess.run(
        [sys.executable, "-m", "flask", "--app", "run:app", *args],
        cwd=ROOT,
        env=_env(db_path),
        capture_output=True,
        text=True,
        timeout=180,
    )


def _flask(db_path: Path, *args: str) -> subprocess.CompletedProcess:
    """同上，但要求 rc=0；失败时把两个流都带进断言消息。"""
    result = _run(db_path, *args)
    assert result.returncode == 0, (
        f"flask {' '.join(args)} 失败（rc={result.returncode}）：\n"
        f"--- STDOUT ---\n{result.stdout}\n--- STDERR ---\n{result.stderr}"
    )
    return result


def _tables(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in rows}


def _stamped_version(db_path: Path) -> str | None:
    """alembic_version 里的版本号；表不存在返回 None。"""
    with sqlite3.connect(db_path) as conn:
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"
        ).fetchone()
        if not exists:
            return None
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    return row[0] if row else None


def _head(db_path: Path) -> str:
    """从 CLI 读 head revision，测试里不硬编码版本号（加新迁移后仍然有效）。"""
    output = _flask(db_path, "db", "heads").stdout
    heads = [line for line in output.splitlines() if "(head)" in line]
    assert heads, f"db heads 没输出 head 行：\n{output}"
    return heads[0].split()[0]


def _columns(db_path: Path, table: str) -> set[str]:
    """读一张表的列名（PRAGMA table_info）。"""
    with sqlite3.connect(db_path) as conn:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _counts(db_path: Path) -> dict[str, int]:
    with sqlite3.connect(db_path) as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in sorted(BUSINESS_TABLES)
        }


def test_db_upgrade_creates_five_tables_and_stamps_head(tmp_path):
    """(a) 空库执行 db upgrade：v1 五张表 + v2 的 users 齐全，alembic_version 等于 head。"""
    db_path = tmp_path / "upgrade.db"

    _flask(db_path, "db", "upgrade")

    assert _tables(db_path) - {"alembic_version"} == BUSINESS_TABLES
    head = _head(db_path)
    assert _stamped_version(db_path) == head

    current = _flask(db_path, "db", "current")
    assert f"{head} (head)" in (current.stdout + current.stderr)


def test_init_db_stamps_head(tmp_path):
    """(b) init-db 建出来的库也带 alembic_version 且等于 head，种子数据照旧写入。"""
    db_path = tmp_path / "init-db.db"

    _flask(db_path, "init-db")

    assert _tables(db_path) - {"alembic_version"} == BUSINESS_TABLES
    assert _stamped_version(db_path) == _head(db_path)
    assert _counts(db_path) == SEED_COUNTS


def test_upgrade_after_init_db_is_noop(tmp_path):
    """(c) init-db 之后再 upgrade：不报错、不重放迁移、表与行数都不变。"""
    db_path = tmp_path / "noop.db"
    _flask(db_path, "init-db")
    tables_before = _tables(db_path)
    counts_before = _counts(db_path)

    result = _flask(db_path, "db", "upgrade")

    assert "Running upgrade" not in (result.stdout + result.stderr)
    assert _tables(db_path) == tables_before
    assert _counts(db_path) == counts_before


def test_db_upgrade_creates_users_table_with_expected_columns(tmp_path):
    """(d) upgrade 到 head 后 users 表存在，列与 SPEC 第 3 节一致（防只加表名不加列）。"""
    db_path = tmp_path / "users.db"

    _flask(db_path, "db", "upgrade")

    assert "users" in _tables(db_path)
    assert _columns(db_path, "users") == USERS_COLUMNS
