"""Flask 扩展实例：在应用工厂里 init_app，避免循环导入。"""

from __future__ import annotations

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 声明式基类（SPEC 第 3 节要求 Mapped/mapped_column）。"""


db = SQLAlchemy(model_class=Base)
migrate = Migrate()
csrf = CSRFProtect()
