"""expenses 蓝图：消费记录（SPEC 第 4、5、6 节）。"""

from __future__ import annotations

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from sqlalchemy import func

from ..auth import login_required
from ..extensions import db
from ..models import Category, Expense, Product
from ..utils import (
    copy_instance,
    current_month,
    month_range,
    owned_or_404,
    parse_date,
    parse_decimal,
    parse_id,
    parse_month,
    to_decimal,
)

bp = Blueprint("expenses", __name__)


def _categories() -> list[Category]:
    """下拉框用：只列当前用户的品类。"""
    return (
        db.session.query(Category)
        .filter(Category.user_id == g.user.id)
        .order_by(Category.name.asc())
        .all()
    )


def _products() -> list[Product]:
    """下拉框用：只列当前用户的商品。"""
    return (
        db.session.query(Product)
        .filter(Product.user_id == g.user.id)
        .order_by(Product.name.asc())
        .all()
    )


def _months() -> list[str]:
    """本用户库内出现过的年月，倒序（形如 2026-11）。"""
    month_expr = func.strftime("%Y-%m", Expense.spent_on)
    rows = (
        db.session.query(month_expr)
        .filter(Expense.user_id == g.user.id)
        .distinct()
        .order_by(month_expr.desc())
        .all()
    )
    return [row[0] for row in rows if row[0]]


def _owned_id(model, raw_id: int | None) -> bool:
    """该 id 是否属于当前用户（跨用户一律当作不存在）。"""
    if raw_id is None:
        return False
    return (
        db.session.query(model.id)
        .filter(model.id == raw_id, model.user_id == g.user.id)
        .first()
        is not None
    )


def _collect(form) -> tuple[dict, list[str]]:
    """解析消费表单，返回 (字段字典, 错误列表)。"""
    errors: list[str] = []

    try:
        spent_on = parse_date(form.get("spent_on"))
        if spent_on is None:
            errors.append("消费日期不能为空")
    except ValueError as exc:
        errors.append(f"日期无效：{exc}")
        spent_on = None

    try:
        amount = parse_decimal(form.get("amount"), default=None)
        if amount is None:
            errors.append("金额不能为空")
    except ValueError as exc:
        errors.append(f"金额无效：{exc}")
        amount = None

    try:
        category_id = parse_id(form.get("category_id"))
    except ValueError as exc:
        errors.append(f"品类无效：{exc}")
        category_id = None
    if category_id is not None and not _owned_id(Category, category_id):
        errors.append("所选品类不存在")
        category_id = None

    try:
        product_id = parse_id(form.get("product_id"))
    except ValueError as exc:
        errors.append(f"商品无效：{exc}")
        product_id = None
    if product_id is not None and not _owned_id(Product, product_id):
        errors.append("所选商品不存在")
        product_id = None

    note = form.get("note", "").strip()
    if len(note) > 200:
        errors.append("备注不能超过 200 个字符")

    values = {
        "spent_on": spent_on,
        "amount": amount,
        "category_id": category_id,
        "product_id": product_id,
        "note": note,
    }
    return values, errors


@bp.get("/expenses")
@login_required
def list():
    """列表页，支持 ?month=YYYY-MM，默认当月（只统计当前用户）。"""
    raw_month = request.args.get("month", "")
    try:
        month = parse_month(raw_month)
    except ValueError:
        flash("月份格式应为 YYYY-MM，已回退到本月。", "danger")
        month = current_month()

    start, end = month_range(month)
    items = (
        db.session.query(Expense)
        .filter(
            Expense.user_id == g.user.id,
            Expense.spent_on >= start,
            Expense.spent_on < end,
        )
        .order_by(Expense.spent_on.desc(), Expense.id.desc())
        .all()
    )
    month_total = (
        db.session.query(func.coalesce(func.sum(Expense.amount), 0))
        .filter(
            Expense.user_id == g.user.id,
            Expense.spent_on >= start,
            Expense.spent_on < end,
        )
        .scalar()
    )
    return render_template(
        "expenses/list.html",
        items=items,
        month=month,
        month_total=to_decimal(month_total),
        months=_months(),
    )


@bp.route("/expenses/new", methods=["GET", "POST"])
@login_required
def new():
    action_url = url_for("expenses.new")
    categories = _categories()
    products = _products()
    if request.method == "POST":
        values, errors = _collect(request.form)
        if errors:
            flash("；".join(errors), "danger")
            return render_template(
                "expenses/form.html",
                obj=Expense(**values),
                action_url=action_url,
                submit_label="记一笔",
                categories=categories,
                products=products,
            )
        expense = Expense(user_id=g.user.id, **values)
        db.session.add(expense)
        db.session.commit()
        flash(f"已记录 {expense.spent_on} 的消费 {expense.amount} 元。", "success")
        return redirect(url_for("expenses.list"))
    return render_template(
        "expenses/form.html",
        obj=None,
        action_url=action_url,
        submit_label="记一笔",
        categories=categories,
        products=products,
    )


@bp.route("/expenses/<int:eid>/edit", methods=["GET", "POST"])
@login_required
def edit(eid: int):
    expense = owned_or_404(Expense, id=eid)
    action_url = url_for("expenses.edit", eid=eid)
    categories = _categories()
    products = _products()
    if request.method == "POST":
        values, errors = _collect(request.form)
        if errors:
            flash("；".join(errors), "danger")
            return render_template(
                "expenses/form.html",
                obj=copy_instance(expense, **values),
                action_url=action_url,
                submit_label="保存修改",
                categories=categories,
                products=products,
            )
        for field, value in values.items():
            setattr(expense, field, value)
        db.session.commit()
        flash("消费记录已更新。", "success")
        return redirect(url_for("expenses.list"))
    return render_template(
        "expenses/form.html",
        obj=expense,
        action_url=action_url,
        submit_label="保存修改",
        categories=categories,
        products=products,
    )


@bp.post("/expenses/<int:eid>/delete")
@login_required
def delete(eid: int):
    expense = owned_or_404(Expense, id=eid)
    db.session.delete(expense)
    db.session.commit()
    flash("消费记录已删除。", "success")
    return redirect(url_for("expenses.list"))
