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
# users=1：init-db 先建 demo 用户（#15 起种子数据全部归属它），再灌 5 张业务表
SEED_COUNTS = {
    "categories": 5,
    "products": 8,
    "shopping_lists": 1,
    "shopping_items": 3,
    "expenses": 6,
    "users": 1,
}

# #15 起 5 张业务表都要有 user_id（SPEC 第 3、10 节）
USER_ID_TABLES = (
    "categories",
    "products",
    "shopping_lists",
    "shopping_items",
    "expenses",
)


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


def _user_id(db_path: Path, username: str) -> int:
    """按用户名取 id（init-admin 建出来的归属用户）。"""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
    assert row is not None, f"users 表里没有 {username}"
    return int(row[0])


def _user_ids(db_path: Path, table: str) -> list[int]:
    """一张表里所有行的 user_id（按 id 排序）。"""
    with sqlite3.connect(db_path) as conn:
        return [
            int(row[0])
            for row in conn.execute(f"SELECT user_id FROM {table} ORDER BY id")
        ]


def _insert_v1_rows(db_path: Path) -> None:
    """往 v1 库塞一套最小业务数据：5 张表各一行（模拟上线前的存量数据）。"""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO categories (name, note, created_at)"
            " VALUES ('蔬果', '生鲜', '2026-11-01 00:00:00')"
        )
        conn.execute(
            "INSERT INTO products (name, category_id, unit, price, barcode, note,"
            " is_active, created_at)"
            " VALUES ('苹果', 1, '件', 6.5, '', '', 1, '2026-11-01 00:00:00')"
        )
        conn.execute(
            "INSERT INTO shopping_lists (name, note, status, created_at)"
            " VALUES ('本周采购', '', 'draft', '2026-11-01 00:00:00')"
        )
        conn.execute(
            "INSERT INTO shopping_items (list_id, product_id, name, qty, unit_price,"
            " done, created_at)"
            " VALUES (1, 1, '苹果', 2, 6.5, 0, '2026-11-01 00:00:00')"
        )
        conn.execute(
            "INSERT INTO expenses (spent_on, amount, category_id, product_id, note,"
            " created_at)"
            " VALUES ('2026-11-02', 13.0, 1, 1, '', '2026-11-01 00:00:00')"
        )
        conn.commit()


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
    # 期望集合之外再逐表确认 user_id 真的建出来了（防止只加表名不加列）
    for table in USER_ID_TABLES:
        assert "user_id" in _columns(db_path, table), f"{table} 缺 user_id 列"
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


def test_user_id_columns_are_not_null_and_indexed(tmp_path):
    """(e) user_id 必须 NOT NULL 且有索引（SPEC 第 3 节），barcode 放开为可空。"""
    db_path = tmp_path / "user-id-schema.db"

    _flask(db_path, "db", "upgrade")

    for table in USER_ID_TABLES:
        with sqlite3.connect(db_path) as conn:
            info = {row[1]: row[3] for row in conn.execute(f"PRAGMA table_info({table})")}
            indexes = {row[1] for row in conn.execute(f"PRAGMA index_list({table})")}
        assert info.get("user_id") == 1, f"{table}.user_id 应为 NOT NULL"
        assert f"ix_{table}_user_id" in indexes, f"{table} 缺 user_id 索引"
    with sqlite3.connect(db_path) as conn:
        barcode = {
            row[1]: row[3] for row in conn.execute("PRAGMA table_info(products)")
        }
    assert barcode.get("barcode") == 0, "products.barcode 应为可空"


def test_legacy_v1_rows_are_backfilled_to_first_user(tmp_path):
    """(f) v1 库插数据 + 建用户 → upgrade 到 head：user_id 全部回填到该用户。"""
    db_path = tmp_path / "legacy.db"
    _flask(db_path, "db", "upgrade", "b4ed9413adcc")  # v1 基线
    _insert_v1_rows(db_path)
    _flask(db_path, "db", "upgrade", "0554acb803f0")  # 先补上 users 表（#14）
    _flask(
        db_path,
        "init-admin",
        "--username",
        "legacy",
        "--password",
        "legacy1234",
        "--display-name",
        "老用户",
    )

    _flask(db_path, "db", "upgrade")  # 到 head：加 user_id + 回填

    assert _stamped_version(db_path) == _head(db_path)
    owner = _user_id(db_path, "legacy")
    assert owner > 0
    for table in USER_ID_TABLES:
        assert _user_ids(db_path, table) == [owner], f"{table} 未回填到唯一用户"
    # barcode 的空串在回填时归一为 NULL（否则唯一约束撞车）
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT barcode FROM products").fetchone()[0] is None


def test_upgrade_with_rows_but_no_user_fails_with_init_admin_hint(tmp_path):
    """(g) 有存量数据但 users 为空：迁移直接失败并提示先 init-admin，且不留半成品。"""
    db_path = tmp_path / "no-user.db"
    _flask(db_path, "db", "upgrade", "b4ed9413adcc")
    _insert_v1_rows(db_path)
    _flask(db_path, "db", "upgrade", "0554acb803f0")  # users 表已建但没人

    result = _run(db_path, "db", "upgrade")

    assert result.returncode != 0, "users 为空时迁移必须失败"
    output = result.stdout + result.stderr
    assert "init-admin" in output, f"报错没给修复命令：\n{output}"
    assert "user_id" not in _columns(db_path, "categories"), "失败前不应留下半成品"
    assert _stamped_version(db_path) == "0554acb803f0"
