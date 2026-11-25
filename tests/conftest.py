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
