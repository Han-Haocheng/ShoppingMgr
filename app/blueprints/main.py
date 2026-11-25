"""main 蓝图：首页（SPEC 第 4、5 节）。"""

from __future__ import annotations

from flask import Blueprint, render_template
from sqlalchemy import func

from ..extensions import db
from ..models import Expense, ShoppingList
from ..utils import current_month, month_range, to_decimal

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    """当月消费汇总 + 最近 5 笔消费 + 草稿清单 5 个。"""
    start, end = month_range(current_month())

    month_total, month_count = (
        db.session.query(
            func.coalesce(func.sum(Expense.amount), 0),
            func.count(Expense.id),
        )
        .filter(Expense.spent_on >= start, Expense.spent_on < end)
        .one()
    )

    recent_expenses = (
        db.session.query(Expense)
        .order_by(Expense.spent_on.desc(), Expense.id.desc())
        .limit(5)
        .all()
    )

    active_lists = (
        db.session.query(ShoppingList)
        .filter(ShoppingList.status == "draft")
        .order_by(ShoppingList.created_at.desc(), ShoppingList.id.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "index.html",
        month_total=to_decimal(month_total),
        month_count=int(month_count or 0),
        recent_expenses=recent_expenses,
        active_lists=active_lists,
    )
