"""CSRF 防护测试（SPEC 第 6 节）。

**不复用** tests/conftest.py 里关闭了 CSRF 的 fixture：这里用启用 CSRF 的临时 app，
验证「无 token 被拒、页面 token 可用」两条独立断言。
"""

from __future__ import annotations

import re

import pytest

from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db as _db
from app.models import Category, User


class CsrfEnabledConfig:
    """与测试夹具同构，但显式打开 CSRF。"""

    TESTING = True
    SECRET_KEY = "csrf-test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True


TOKEN_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture()
def csrf_app():
    """启用 CSRF 的独立应用（内存库）。

    注意：**不在 yield 期间持有 app context**。Flask-WTF 把本次请求的 token 缓存在
    g 上，而请求上下文会复用已存在的 app context；外层一直挂着 app context 会让 g
    跨请求泄漏，页面上的 token 与 session 里的 token 对不上，看起来像 CSRF 失败。
    真实运行时不存在这种外层上下文，所以夹具按生产形态来。
    """
    application = create_app(CsrfEnabledConfig)
    with application.app_context():
        _db.create_all()
    yield application
    with application.app_context():
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def csrf_client(csrf_app):
    """启用 CSRF 的测试客户端。"""
    return csrf_app.test_client()


def _page_token(client, path: str = "/categories/new") -> str:
    """从 GET 页面里解析 csrf_token 隐藏域的值。"""
    html = client.get(path).get_data(as_text=True)
    match = TOKEN_RE.search(html)
    assert match is not None, f"{path} 页面未渲染 csrf_token 隐藏域"
    return match.group(1)


def test_post_without_token_is_rejected(csrf_app, csrf_client):
    """不带 token 提交 POST /categories/new 被拒（400 或重定向），且不落库。"""
    response = csrf_client.post(
        "/categories/new",
        data={"name": "跨站品类", "note": "无 token"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 400), f"未拦截，状态码 {response.status_code}"

    if response.status_code == 302:
        # 被 errorhandler(CSRFError) 接住：danger flash + 跳回来源页/首页
        with csrf_client.session_transaction() as session:
            flashes = session.get("_flashes", [])
        assert any(
            category == "danger" and "表单已过期" in message
            for category, message in flashes
        ), f"未给出血清提示：{flashes}"

    with csrf_app.app_context():
        assert Category.query.filter_by(name="跨站品类").count() == 0


def test_tampered_token_is_rejected(csrf_app, csrf_client):
    """伪造的 token 同样被拒，证明校验的是 token 值而不只是字段存在。"""
    response = csrf_client.post(
        "/categories/new",
        data={"csrf_token": "forged-token-value", "name": "伪造品类", "note": ""},
        follow_redirects=False,
    )
    assert response.status_code in (302, 400)
    with csrf_app.app_context():
        assert Category.query.filter_by(name="伪造品类").count() == 0


CSRF_USERNAME = "csrf-user"
CSRF_PASSWORD = "csrf-password-1"


def _create_user(application) -> int:
    """造一个用户：业务页 #15 起要登录，走真实链路前先有账号。"""
    with application.app_context():
        user = User(
            username=CSRF_USERNAME,
            password_hash=generate_password_hash(CSRF_PASSWORD),
            display_name="CSRF 用户",
        )
        _db.session.add(user)
        _db.session.commit()
        return user.id


def test_post_with_page_token_succeeds(csrf_app, csrf_client):
    """用页面里解析出的 token 提交则成功：302 且库里有记录。

    #15 起业务页需要登录，所以改走真实链路：登录页取 token → 登录（顺带证明
    登录表单本身受 CSRF 保护）→ 业务页取 token → 提交创建。
    """
    _create_user(csrf_app)

    login_token = _page_token(csrf_client, "/login")
    signed_in = csrf_client.post(
        "/login",
        data={
            "csrf_token": login_token,
            "username": CSRF_USERNAME,
            "password": CSRF_PASSWORD,
        },
        follow_redirects=False,
    )
    assert signed_in.status_code == 302, f"登录失败：{signed_in.status_code}"

    token = _page_token(csrf_client, "/categories/new")
    response = csrf_client.post(
        "/categories/new",
        data={"csrf_token": token, "name": "合法品类", "note": "带 token"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "categories" in response.headers["Location"]

    with csrf_app.app_context():
        saved = Category.query.filter_by(name="合法品类").one()
        assert saved.id > 0
        owner = User.query.filter_by(username=CSRF_USERNAME).one()
        assert saved.user_id == owner.id  # 顺手验归属：写操作必须落到当前用户


def test_cross_site_referrer_falls_back_to_index(csrf_app, csrf_client):
    """带外域 Referer 的无 token POST：重定向目标必须是 /，不能跟随外域地址（防开放重定向）。"""
    response = csrf_client.post(
        "/categories/new",
        data={"name": "外域引用品类", "note": ""},
        headers={"Referer": "https://evil.example/x"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/", f"被外域 Referer 带走：{response.headers['Location']}"
    assert "evil.example" not in response.headers["Location"]
    with csrf_app.app_context():
        assert Category.query.filter_by(name="外域引用品类").count() == 0


def test_same_origin_referrer_is_honoured(csrf_app, csrf_client):
    """同源 Referer 才回跳原页：http://localhost/categories → Location 指向 /categories。"""
    response = csrf_client.post(
        "/categories/new",
        data={"name": "同源引用品类", "note": ""},
        headers={"Referer": "http://localhost/categories"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/categories"), response.headers["Location"]
    with csrf_app.app_context():
        assert Category.query.filter_by(name="同源引用品类").count() == 0
