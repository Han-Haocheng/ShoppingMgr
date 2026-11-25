"""pytest 夹具（SPEC 第 8 节）：内存 SQLite + Flask test client，禁网络。"""

from __future__ import annotations

import pytest

from app import create_app
from app.extensions import db as _db


class TestConfig:
    """测试配置：内存库（Flask-SQLAlchemy 对 sqlite 内存库自动用 StaticPool）。"""

    TESTING = True
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False  # 冒烟用例不处理 token；CSRF 行为由 tests/test_csrf.py 单独验


@pytest.fixture()
def app():
    """每个用例一份干净的应用与库。"""
    application = create_app(TestConfig)
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    """Flask 测试客户端。"""
    return app.test_client()

# ---------------------------------------------------------------- 认证夹具（#14 追加）
# 仅追加，不改上面的既有 fixture 与既有用例（SPEC 第 11 节）。

AUTH_PASSWORD = "password123"
AUTH_USERNAME = "alice"
SECOND_USERNAME = "bob"


def _seed_user(application, username, password=AUTH_PASSWORD, display_name="", is_active=True) -> int:
    """在应用上下文里建一个用户并返回 id（同名已存在则复用）。"""
    from werkzeug.security import generate_password_hash

    from app.models import User

    with application.app_context():
        existing = User.query.filter_by(username=username).first()
        if existing is not None:
            return existing.id
        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            display_name=display_name,
            is_active=is_active,
        )
        _db.session.add(user)
        _db.session.commit()
        return user.id


def _sign_in(client, username, password=AUTH_PASSWORD):
    """用测试客户端走一次真实登录 POST（不跟随跳转）。"""
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


@pytest.fixture()
def auth_client(app):
    """已登录客户端：用户 alice（SPEC 第 11 节）。"""
    client = app.test_client()
    _seed_user(app, AUTH_USERNAME)
    response = _sign_in(client, AUTH_USERNAME)
    assert response.status_code == 302, f"登录失败：{response.status_code}"
    return client


@pytest.fixture()
def second_client(app):
    """第二个用户的已登录客户端：用户 bob（SPEC 第 11 节，供归属隔离用例使用）。"""
    client = app.test_client()
    _seed_user(app, SECOND_USERNAME)
    response = _sign_in(client, SECOND_USERNAME)
    assert response.status_code == 302, f"登录失败：{response.status_code}"
    return client

