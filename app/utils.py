"""解析、格式化、月份区间与示例数据（SPEC 第 4、6 节）。

金额解析集中在这里：调用方捕获 ValueError，走「flash danger + 重渲染同模板」分支。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import g

from .extensions import db

TWO_PLACES = Decimal("0.01")
ZERO_MONEY = Decimal("0.00")
MONTH_FORMAT = "%Y-%m"
DATE_FORMAT = "%Y-%m-%d"


# ---------------------------------------------------------------- 解析


def to_decimal(value, default: Decimal = ZERO_MONEY) -> Decimal:
    """把数据库返回值（可能为 None / int / float / Decimal）收敛为两位小数 Decimal。"""
    if value is None:
        return default
    if isinstance(value, Decimal):
        amount = value
    else:
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return default
    if not amount.is_finite():
        return default
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def parse_decimal(raw, default: Decimal | None = None, minimum=ZERO_MONEY) -> Decimal | None:
    """表单文本 -> 两位小数 Decimal。

    - 空字符串 / None 返回 default（未传默认值时即 None，由调用方判空）。
    - 非数字、非有限值、小于 minimum（默认 0，即负数）抛 ValueError。
    """
    if raw is None:
        return default
    text = str(raw).strip()
    if not text:
        return default
    cleaned = text.replace("¥", "").replace("￥", "").replace(",", "").replace("，", "")
    try:
        value = Decimal(cleaned)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"“{text}”不是有效数字") from exc
    if not value.is_finite():
        raise ValueError(f"“{text}”不是有效数字")
    if minimum is not None and value < minimum:
        if minimum == ZERO_MONEY:
            raise ValueError("数值不能为负数")
        raise ValueError(f"数值不能小于 {minimum}")
    try:
        return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError(f"“{text}”超出可表示范围") from exc


def parse_date(raw, default: date | None = None) -> date | None:
    """表单日期（YYYY-MM-DD）-> date；空值返回 default，非法抛 ValueError。"""
    if raw is None:
        return default
    text = str(raw).strip()
    if not text:
        return default
    try:
        return datetime.strptime(text, DATE_FORMAT).date()
    except ValueError as exc:
        raise ValueError(f"“{text}”不是有效日期（应为 YYYY-MM-DD）") from exc


def parse_id(raw, default: int | None = None) -> int | None:
    """表单主键文本 -> 正整数；空值返回 default，非法抛 ValueError。"""
    if raw is None:
        return default
    text = str(raw).strip()
    if not text:
        return default
    try:
        value = int(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"“{text}”不是有效编号") from exc
    if value <= 0:
        raise ValueError(f"“{text}”不是有效编号")
    return value


def parse_month(raw, default_to_current: bool = True) -> str | None:
    """'YYYY-MM' -> 'YYYY-MM'；空值返回当前月（或 None），非法抛 ValueError。"""
    text = "" if raw is None else str(raw).strip()
    if not text:
        return current_month() if default_to_current else None
    try:
        parsed = datetime.strptime(text, MONTH_FORMAT)
    except ValueError as exc:
        raise ValueError(f"“{text}”不是有效月份（应为 YYYY-MM）") from exc
    return parsed.strftime(MONTH_FORMAT)


# ---------------------------------------------------------------- 归属过滤


def owned_or_404(model, **criteria):
    """按 id + 当前用户取对象；不存在或不属于当前用户一律 404（SPEC 第 5 节）。

    跨用户访问按「不存在」处理，返回 404 而不是 403，避免泄露资源是否存在。
    所有按主键取业务对象的视图都必须走这里（等价于
    `filter_by(id=..., user_id=g.user.id).first_or_404()`）。
    """
    return db.session.query(model).filter_by(user_id=g.user.id, **criteria).first_or_404()


# ---------------------------------------------------------------- 月份 / 展示


def current_month() -> str:
    """当前月，形如 2026-11。"""
    return date.today().strftime(MONTH_FORMAT)


def month_range(month: str) -> tuple[date, date]:
    """返回 [首日, 次月首日) 的左闭右开区间。"""
    start = datetime.strptime(month, MONTH_FORMAT).date().replace(day=1)
    if start.month == 12:
        next_start = date(start.year + 1, 1, 1)
    else:
        next_start = date(start.year, start.month + 1, 1)
    return start, next_start


def fmt_money(value) -> str:
    """金额显示：¥ + 两位小数。"""
    return "¥" + f"{to_decimal(value):.2f}"


def copy_instance(obj, **values):
    """复制一个未入库的同类型实例并覆盖字段，用于校验失败时回填表单。"""
    data = {column.key: getattr(obj, column.key) for column in obj.__table__.columns}
    data.update(values)
    return type(obj)(**data)


# ---------------------------------------------------------------- 示例数据


# 本地演示账号（README「首次使用」已注明：仅本地演示用，上线前必须删除或改密）
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo1234"
DEMO_DISPLAY_NAME = "演示用户"


def ensure_demo_user():
    """确保演示账号存在并返回它；种子数据全部归属到该用户。"""
    from .models import User

    user = db.session.query(User).filter_by(username=DEMO_USERNAME).first()
    if user is not None:
        return user
    user = User(username=DEMO_USERNAME, display_name=DEMO_DISPLAY_NAME)
    user.set_password(DEMO_PASSWORD)  # 只存哈希，原始密码不落库
    db.session.add(user)
    db.session.commit()
    return user


def sample_data_exists(user_id: int) -> bool:
    """该用户名下是否已有品类数据（seed-db 防重复插入用，按用户隔离）。"""
    from .models import Category

    return (
        db.session.query(Category.id).filter_by(user_id=user_id).limit(1).first()
        is not None
    )


def seed_sample_data() -> dict:
    """写入示例数据（全部归属 demo 用户）：5 品类 / 8 商品 / 1 草稿清单（3 条目）/ 6 笔本月消费。"""
    from .models import Category, Expense, Product, ShoppingItem, ShoppingList

    user = ensure_demo_user()
    if sample_data_exists(user.id):
        return {
            "created": False,
            "username": user.username,
            "categories": 0,
            "products": 0,
            "lists": 0,
            "items": 0,
            "expenses": 0,
        }

    categories: dict[str, Category] = {}
    for name, note in (
        ("蔬果", "生鲜蔬果"),
        ("零食", "休闲零食"),
        ("日用", "日用百货"),
        ("乳饮", "牛奶酸奶"),
        ("个护", "个人护理"),
    ):
        category = Category(name=name, note=note, user_id=user.id)
        db.session.add(category)
        categories[name] = category
    db.session.flush()

    products: dict[str, Product] = {}
    for name, category_name, unit, price in (
        ("苹果", "蔬果", "件", Decimal("6.50")),
        ("香蕉", "蔬果", "把", Decimal("5.20")),
        ("薯片", "零食", "袋", Decimal("8.90")),
        ("饼干", "零食", "盒", Decimal("12.00")),
        ("抽纸", "日用", "包", Decimal("9.90")),
        ("洗洁精", "日用", "瓶", Decimal("15.80")),
        ("牛奶", "乳饮", "盒", Decimal("3.50")),
        ("酸奶", "乳饮", "杯", Decimal("4.20")),
    ):
        product = Product(
            user_id=user.id,
            name=name,
            category_id=categories[category_name].id,
            unit=unit,
            price=price,
            barcode=None,  # 空条码存 NULL：(user_id, barcode) 唯一约束才不会撞车
            note="",
            is_active=True,
        )
        db.session.add(product)
        products[name] = product
    db.session.flush()

    shopping_list = ShoppingList(
        user_id=user.id, name="本周采购", note="草稿示例清单", status="draft"
    )
    db.session.add(shopping_list)
    db.session.flush()

    item_seed = (
        ("苹果", Decimal("2.00"), Decimal("6.50")),
        ("牛奶", Decimal("4.00"), Decimal("3.50")),
        ("抽纸", Decimal("1.00"), Decimal("9.90")),
    )
    for name, qty, unit_price in item_seed:
        db.session.add(
            ShoppingItem(
                user_id=user.id,
                list_id=shopping_list.id,
                product_id=products[name].id,
                name=name,
                qty=qty,
                unit_price=unit_price,
                done=False,
            )
        )

    first_day = date.today().replace(day=1)
    expense_seed = (
        ("苹果", "蔬果", Decimal("6.50"), 0, "早餐水果"),
        ("牛奶", "乳饮", Decimal("3.50"), 1, ""),
        ("薯片", "零食", Decimal("8.90"), 2, "下午茶"),
        ("抽纸", "日用", Decimal("9.90"), 3, "日用补给"),
        ("洗洁精", "日用", Decimal("15.80"), 4, "厨房"),
        ("酸奶", "乳饮", Decimal("4.20"), 5, "夜宵"),
    )
    for product_name, category_name, amount, day_offset, note in expense_seed:
        db.session.add(
            Expense(
                user_id=user.id,
                spent_on=first_day + timedelta(days=day_offset),
                amount=amount,
                category_id=categories[category_name].id,
                product_id=products[product_name].id,
                note=note,
            )
        )

    db.session.commit()
    return {
        "created": True,
        "username": user.username,
        "categories": len(categories),
        "products": len(products),
        "lists": 1,
        "items": len(item_seed),
        "expenses": len(expense_seed),
    }
