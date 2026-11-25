"""冒烟测试：覆盖 SPEC 第 8 节全部断言。"""

from __future__ import annotations

from datetime import date

from app.models import Category, Expense


def _text(response) -> str:
    return response.get_data(as_text=True)


def _category_id(app, name: str) -> int:
    with app.app_context():
        return Category.query.filter_by(name=name).one().id


def test_index_ok(client):
    """GET / 返回 200，页面含“本月”。"""
    response = client.get("/")
    assert response.status_code == 200
    assert "本月" in _text(response)


def test_list_pages_ok(client):
    """四个列表页均 200。"""
    for path in ("/categories", "/products", "/lists", "/expenses"):
        response = client.get(path)
        assert response.status_code == 200, f"{path} -> {response.status_code}"


def test_create_category(app, client):
    """POST 新建品类 302，列表页含名称。"""
    response = client.post(
        "/categories/new",
        data={"name": "测试品类", "note": "冒烟测试"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "categories" in response.headers["Location"]

    listing = client.get("/categories")
    assert "测试品类" in _text(listing)
    assert _category_id(app, "测试品类") > 0


def test_create_product_with_category(app, client):
    """POST 新建商品（带 category_id）302。"""
    client.post(
        "/products/new",
        data={"name": "苹果", "category_id": "", "unit": "件", "price": "0"},
    )
    # 先建品类，再用真实 id 建商品
    client.post("/categories/new", data={"name": "蔬果", "note": ""})
    cid = _category_id(app, "蔬果")

    response = client.post(
        "/products/new",
        data={
            "name": "香蕉",
            "category_id": str(cid),
            "unit": "把",
            "price": "5.20",
            "barcode": "6901234567890",
            "note": "测试商品",
            "is_active": "1",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "products" in response.headers["Location"]

    listing = client.get(f"/products?category_id={cid}")
    assert listing.status_code == 200
    assert "香蕉" in _text(listing)


def test_create_list_then_detail(client):
    """新建清单 302，随后详情页 200。"""
    response = client.post(
        "/lists/new",
        data={"name": "本周采购", "note": "冒烟测试"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    detail = client.get(response.headers["Location"])
    assert detail.status_code == 200
    assert "本周采购" in _text(detail)


def test_create_expense(client):
    """POST 记一笔消费 302，列表页含该金额。"""
    today = date.today().isoformat()
    response = client.post(
        "/expenses/new",
        data={
            "spent_on": today,
            "amount": "12.34",
            "category_id": "",
            "product_id": "",
            "note": "冒烟测试",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    listing = client.get("/expenses")
    assert listing.status_code == 200
    assert "12.34" in _text(listing)


def test_expense_invalid_amount_rerenders(app, client):
    """金额非数字：不写库，返回 200 重渲染（校验失败分支）。"""
    response = client.post(
        "/expenses/new",
        data={"spent_on": date.today().isoformat(), "amount": "abc", "note": ""},
        follow_redirects=False,
    )
    assert response.status_code == 200

    with app.app_context():
        assert Expense.query.count() == 0


def test_expense_negative_amount_rerenders(app, client):
    """负金额同样走校验失败分支。"""
    response = client.post(
        "/expenses/new",
        data={"spent_on": date.today().isoformat(), "amount": "-1.00", "note": ""},
        follow_redirects=False,
    )
    assert response.status_code == 200

    with app.app_context():
        assert Expense.query.count() == 0
