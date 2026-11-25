"""应用工厂（SPEC 第 4 节）：配置、扩展、5 个蓝图、404 与 CLI 都在这里装配。"""

from __future__ import annotations

import os
from urllib.parse import urlsplit

import click
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError

from .config import (
    DEV_SECRET_KEY_WARNING,
    Config,
    debug_enabled_by_env,
    resolve_secret_key,
)
from .extensions import csrf, db, migrate
from .utils import fmt_money


def create_app(config_object=None) -> Flask:
    """创建 Flask 应用；config_object 可为配置类或 dict（测试用）。"""
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_object(Config)
    if config_object is not None:
        if isinstance(config_object, dict):
            app.config.from_mapping(config_object)
        else:
            app.config.from_object(config_object)

    # SECRET_KEY 必填校验：debug 关闭且没配置就直接失败（此时还没建目录、没连库）。
    # Config.SECRET_KEY 是 import 期的环境快照，这里再读一次环境变量兜住「import 之后才设置」的场景。
    secret_key, used_dev_secret_key = resolve_secret_key(
        app.config.get("SECRET_KEY") or os.environ.get("SECRET_KEY"),
        debug=debug_enabled_by_env() or bool(app.config.get("DEBUG")),
    )
    app.config["SECRET_KEY"] = secret_key
    if used_dev_secret_key:
        app.logger.warning(DEV_SECRET_KEY_WARNING)

    # instance/shop.db 的父目录（.gitignore 已忽略 instance/）
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    from . import models  # noqa: F401  先注册模型，create_all 才能见全表
    from .blueprints import ALL_BLUEPRINTS

    for blueprint in ALL_BLUEPRINTS:
        app.register_blueprint(blueprint)

    _register_error_handlers(app)
    _register_cli(app)

    # 模板里可直接用 {{ value|money }} 显示 ¥xx.xx（附加便利，非 SPEC 要求）
    app.add_template_filter(fmt_money, "money")
    return app


def _safe_redirect_target() -> str:
    """CSRF 失败后的跳转目标：只有同源 referrer 才回跳，其余一律回首页。

    同源判定：urllib.parse.urlsplit 解析 request.referrer，scheme 属于 http/https
    且 netloc 与 request.host 完全相等；外域、相对路径、非 http(s) 都回首页。
    """
    referrer = request.referrer
    if referrer:
        parts = urlsplit(referrer)
        if parts.scheme in ("http", "https") and parts.netloc == request.host:
            return referrer
    return url_for("main.index")


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(404)
    def not_found(error):  # pragma: no cover - 由前端模板承载
        return render_template("404.html"), 404

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        """CSRF 校验失败：提示后回到同源来源页（无来源或跨源回首页）；只 flash+redirect，不再触发 CSRF。"""
        flash("表单已过期，请刷新页面重试", "danger")
        return redirect(_safe_redirect_target())


def _register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db_command() -> None:
        """重建表结构并写入示例数据。"""
        from .utils import seed_sample_data

        db.drop_all()
        db.create_all()
        stats = seed_sample_data()
        if stats["created"]:
            click.echo(
                "数据库已重建：品类 {categories} / 商品 {products} / 清单 {lists} "
                "/ 条目 {items} / 消费 {expenses}".format(**stats)
            )
        else:
            click.echo("数据库已重建（示例数据已存在，未重复写入）。")

    @app.cli.command("seed-db")
    def seed_db_command() -> None:
        """只写入示例数据，不改表结构。"""
        from .utils import seed_sample_data

        stats = seed_sample_data()
        if stats["created"]:
            click.echo(
                "示例数据已写入：品类 {categories} / 商品 {products} / 清单 {lists} "
                "/ 条目 {items} / 消费 {expenses}".format(**stats)
            )
        else:
            click.echo("库中已有数据，跳过写入。")
