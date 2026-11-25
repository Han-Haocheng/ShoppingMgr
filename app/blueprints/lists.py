"""lists 蓝图：购物清单与条目（SPEC 第 4、5、6 节）。"""

from __future__ import annotations

from decimal import Decimal

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import case, func

from ..extensions import db
from ..models import Product, ShoppingItem, ShoppingList
from ..utils import copy_instance, parse_decimal, parse_id

bp = Blueprint("lists", __name__)


def _validate(name: str, note: str) -> list[str]:
    errors: list[str] = []
    if not name:
        errors.append("清单名称不能为空")
    elif len(name) > 80:
        errors.append("清单名称不能超过 80 个字符")
    if len(note) > 200:
        errors.append("备注不能超过 200 个字符")
    return errors


def _products() -> list[Product]:
    return db.session.query(Product).order_by(Product.name.asc()).all()


@bp.get("/lists")
def list():
    """列表页；item_count / done_count 用一次 outer join + group_by 聚合，避免 N+1。"""
    rows = (
        db.session.query(
            ShoppingList,
            func.count(ShoppingItem.id),
            func.coalesce(
                func.sum(case((ShoppingItem.done.is_(True), 1), else_=0)), 0
            ),
        )
        .outerjoin(ShoppingItem, ShoppingItem.list_id == ShoppingList.id)
        .group_by(ShoppingList.id)
        .order_by(ShoppingList.created_at.desc(), ShoppingList.id.desc())
        .all()
    )
    items = []
    for shopping_list, item_count, done_count in rows:
        shopping_list.item_count = int(item_count or 0)
        shopping_list.done_count = int(done_count or 0)
        items.append(shopping_list)
    return render_template("lists/list.html", items=items)


@bp.route("/lists/new", methods=["GET", "POST"])
def new():
    action_url = url_for("lists.new")
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        note = request.form.get("note", "").strip()
        errors = _validate(name, note)
        if errors:
            flash("；".join(errors), "danger")
            return render_template(
                "lists/form.html",
                obj=ShoppingList(name=name, note=note),
                action_url=action_url,
                submit_label="新建清单",
            )
        shopping_list = ShoppingList(name=name, note=note, status="draft")
        db.session.add(shopping_list)
        db.session.commit()
        flash(f"清单“{name}”已创建。", "success")
        return redirect(url_for("lists.detail", lid=shopping_list.id))
    return render_template(
        "lists/form.html",
        obj=None,
        action_url=action_url,
        submit_label="新建清单",
    )


@bp.get("/lists/<int:lid>")
def detail(lid: int):
    shopping_list = db.get_or_404(ShoppingList, lid)
    return render_template(
        "lists/detail.html",
        obj=shopping_list,
        products=_products(),
        total=shopping_list.total,
    )


@bp.route("/lists/<int:lid>/edit", methods=["GET", "POST"])
def edit(lid: int):
    shopping_list = db.get_or_404(ShoppingList, lid)
    action_url = url_for("lists.edit", lid=lid)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        note = request.form.get("note", "").strip()
        errors = _validate(name, note)
        if errors:
            flash("；".join(errors), "danger")
            return render_template(
                "lists/form.html",
                obj=copy_instance(shopping_list, name=name, note=note),
                action_url=action_url,
                submit_label="保存修改",
            )
        shopping_list.name = name
        shopping_list.note = note
        db.session.commit()
        flash(f"清单“{name}”已更新。", "success")
        return redirect(url_for("lists.detail", lid=shopping_list.id))
    return render_template(
        "lists/form.html",
        obj=shopping_list,
        action_url=action_url,
        submit_label="保存修改",
    )


@bp.post("/lists/<int:lid>/items")
def add_item(lid: int):
    shopping_list = db.get_or_404(ShoppingList, lid)
    form = request.form
    errors: list[str] = []

    try:
        product_id = parse_id(form.get("product_id"))
    except ValueError as exc:
        errors.append(f"商品无效：{exc}")
        product_id = None
    product = db.session.get(Product, product_id) if product_id else None
    if product_id is not None and product is None:
        errors.append("所选商品不存在")
        product_id = None

    name = form.get("name", "").strip()
    if not name and product is not None:
        name = product.name
    if not name:
        errors.append("条目名称不能为空")
    elif len(name) > 80:
        errors.append("条目名称不能超过 80 个字符")

    default_qty = Decimal("1.00")
    try:
        qty = parse_decimal(form.get("qty"), default=default_qty)
    except ValueError as exc:
        errors.append(f"数量无效：{exc}")
        qty = default_qty

    default_price = (
        product.price if product is not None and product.price is not None
        else Decimal("0.00")
    )
    try:
        unit_price = parse_decimal(form.get("unit_price"), default=default_price)
    except ValueError as exc:
        errors.append(f"单价无效：{exc}")
        unit_price = default_price

    if errors:
        # 该端点无模板（SPEC 表格模板列为“-”），用 danger flash + 回详情页呈现
        flash("；".join(errors), "danger")
        return redirect(url_for("lists.detail", lid=shopping_list.id))

    item = ShoppingItem(
        list_id=shopping_list.id,
        product_id=product_id,
        name=name,
        qty=qty,
        unit_price=unit_price,
        done=False,
    )
    db.session.add(item)
    db.session.commit()
    flash(f"已添加条目“{name}”。", "success")
    return redirect(url_for("lists.detail", lid=shopping_list.id))


@bp.post("/lists/<int:lid>/items/<int:iid>/toggle")
def toggle_item(lid: int, iid: int):
    shopping_list = db.get_or_404(ShoppingList, lid)
    item = db.get_or_404(ShoppingItem, iid)
    if item.list_id != shopping_list.id:
        abort(404)
    item.done = not item.done
    db.session.commit()
    flash(f"条目“{item.name}”已{'勾选' if item.done else '取消勾选'}。", "success")
    return redirect(url_for("lists.detail", lid=shopping_list.id))


@bp.post("/items/<int:iid>/delete")
def delete_item(iid: int):
    """endpoint 属于 lists 蓝图（SPEC 第 4 节），路径为 /items/<iid>/delete。"""
    item = db.get_or_404(ShoppingItem, iid)
    list_id = item.list_id
    name = item.name
    db.session.delete(item)
    db.session.commit()
    flash(f"已删除条目“{name}”。", "success")

    back = (request.form.get("back") or request.args.get("back") or "").strip()
    if back == "list":
        return redirect(url_for("lists.list"))
    if list_id is not None and db.session.get(ShoppingList, list_id) is not None:
        return redirect(url_for("lists.detail", lid=list_id))
    return redirect(url_for("lists.list"))


@bp.post("/lists/<int:lid>/done")
def mark_done(lid: int):
    shopping_list = db.get_or_404(ShoppingList, lid)
    shopping_list.status = "done"
    db.session.commit()
    flash(f"清单“{shopping_list.name}”已标记完成。", "success")
    return redirect(url_for("lists.detail", lid=shopping_list.id))


@bp.post("/lists/<int:lid>/delete")
def delete(lid: int):
    shopping_list = db.get_or_404(ShoppingList, lid)
    name = shopping_list.name
    db.session.delete(shopping_list)  # items 由 cascade='all, delete-orphan' 级联
    db.session.commit()
    flash(f"清单“{name}”已删除。", "success")
    return redirect(url_for("lists.list"))
