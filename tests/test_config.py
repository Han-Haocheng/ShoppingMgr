"""SECRET_KEY 必填与 FLASK_DEBUG 默认关闭的用例（安全默认值）。"""

from __future__ import annotations

import logging

import pytest

from app import create_app
from app.config import Config, debug_enabled_by_env


class LocalConfig(Config):
    """独立配置子类：内存库 + 配置类自带 SECRET_KEY。"""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SECRET_KEY = "from-config-class"


class NoSecretConfig(Config):
    """独立配置子类：内存库，但不提供 SECRET_KEY。"""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"


@pytest.fixture()
def clean_env(monkeypatch):
    """清掉两个相关环境变量，避免本机环境或其它用例影响判定。"""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    return monkeypatch


def test_missing_secret_key_raises_runtime_error(clean_env):
    """debug 关闭且没有 SECRET_KEY：create_app 抛 RuntimeError，消息可直接照做。"""
    with pytest.raises(RuntimeError) as excinfo:
        create_app(NoSecretConfig)

    message = str(excinfo.value)
    assert "SECRET_KEY" in message
    assert ".env.example" in message
    assert "FLASK_DEBUG=1" in message


def test_secret_key_from_env_creates_app(clean_env):
    """提供 SECRET_KEY（环境变量）时正常创建，并落到 app.config。"""
    clean_env.setenv("SECRET_KEY", "unit-test-secret")

    app = create_app(NoSecretConfig)

    assert app.config["SECRET_KEY"] == "unit-test-secret"


def test_secret_key_from_config_object_creates_app(clean_env):
    """提供 SECRET_KEY（配置类）时正常创建；环境变量为空也不报错。"""
    app = create_app(LocalConfig)

    assert app.config["SECRET_KEY"] == "from-config-class"


def test_debug_without_secret_key_creates_app_with_warning(clean_env, caplog):
    """debug 开启且没有 SECRET_KEY：允许固定开发密钥，并打一条警告。"""
    clean_env.setenv("FLASK_DEBUG", "1")

    with caplog.at_level(logging.WARNING):
        app = create_app(NoSecretConfig)

    secret = app.config["SECRET_KEY"]
    assert isinstance(secret, str) and secret
    assert "开发密钥" in caplog.text
    assert "生产" in caplog.text


def test_debug_flag_requires_explicit_true_values(clean_env):
    """FLASK_DEBUG 只有 1/true/yes 才算开启，其余（含未设置）都是关闭。"""

    def enabled(value: str | None) -> bool:
        if value is None:
            clean_env.delenv("FLASK_DEBUG", raising=False)
        else:
            clean_env.setenv("FLASK_DEBUG", value)
        return debug_enabled_by_env()

    assert enabled("1") is True
    assert enabled("true") is True
    assert enabled("TRUE") is True
    assert enabled(" yes ") is True
    assert enabled("0") is False
    assert enabled("false") is False
    assert enabled("no") is False
    assert enabled("") is False
    assert enabled(None) is False
