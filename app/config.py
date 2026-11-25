"""应用配置：只暴露少量可由环境变量覆盖的项，其余按 SPEC 固定。

安全默认值的落点：
- Config.SECRET_KEY 只做「读环境变量」，没有硬编码兜底（未设置时为 None）。
- 「必须配置真实 SECRET_KEY」的判定是纯函数 resolve_secret_key：入参显式、
  不读调用栈，由 create_app() 在合并完配置后调用（本模块 import 期不求值）。
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

# 项目根目录（/mnt/d/Project/ShoppingMgr）
BASE_DIR = Path(__file__).resolve().parent.parent

# 调试开关的环境变量名：只有 1/true/yes（忽略大小写与首尾空白）才算显式开启
DEBUG_ENV_NAME = "FLASK_DEBUG"
_TRUE_VALUES = frozenset({"1", "true", "yes"})

# 仅供本地调试的固定开发密钥：绝不能出现在生产环境
DEV_SECRET_KEY = "shoppingmgr-dev-only-secret"

# 缺少 SECRET_KEY 时的报错文案：必须能直接照做
MISSING_SECRET_KEY_MESSAGE = (
    "未设置 SECRET_KEY：请在 .env 或环境变量里配置（参考 .env.example），"
    "或设置 FLASK_DEBUG=1 用于本地开发"
)

# 退回固定开发密钥时的警告文案（由 create_app 用 app.logger.warning 打出）
DEV_SECRET_KEY_WARNING = (
    "未设置 SECRET_KEY，正在使用固定的开发密钥：仅供本地调试，"
    "请勿在生产环境使用；部署前请配置真实 SECRET_KEY（参考 .env.example）。"
)


def debug_enabled_by_env() -> bool:
    """FLASK_DEBUG 是否明确请求调试。

    只认 1/true/yes（忽略大小写），其余取值（含未设置、0、false、no）一律为关闭。
    """
    return os.environ.get(DEBUG_ENV_NAME, "").strip().lower() in _TRUE_VALUES


def resolve_secret_key(secret_key: str | None, *, debug: bool) -> tuple[str, bool]:
    """确定本次运行使用的 SECRET_KEY，返回 (生效密钥, 是否退回了固定开发密钥)。

    - 传入非空：直接使用，第二项为 False；
    - 传入为空且 debug=True：退回 DEV_SECRET_KEY，第二项为 True，警告由调用方打；
    - 传入为空且 debug=False：抛 RuntimeError，消息可直接照做。
    """
    value = (secret_key or "").strip()
    if value:
        return value, False
    if debug:
        return DEV_SECRET_KEY, True
    raise RuntimeError(MISSING_SECRET_KEY_MESSAGE)


class Config:
    """默认配置：数据库固定为 SQLite 的 instance/shop.db。"""

    # 只读环境变量，没有硬编码兜底；是否必填由 resolve_secret_key 在 create_app 里判定
    SECRET_KEY = os.environ.get("SECRET_KEY")

    # 相对路径由 Flask-SQLAlchemy 解析到 app.instance_path，
    # 即项目根下的 instance/shop.db（SPEC 第 1 节）。
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///shop.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ---- 会话（SPEC 第 4 节）：登录成功会写 session.permanent，有效期以此为准
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    # Lax：跨站 POST 不带 cookie，同站导航仍然带，兼顾 CSRF 与正常跳转
    SESSION_COOKIE_SAMESITE = "Lax"
    # 本地 http 必须关闭（否则浏览器不回传 cookie）；部署到 https 时用
    # 环境变量 SESSION_COOKIE_SECURE=1 打开，与 SECRET_KEY 一样只在 import 期读一次。
    SESSION_COOKIE_SECURE = (
        os.environ.get("SESSION_COOKIE_SECURE", "").strip().lower() in _TRUE_VALUES
    )
