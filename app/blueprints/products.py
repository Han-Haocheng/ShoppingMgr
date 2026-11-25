"""products 蓝图：商品增删改查（SPEC 第 4、5、6 节）。"""

from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Category, Product
from ..utils import copy_instance, parse_decimal, parse_id

bp = Blueprint("products", __name__)


def _categories() -> list[Category]:
    return db.session.query(Category).order_by(Category.name.asc()).all()


def _collect(form) -> tuple[dict, list[str]]:
    """解析商品表单，返回 (字段字典, 错误列表)。"""
    errors: list[str] = []

    name = form.get("name", "").strip()
    if not name:
        errors.append("商品名称不能为空")
    elif len(name) > 80:
        errors.append("商品名称不能超过 80 个字符")

    unit = form.get("unit", "").strip() or "件"
    if len(unit) > 10:
        errors.append("单位不能超过 10 个字符")

    barcode = form.get("barcode", "").strip()
    if len(barcode) > 64:
        errors.append("条码不能超过 64 个字符")

    note = form.get("note", "").strip()
    if len(note) > 200:
        errors.append("备注不能超过 200 个字符")

    try:
        price = parse_decimal(form.get("price"), default=Decimal("0.00"))
    except ValueError as exc:
        errors.append(f"价格无效：{exc}")
        price = Decimal("0.00")

    try:
        category_id = parse_id(form.get("category_id"))
    except ValueError as exc:
        errors.append(f"品类无效：{exc}")
        category_id = None
    if category_id is not None and db.session.get(Category, category_id) is None:
        errors.append("所选品类不存在")
        category_id = None

    is_active = form.get("is_active", "").strip() in {"1", "on", "true", "True"}
    values = {
        "name": name,
        "category_id": category_id,
        "unit": unit,
        "price": price,
        "barcode": barcode,
        "note": note,
        "is_active": is_active,
    }
    return values, errors


@bp.get("/products")
def list():
    """列表页，支持 ?category_id= 筛选。"""
    current_category_id = request.args.get("category_id", type=int)
    query = db.session.query(Product)
    if current_category_id is not None:
        query = query.filter(Product.category_id == current_category_id)
    items = query.order_by(Product.created_at.asc(), Product.id.asc()).all()
    return render_template(
        "products/list.html",
        items=items,
        categories=_categories(),
        current_category_id=current_category_id,
    )


@bp.route("/products/new", methods=["GET", "POST"])
def new():
    action_url = url_for("products.new")
    categories = _categories()
    if request.method == "POST":
        values, errors = _collect(request.form)
        if errors:
            flash("；".join(errors), "danger")
            return render_template(
                "products/form.html",
                obj=Product(**values),
                action_url=action_url,
                submit_label="新建商品",
                categories=categories,
            )
        product = Product(**values)
        db.session.add(product)
        db.session.commit()
        flash(f"商品“{product.name}”已创建。", "success")
        return redirect(url_for("products.list"))
    return render_template(
        "products/form.html",
        obj=None,
        action_url=action_url,
        submit_label="新建商品",
        categories=categories,
    )


@bp.route("/products/<int:pid>/edit", methods=["GET", "POST"])
def edit(pid: int):
    product = db.get_or_404(Product, pid)
    action_url = url_for("products.edit", pid=pid)
    categories = _categories()
    if request.method == "POST":
        values, errors = _collect(request.form)
        if errors:
            flash("；".join(errors), "danger")
            return render_template(
                "products/form.html",
                obj=copy_instance(product, **values),
                action_url=action_url,
                submit_label="保存修改",
                categories=categories,
            )
        for field, value in values.items():
            setattr(product, field, value)
        db.session.commit()
        flash(f"商品“{product.name}”已更新。", "success")
        return redirect(url_for("products.list"))
    return render_template(
        "products/form.html",
        obj=product,
        action_url=action_url,
        submit_label="保存修改",
        categories=categories,
    )


@bp.post("/products/<int:pid>/delete")
def delete(pid: int):
    product = db.get_or_404(Product, pid)
    name = product.name
    db.session.delete(product)
    db.session.commit()
    flash(f"商品“{name}”已删除。", "success")
    return redirect(url_for("products.list"))
