"""认证骨架（SPEC 第 4 节）：g.user 钩子、login_required、next 校验与登录限流。

本模块只回答「当前是谁」和「这次登录该不该按失败处理」；具体路由在
app/blueprints/auth.py。本轮（#14）不给其它蓝图加 @login_required，因为
既有 21 条用例都是匿名访问，全量加装饰器是 #15 的工作。
"""

from __future__ import annotations

import time
from functools import wraps
from urllib.parse import urlsplit

from flask import current_app, g, redirect, request, session, url_for
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import User

# 登录失败限流（SPEC 第 4 节）：同一 username 在 60 秒窗口内累计 5 次失败后，
# 窗口内该 username 一律按失败返回。内存字典实现，重启即失效，SPEC 明确接受。
LOGIN_FAILURE_LIMIT = 5
LOGIN_FAILURE_WINDOW = 60.0  # 秒

# username -> 最近的失败时间戳（time.monotonic，不受系统改时间影响）
_login_failures: dict[str, list[float]] = {}


# ---------------------------------------------------------------- 当前用户


def get_current_user() -> User | None:
    """当前登录用户；未登录返回 None（值由 load_logged_in_user 写进 g.user）。"""
    return g.get("user")


def load_logged_in_user() -> None:
    """before_request 钩子：把 session['user_id'] 解析成 g.user。

    未登录、会话里的用户不存在、账号被停用都只让 g.user 为 None，绝不抛错。
    """
    g.user = None
    user_id = session.get("user_id")
    if user_id is None:
        return
    try:
        user = db.session.get(User, user_id)
    except SQLAlchemyError as error:  # 库还没建（未跑 init-db）时按未登录处理
        db.session.rollback()
        current_app.logger.warning("读取登录用户失败，按未登录处理：%s", error)
        return
    if user is None:
        session.pop("user_id", None)  # 用户被删：清掉脏会话
        return
    if not user.is_active:
        session.pop("user_id", None)  # 账号被停用：立刻退出
        return
    g.user = user


def _current_relative_path() -> str:
    """未登录被拦下的原路径（带查询串，不带主机名）。"""
    if request.query_string:
        return request.full_path
    return request.path


def login_required(view):
    """未登录 → 302 到 /login?next=<原路径>；已登录直接执行视图。"""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if get_current_user() is None:
            return redirect(url_for("auth.login", next=_current_relative_path()))
        return view(*args, **kwargs)

    return wrapped


# ---------------------------------------------------------------- next 校验


def safe_next_target(raw) -> str | None:
    """校验登录回跳目标：只接受站内相对路径，其余（含外域）返回 None。

    规则（SPEC 第 4 节）：以单个斜杠开头，且不以双斜杠开头；
    额外拒绝反斜杠，因为浏览器会把 / 反斜杠 evil.com 归一化成双斜杠外域。
    """
    if not raw:
        return None
    target = str(raw).strip()
    if not target.startswith("/") or target.startswith("//"):
        return None
    if "\\" in target:  # 反斜杠绕行写法
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:  # 兜底：绝对 URL 一律拒绝
        return None
    return target


# ---------------------------------------------------------------- 登录限流


def _prune(username: str, now: float) -> list[float]:
    """剔除窗口外的失败时间戳，顺带删掉空条目，避免字典无限增长。"""
    hits = [
        stamp
        for stamp in _login_failures.get(username, ())
        if now - stamp < LOGIN_FAILURE_WINDOW
    ]
    if hits:
        _login_failures[username] = hits
    else:
        _login_failures.pop(username, None)
    return hits


def is_login_blocked(username: str, now: float | None = None) -> bool:
    """该 username 是否处于限流窗口内（窗口内失败次数已达上限）。"""
    if not username:
        return False
    timestamp = time.monotonic() if now is None else now
    return len(_prune(username, timestamp)) >= LOGIN_FAILURE_LIMIT


def register_login_failure(username: str, now: float | None = None) -> None:
    """记一次登录失败；空 username 不记账，免得被刷成海量 key。"""
    if not username:
        return
    timestamp = time.monotonic() if now is None else now
    hits = _prune(username, timestamp)
    hits.append(timestamp)
    _login_failures[username] = hits


def clear_login_failures(username: str) -> None:
    """登录成功后清空该 username 的失败记录。"""
    _login_failures.pop(username, None)


def reset_login_failures() -> None:
    """清空全部限流状态（测试隔离用）。"""
    _login_failures.clear()
