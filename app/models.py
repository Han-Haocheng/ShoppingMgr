"""数据模型（SPEC 第 3 节）。金额一律 Decimal + Numeric(10,2)。

v2 起 5 张业务表都带 user_id（FK users.id、NOT NULL、带索引）：所有查询按它过滤，
跨用户的 id 在视图层统一收敛成 404（见 app/utils.py 的 owned_or_404）。
唯一性也随之下沉到「同用户内」：categories 是 (user_id, name)，products 是
(user_id, barcode)（barcode 空输入存 NULL，SQLite 的 UNIQUE 允许并列 NULL）。
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db

TWO_PLACES = Decimal("0.01")


def _now() -> datetime:
    """写入时间戳（本地时间，naive）。"""
    return datetime.now()


def _money(value) -> Decimal:
    """把 None / int / str / Decimal 统一收敛成两位小数的 Decimal。"""
    if value is None:
        return Decimal("0.00")
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class User(db.Model):
    """用户（SPEC 第 3、4 节）：密码只存 werkzeug 哈希，原始密码不落库。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=_now)

    # 反向关系（SPEC 第 3 节「User 侧反向关系」）：只作导航，不设级联删除，
    # 删用户不应悄悄带走业务数据（真要清理走迁移或手工 SQL）。
    categories: Mapped[list["Category"]] = relationship(
        back_populates="user", order_by="Category.id"
    )
    products: Mapped[list["Product"]] = relationship(
        back_populates="user", order_by="Product.id"
    )
    shopping_lists: Mapped[list["ShoppingList"]] = relationship(
        back_populates="user", order_by="ShoppingList.id"
    )
    shopping_items: Mapped[list["ShoppingItem"]] = relationship(
        back_populates="user", order_by="ShoppingItem.id"
    )
    expenses: Mapped[list["Expense"]] = relationship(
        back_populates="user", order_by="Expense.id"
    )

    def set_password(self, raw_password: str) -> None:
        """写入密码哈希（werkzeug.security，随 Flask 安装，不引入新依赖）。"""
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """校验原始密码；哈希串本身不匹配时返回 False，不抛异常。"""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, raw_password)

    @property
    def display(self) -> str:
        """导航栏展示名：优先昵称，缺省回落到用户名。"""
        return self.display_name or self.username

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<User id={self.id} username={self.username!r} active={self.is_active}>"


class Category(db.Model):
    """品类。名称只在同一用户内唯一（SPEC 第 3 节）。"""

    __tablename__ = "categories"
    # 取代 v1 的全局 UNIQUE(name)：两个用户可以有同名品类
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_categories_user_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    note: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=_now)

    user: Mapped["User"] = relationship(back_populates="categories")
    products: Mapped[list["Product"]] = relationship(
        back_populates="category",
        order_by="Product.id",
    )

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<Category id={self.id} user_id={self.user_id} name={self.name!r}>"


class Product(db.Model):
    """商品。条码同用户内唯一，空值存 NULL（SPEC 第 3 节）。"""

    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("user_id", "barcode", name="uq_products_user_barcode"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True
    )
    unit: Mapped[str] = mapped_column(String(10), nullable=False, default="件")
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    # v2：可空，空输入存 NULL（None），这样 (user_id, barcode) 唯一约束不会互相撞车
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    note: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=_now)

    user: Mapped["User"] = relationship(back_populates="products")
    category: Mapped["Category | None"] = relationship(back_populates="products")

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<Product id={self.id} user_id={self.user_id} name={self.name!r}>"


class ShoppingList(db.Model):
    """购物清单。status: draft | done。"""

    __tablename__ = "shopping_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    note: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=_now)

    user: Mapped["User"] = relationship(back_populates="shopping_lists")
    items: Mapped[list["ShoppingItem"]] = relationship(
        back_populates="list",
        cascade="all, delete-orphan",
        order_by="ShoppingItem.id",
    )

    @property
    def total(self) -> Decimal:
        """各子项 subtotal 之和；空清单返回 Decimal('0.00')。"""
        if not self.items:
            return Decimal("0.00")
        return _money(sum((item.subtotal for item in self.items), Decimal("0.00")))

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return (
            f"<ShoppingList id={self.id} user_id={self.user_id} "
            f"name={self.name!r} status={self.status!r}>"
        )


class ShoppingItem(db.Model):
    """清单条目；name 是下单名称快照，product 可能为空。"""

    __tablename__ = "shopping_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    list_id: Mapped[int] = mapped_column(
        ForeignKey("shopping_lists.id"), nullable=False
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    qty: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("1.00")
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    done: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=_now)

    user: Mapped["User"] = relationship(back_populates="shopping_items")
    list: Mapped["ShoppingList"] = relationship(back_populates="items")
    product: Mapped["Product | None"] = relationship()

    @property
    def subtotal(self) -> Decimal:
        """小计 = 数量 × 单价，保留两位。"""
        qty = self.qty if self.qty is not None else Decimal("0.00")
        unit_price = self.unit_price if self.unit_price is not None else Decimal("0.00")
        return _money(qty * unit_price)

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<ShoppingItem id={self.id} user_id={self.user_id} name={self.name!r} done={self.done}>"


class Expense(db.Model):
    """消费记录。"""

    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    spent_on: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id"), nullable=True
    )
    note: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=_now)

    user: Mapped["User"] = relationship(back_populates="expenses")
    category: Mapped["Category | None"] = relationship()
    product: Mapped["Product | None"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<Expense id={self.id} user_id={self.user_id} spent_on={self.spent_on} amount={self.amount}>"
