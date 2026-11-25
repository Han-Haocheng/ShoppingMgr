"""数据模型（SPEC 第 3 节）。金额一律 Decimal + Numeric(10,2)。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

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


class Category(db.Model):
    """品类。"""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    note: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=_now)

    products: Mapped[list["Product"]] = relationship(
        back_populates="category",
        order_by="Product.id",
    )

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<Category id={self.id} name={self.name!r}>"


class Product(db.Model):
    """商品。"""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True
    )
    unit: Mapped[str] = mapped_column(String(10), nullable=False, default="件")
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    barcode: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    note: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=_now)

    category: Mapped["Category | None"] = relationship(back_populates="products")

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<Product id={self.id} name={self.name!r}>"


class ShoppingList(db.Model):
    """购物清单。status: draft | done。"""

    __tablename__ = "shopping_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    note: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=_now)

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
        return f"<ShoppingList id={self.id} name={self.name!r} status={self.status!r}>"


class ShoppingItem(db.Model):
    """清单条目；name 是下单名称快照，product 可能为空。"""

    __tablename__ = "shopping_items"

    id: Mapped[int] = mapped_column(primary_key=True)
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

    list: Mapped["ShoppingList"] = relationship(back_populates="items")
    product: Mapped["Product | None"] = relationship()

    @property
    def subtotal(self) -> Decimal:
        """小计 = 数量 × 单价，保留两位。"""
        qty = self.qty if self.qty is not None else Decimal("0.00")
        unit_price = self.unit_price if self.unit_price is not None else Decimal("0.00")
        return _money(qty * unit_price)

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<ShoppingItem id={self.id} name={self.name!r} done={self.done}>"


class Expense(db.Model):
    """消费记录。"""

    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
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

    category: Mapped["Category | None"] = relationship()
    product: Mapped["Product | None"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<Expense id={self.id} spent_on={self.spent_on} amount={self.amount}>"
