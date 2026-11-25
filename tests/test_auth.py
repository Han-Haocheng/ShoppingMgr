"""用户与登录用例（SPEC 第 4、11 节）。"""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest
from werkzeug.security import generate_password_hash

from app.auth import LOGIN_FAILURE_LIMIT, reset_login_failures, safe_next_target
from app.extensions import db as _db
from app.models import User

PASSWORD = "password123"
USERNAME = "alice"


@pytest.fixture(autouse=True)
def _clear_rate_limit():
    """限流是模块级内存字典，用例之间必须互相隔离。"""
    reset_login_failures()
    yield
    reset_login_failures()


def _text(response) -> str:
    return response.get_data(as_text=True)


def _register(client, username=USERNAME, password=PASSWORD, password2=None, display_name=""):
    """走注册 POST；password2 默认与 password 一致。"""
    return client.post(
        "/register",
        data={
            "username": username,
            "display_name": display_name,
            "password": password,
            "password2": password if password2 is None else password2,
        },
        follow_redirects=False,
    )


def _login(client, username=USERNAME, password=PASSWORD, next_value=None):
    """走登录 POST；next_value 非 None 时带上隐藏域。"""
    data = {"username": username, "password": password}
    if next_value is not None:
        data["next"] = next_value
    return client.post("/login", data=data, follow_redirects=False)


def _create_user(app, username=USERNAME, password=PASSWORD, is_active=True, display_name=""):
    """直接在库里造用户（用来覆盖 is_active=False 这类注册接口造不出来的状态）。"""
    with app.app_context():
        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            display_name=display_name,
            is_active=is_active,
        )
        _db.session.add(user)
        _db.session.commit()
        return user.id


def _next_param(location: str):
    """从 302 的 Location 里取 next 参数（不依赖 URL 编码细节）。"""
    parts = urlsplit(location)
    values = parse_qs(parts.query).get("next")
    return parts.path, (values[0] if values else None)


# ---------------------------------------------------------------- 注册


def test_register_success_redirects_home_and_account_works(app, client):
    """注册成功：302 回首页、直接登录；同一套凭据之后还能再登录。"""
    response = _register(client, display_name="爱丽丝")
    assert response.status_code == 302
    assert response.headers["Location"] == "/"

    with app.app_context():
        user = User.query.filter_by(username=USERNAME).one()
        assert user.password_hash != PASSWORD
        assert user.password_hash.startswith(("scrypt:", "pbkdf2:", "argon2"))
        assert user.display_name == "爱丽丝"
        assert user.is_active is True

    assert client.get("/").status_code == 200

    client.post("/logout")
    again = _login(client)
    assert again.status_code == 302
    assert again.headers["Location"] == "/"


def test_register_duplicate_username_rerenders_with_danger(app, client):
    """重名：HTTP 200 重渲染，页面含 danger 提示，库里仍只有一条。"""
    _register(client)
    client.post("/logout")

    response = _register(client, display_name="第二个")
    assert response.status_code == 200
    html = _text(response)
    assert "用户名已被占用" in html
    assert "danger" in html

    with app.app_context():
        assert User.query.filter_by(username=USERNAME).count() == 1


def test_register_short_password_rejected(app, client):
    """密码不足 8 位：拒绝、不落库、页面含 danger。"""
    response = _register(client, password="1234567", password2="1234567")
    assert response.status_code == 200
    html = _text(response)
    assert "密码至少 8 位" in html
    assert "danger" in html
    with app.app_context():
        assert User.query.count() == 0


def test_register_password_equal_to_username_rejected(app, client):
    """密码与用户名相同：拒绝（即使长度足够）。"""
    response = _register(
        client, username="abcdefgh", password="abcdefgh", password2="abcdefgh"
    )
    assert response.status_code == 200
    assert "密码不能与用户名相同" in _text(response)
    with app.app_context():
        assert User.query.count() == 0


def test_register_password_mismatch_rejected(app, client):
    """两次密码不一致：拒绝。"""
    response = _register(client, password=PASSWORD, password2=PASSWORD + "x")
    assert response.status_code == 200
    assert "两次输入的密码不一致" in _text(response)
    with app.app_context():
        assert User.query.count() == 0


def test_register_forms_carry_csrf_token(client):
    """注册页与登录页的表单都带 csrf_token 隐藏域（缺了 CSRFProtect 会 400）。"""
    for path in ("/register", "/login"):
        html = _text(client.get(path))
        assert 'name="csrf_token"' in html, f"{path} 缺 csrf_token"


# ---------------------------------------------------------------- 登录


def test_login_success_writes_permanent_session(app, client):
    """登录成功：302 首页、session 有 user_id 且为永久会话、last_login_at 落库。"""
    _create_user(app)
    response = _login(client)
    assert response.status_code == 302
    assert response.headers["Location"] == "/"

    with client.session_transaction() as sess:
        assert sess.get("user_id") is not None
        assert sess.permanent is True

    with app.app_context():
        user = User.query.filter_by(username=USERNAME).one()
        assert user.last_login_at is not None

    assert client.get("/").status_code == 200


def test_login_wrong_password_uses_uniform_message(app, client):
    """密码错误与用户不存在给出完全相同的提示，且都不写 session。"""
    _create_user(app)

    wrong_password = _login(client, password="wrong-password")
    assert wrong_password.status_code == 200
    wrong_html = _text(wrong_password)
    assert "用户名或密码不正确" in wrong_html

    unknown_user = _login(client, username="nobody-here")
    assert unknown_user.status_code == 200
    unknown_html = _text(unknown_user)
    assert "用户名或密码不正确" in unknown_html

    # 两条失败路径的提示文案一致，不泄露账号是否存在
    assert "用户名不存在" not in wrong_html
    assert "用户名不存在" not in unknown_html

    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_login_inactive_user_treated_as_failure(app, client):
    """is_active=False：即使密码正确也按失败处理，提示同一条。"""
    _create_user(app, is_active=False)
    response = _login(client)
    assert response.status_code == 200
    assert "用户名或密码不正确" in _text(response)
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_login_rate_limited_after_five_failures(app, client):
    """同一 username 60 秒内失败 5 次后，第 6 次即使密码正确也按失败返回。"""
    _create_user(app)

    for _ in range(LOGIN_FAILURE_LIMIT):
        failed = _login(client, password="wrong-password")
        assert failed.status_code == 200
        assert "用户名或密码不正确" in _text(failed)

    blocked = _login(client)  # 密码正确，但已被限流
    assert blocked.status_code == 200
    assert "用户名或密码不正确" in _text(blocked)
    with client.session_transaction() as sess:
        assert "user_id" not in sess

    # 限流按 username 记账：另一个用户不受影响
    _create_user(app, username="bob")
    assert _login(client, username="bob").status_code == 302


def test_login_success_clears_failure_counter(app, client):
    """成功登录后失败计数清零：再错几次仍不会立刻被限流。"""
    _create_user(app)
    for _ in range(LOGIN_FAILURE_LIMIT - 1):
        _login(client, password="wrong-password")

    assert _login(client).status_code == 302
    client.post("/logout")

    for _ in range(LOGIN_FAILURE_LIMIT - 1):
        assert _login(client, password="wrong-password").status_code == 200
    assert _login(client).status_code == 302  # 计数已清零，不会到第 6 次才放行


# ---------------------------------------------------------------- 登出与会话


def test_logout_clears_session(auth_client):
    """登出后 session 里没有 user_id，并 302 回登录页。"""
    response = auth_client.post("/logout", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"
    with auth_client.session_transaction() as sess:
        assert "user_id" not in sess


def test_forged_session_for_missing_user_is_ignored(app, client):
    """会话里指向不存在的用户：按未登录处理并送去登录页，不抛错、不渲染首页。

    #15 起 / 需要登录，所以断言从「200 首页」改为「302 → /login」；
    「伪造 user_id 不生效」的语义不变，并且额外证明没有渲染首页正文。
    """
    with client.session_transaction() as sess:
        sess["user_id"] = 424242
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login"), response.headers["Location"]
    assert response.status_code != 200
    assert "本月" not in response.get_data(as_text=True)
    with client.session_transaction() as sess:
        assert "user_id" not in sess


# ---------------------------------------------------------------- login_required 与 next


def test_login_required_redirects_with_next(app, client):
    """未登录访问受保护视图（本轮只有 auth.logout）→ 302 /login?next=<原路径>。"""
    response = client.post("/logout")
    assert response.status_code == 302
    path, next_value = _next_param(response.headers["Location"])
    assert path == "/login"
    assert next_value == "/logout"


def test_login_required_preserves_query_string(app, client):
    """受保护视图带查询串时，next 要带上查询串（request.full_path）。"""
    from app.auth import login_required

    @app.route("/_probe")
    @login_required
    def _probe():  # pragma: no cover - 只用于验证装饰器
        return "ok"

    response = client.get("/_probe?x=1")
    assert response.status_code == 302
    path, next_value = _next_param(response.headers["Location"])
    assert path == "/login"
    assert next_value == "/_probe?x=1"


def test_login_next_redirects_back_inside_site(app, client):
    """登录页带上 next，登录成功后回到该站内路径。"""
    _create_user(app)
    page = client.get("/login?next=/categories")
    assert page.status_code == 200
    assert 'name="next" value="/categories"' in _text(page)

    response = _login(client, next_value="/categories")
    assert response.status_code == 302
    assert response.headers["Location"] == "/categories"


def test_login_next_keeps_query_string(app, client):
    """next 里的查询串要原样保留。"""
    _create_user(app)
    target = "/products?category_id=2"
    response = _login(client, next_value=target)
    assert response.status_code == 302
    assert response.headers["Location"] == target


@pytest.mark.parametrize(
    "bad_next",
    [
        "//evil.com",
        "///evil.com",
        "https://evil.com",
        "http://evil.com/login",
        "/\\evil.com",
        "evil.com",
        "javascript:alert(1)",
    ],
)
def test_login_external_next_falls_back_to_index(app, client, bad_next):
    """外域或非站内相对路径的 next 一律回首页（防开放重定向）。"""
    _create_user(app)
    response = _login(client, next_value=bad_next)
    assert response.status_code == 302
    assert response.headers["Location"] == "/"


def test_safe_next_target_unit():
    """safe_next_target 的边界：只放行站内相对路径。"""
    assert safe_next_target("/categories") == "/categories"
    assert safe_next_target("/lists/1?tab=items") == "/lists/1?tab=items"
    for bad in (
        None,
        "",
        "//evil.com",
        "///evil.com",
        "https://evil.com",
        "http://evil.com",
        "/\\evil.com",
        "evil.com",
        "javascript:alert(1)",
    ):
        assert safe_next_target(bad) is None, f"{bad!r} 应被拒绝"


# ---------------------------------------------------------------- 已登录访问认证页


def test_logged_in_user_cannot_open_login_or_register(auth_client):
    """已登录访问 /login、/register → 302 首页。"""
    for path in ("/login", "/register"):
        response = auth_client.get(path)
        assert response.status_code == 302, f"{path} -> {response.status_code}"
        assert response.headers["Location"] == "/"


def test_nav_shows_current_user_and_logout(auth_client):
    """导航右侧显示昵称或用户名 + 登出表单（POST + csrf_token）。"""
    html = _text(auth_client.get("/"))
    assert USERNAME in html
    assert 'action="/logout"' in html
    assert 'method="post"' in html
    assert 'name="csrf_token"' in html


def test_nav_shows_login_links_for_anonymous(client):
    """未登录：(a) 首页被送去登录页；(b) 登录页导航里有登录/注册入口。

    #15 起匿名拿不到首页正文，登录/注册入口只剩登录页可见，所以拆成两条断言；
    语义等价且更强（多验了未登录被拦下这一层）。
    """
    home = client.get("/")
    assert home.status_code == 302
    assert home.headers["Location"].startswith("/login?next="), home.headers["Location"]

    page = client.get("/login")
    assert page.status_code == 200
    html = _text(page)
    assert 'href="/login"' in html
    assert 'href="/register"' in html
    assert "登录" in html and "注册" in html

