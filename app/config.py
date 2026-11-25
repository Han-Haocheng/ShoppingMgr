"""应用配置：只暴露少量可由环境变量覆盖的项，其余按 SPEC 固定。"""

from __future__ import annotations

import os
from pathlib import Path

# 项目根目录（/mnt/d/Project/ShoppingMgr）
BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """默认配置：数据库固定为 SQLite 的 instance/shop.db。"""

    SECRET_KEY = os.environ.get("SECRET_KEY", "shoppingmgr-dev-secret")

    # 相对路径由 Flask-SQLAlchemy 解析到 app.instance_path，
    # 即项目根下的 instance/shop.db（SPEC 第 1 节）。
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///shop.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
