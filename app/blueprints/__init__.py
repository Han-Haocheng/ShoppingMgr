"""蓝图集合（SPEC 第 4 节）：5 个蓝图，均无 url_prefix。"""

from __future__ import annotations

from .categories import bp as categories_bp
from .expenses import bp as expenses_bp
from .lists import bp as lists_bp
from .main import bp as main_bp
from .products import bp as products_bp

ALL_BLUEPRINTS = (
    main_bp,
    categories_bp,
    products_bp,
    lists_bp,
    expenses_bp,
)

__all__ = [
    "ALL_BLUEPRINTS",
    "main_bp",
    "categories_bp",
    "products_bp",
    "lists_bp",
    "expenses_bp",
]
