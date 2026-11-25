"""categories 蓝图：品类增删改查（SPEC 第 4、5、6 节）。"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import func, update

from ..extensions import db
from ..models import Category, Expense, Product
from ..utils import copy_instance

bp = Blueprint("categories", __name__)


def _validate(name: str, note: str, exclude_id: int | None = None) -> list[str]:
    """返回错误列表；空列表表示通过。"""
    errors: list[str] = []
    if not name:
        errors.append("品类名称不能为空")
    elif len(name) > 60:
        errors.append("品类名称不能超过 60 个字符")
    if len(note) > 200:
        errors.append("备注不能超过 200 个字符")
    if not errors:
        query = db.session.query(Category.id).filter(Category.name == name)
        if exclude_id is not None:
            query = query.filter(Category.id != exclude_id)
        if query.first() is not None:
            errors.append(f"品类“{name}”已存在")
    return errors


@bp.get("/categories")
def list():
    """列表页；product_count 用一次 outer join + group_by 聚合，避免 N+1。"""
    rows = (
        db.session.query(Category, func.count(Product.id))
        .outerjoin(Product, Product.category_id == Category.id)
        .group_by(Category.id)
        .order_by(Category.created_at.asc(), Category.id.asc())
        .all()
    )
    items = []
    for category, product_count in rows:
        category.product_count = int(product_count or 0)
        items.append(category)
    return render_template("categories/list.html", items=items)


@bp.route("/categories/new", methods=["GET", "POST"])
def new():
    action_url = url_for("categories.new")
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        note = request.form.get("note", "").strip()
        errors = _validate(name, note)
        if errors:
            flash("；".join(errors), "danger")
            return render_template(
                "categories/form.html",
                obj=Category(name=name, note=note),
                action_url=action_url,
                submit_label="新建品类",
            )
        category = Category(name=name, note=note)
        db.session.add(category)
        db.session.commit()
        flash(f"品类“{name}”已创建。", "success")
        return redirect(url_for("categories.list"))
    return render_template(
        "categories/form.html",
        obj=None,
        action_url=action_url,
        submit_label="新建品类",
    )


@bp.route("/categories/<int:cid>/edit", methods=["GET", "POST"])
def edit(cid: int):
    category = db.get_or_404(Category, cid)
    action_url = url_for("categories.edit", cid=cid)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        note = request.form.get("note", "").strip()
        errors = _validate(name, note, exclude_id=category.id)
        if errors:
            flash("；".join(errors), "danger")
            return render_template(
                "categories/form.html",
                obj=copy_instance(category, name=name, note=note),
                action_url=action_url,
                submit_label="保存修改",
            )
        category.name = name
        category.note = note
        db.session.commit()
        flash(f"品类“{name}”已更新。", "success")
        return redirect(url_for("categories.list"))
    return render_template(
        "categories/form.html",
        obj=category,
        action_url=action_url,
        submit_label="保存修改",
    )


@bp.post("/categories/<int:cid>/delete")
def delete(cid: int):
    category = db.get_or_404(Category, cid)
    # 关联可空外键：删除前先置空，避免留下悬空引用
    db.session.execute(
        update(Product).where(Product.category_id == cid).values(category_id=None)
    )
    db.session.execute(
        update(Expense).where(Expense.category_id == cid).values(category_id=None)
    )
    db.session.delete(category)
    db.session.commit()
    flash(f"品类“{category.name}”已删除。", "success")
    return redirect(url_for("categories.list"))
