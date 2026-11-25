"""认证路由（SPEC 第 5 节）：/register、/login、/logout。"""

from __future__ import annotations

from datetime import datetime

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from ..auth import (
    clear_login_failures,
    get_current_user,
    is_login_blocked,
    login_required,
    register_login_failure,
    safe_next_target,
)
from ..extensions import db
from ..models import User

bp = Blueprint("auth", __name__)

MIN_PASSWORD_LENGTH = 8
USERNAME_MAX_LENGTH = 60
# 登录失败统一文案：不区分「用户不存在」「密码错误」「账号停用」（SPEC 第 4 节）
LOGIN_FAILED_MESSAGE = "用户名或密码不正确"


def _index():
    """登录成功 / 已登录时的默认落点。"""
    return redirect(url_for("main.index"))


def _find_user(username: str) -> User | None:
    """按用户名取用户（username 唯一）。"""
    return db.session.query(User).filter_by(username=username).first()


def _start_session(user: User) -> None:
    """登录成功后的会话写入：先清空（防会话固定），再写 user_id 并设为持久会话。"""
    session.clear()
    session["user_id"] = user.id
    session.permanent = True  # 有效期取 Config.PERMANENT_SESSION_LIFETIME（7 天）


def _validate_register(username: str, display_name: str, password: str, password2: str):
    """注册校验：返回错误文案（None 表示通过）。"""
    if not username:
        return "请填写用户名"
    if len(username) > USERNAME_MAX_LENGTH:
        return f"用户名最长 {USERNAME_MAX_LENGTH} 个字符"
    if len(display_name) > USERNAME_MAX_LENGTH:
        return f"显示名称最长 {USERNAME_MAX_LENGTH} 个字符"
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"密码至少 {MIN_PASSWORD_LENGTH} 位"
    if password == username:
        return "密码不能与用户名相同"
    if password != password2:
        return "两次输入的密码不一致"
    if _find_user(username) is not None:
        return "用户名已被占用，请换一个"
    return None


@bp.route("/register", methods=["GET", "POST"])
def register():
    """注册（字段名见 SPEC 第 8 节）；成功后直接登录并回首页。"""
    if get_current_user() is not None:
        return _index()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        display_name = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        error = _validate_register(username, display_name, password, password2)
        if error is None:
            user = User(username=username, display_name=display_name)
            user.set_password(password)  # 只存哈希，原始密码不落库、不写日志
            db.session.add(user)
            db.session.commit()
            _start_session(user)
            flash("注册成功，已自动登录", "success")
            return _index()

        # 校验失败：HTTP 200 重渲染同模板，已填值由模板从 request.form 回填
        flash(error, "danger")
        return render_template("auth/register.html"), 200

    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    """登录（字段名见 SPEC 第 8 节）；成功回跳站内 next，否则首页。"""
    if get_current_user() is not None:
        return _index()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        raw_next = request.form.get("next", "")
        password = request.form.get("password", "")

        # 限流优先于任何校验：窗口内已失败 5 次的 username 一律按失败处理
        if is_login_blocked(username):
            flash(LOGIN_FAILED_MESSAGE, "danger")
            return render_template("auth/login.html", next=safe_next_target(raw_next)), 200

        user = _find_user(username)
        if user is None or not user.is_active or not user.check_password(password):
            register_login_failure(username)
            flash(LOGIN_FAILED_MESSAGE, "danger")
            return render_template("auth/login.html", next=safe_next_target(raw_next)), 200

        clear_login_failures(username)
        _start_session(user)
        user.last_login_at = datetime.now()
        db.session.commit()
        flash("登录成功", "success")

        target = safe_next_target(raw_next)
        if target is not None:
            return redirect(target)
        return _index()

    return render_template("auth/login.html", next=safe_next_target(request.args.get("next")))


@bp.post("/logout")
@login_required
def logout():
    """登出：清空会话后回到登录页。"""
    session.clear()
    flash("已退出登录", "success")
    return redirect(url_for("auth.login"))
