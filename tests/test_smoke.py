"""冒烟测试：覆盖 SPEC 第 8 节全部断言。

#15 起所有业务页都要登录，既有用例一律改走 auth_client（语义不变，只换客户端）。
"""

from __future__ import annotations

from datetime import date

from app.models import Category, Expense


def _text(response) -> str:
    return response.get_data(as_text=True)


def _category_id(app, name: str) -> int:
    with app.app_context():
        return Category.query.filter_by(name=name).one().id


def test_index_ok(auth_client):
    """GET / 返回 200，页面含“本月”。"""
    response = auth_client.get("/")
    assert response.status_code == 200
    assert "本月" in _text(response)


def test_list_pages_ok(auth_client):
    """四个列表页均 200。"""
    for path in ("/categories", "/products", "/lists", "/expenses"):
        response = auth_client.get(path)
        assert response.status_code == 200, f"{path} -> {response.status_code}"


def test_create_category(app, auth_client):
    """POST 新建品类 302，列表页含名称。"""
    response = auth_client.post(
        "/categories/new",
        data={"name": "测试品类", "note": "冒烟测试"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "categories" in response.headers["Location"]

    listing = auth_client.get("/categories")
    assert "测试品类" in _text(listing)
    assert _category_id(app, "测试品类") > 0


def test_create_product_with_category(app, auth_client):
    """POST 新建商品（带 category_id）302。"""
    auth_client.post(
        "/products/new",
        data={"name": "苹果", "category_id": "", "unit": "件", "price": "0"},
    )
    # 先建品类，再用真实 id 建商品
    auth_client.post("/categories/new", data={"name": "蔬果", "note": ""})
    cid = _category_id(app, "蔬果")

    response = auth_client.post(
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

    listing = auth_client.get(f"/products?category_id={cid}")
    assert listing.status_code == 200
    assert "香蕉" in _text(listing)


def test_create_list_then_detail(auth_client):
    """新建清单 302，随后详情页 200。"""
    response = auth_client.post(
        "/lists/new",
        data={"name": "本周采购", "note": "冒烟测试"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    detail = auth_client.get(response.headers["Location"])
    assert detail.status_code == 200
    assert "本周采购" in _text(detail)


def test_create_expense(auth_client):
    """POST 记一笔消费 302，列表页含该金额。"""
    today = date.today().isoformat()
    response = auth_client.post(
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

    listing = auth_client.get("/expenses")
    assert listing.status_code == 200
    assert "12.34" in _text(listing)


def test_expense_invalid_amount_rerenders(app, auth_client):
    """金额非数字：不写库，返回 200 重渲染（校验失败分支）。"""
    response = auth_client.post(
        "/expenses/new",
        data={"spent_on": date.today().isoformat(), "amount": "abc", "note": ""},
        follow_redirects=False,
    )
    assert response.status_code == 200

    with app.app_context():
        assert Expense.query.count() == 0


def test_expense_negative_amount_rerenders(app, auth_client):
    """负金额同样走校验失败分支。"""
    response = auth_client.post(
        "/expenses/new",
        data={"spent_on": date.today().isoformat(), "amount": "-1.00", "note": ""},
        follow_redirects=False,
    )
    assert response.status_code == 200

    with app.app_context():
        assert Expense.query.count() == 0


# ---------------------------------------------------------------- #15 追加（归属相关）

def test_empty_barcode_is_stored_as_null(app, auth_client):
    """SPEC 第 3 节：条码空输入存 NULL 而不是空串，否则唯一约束会互相撞车。"""
    from app.models import Product

    auth_client.post(
        "/products/new",
        data={"name": "无码商品", "unit": "件", "price": "1.00", "barcode": "   "},
    )
    with app.app_context():
        product = Product.query.filter_by(name="无码商品").one()
        assert product.barcode is None
        assert product.user_id > 0


def test_duplicate_category_name_rejected_for_same_user(app, auth_client):
    """同用户内品类重名被拒：页面提示已存在，库里只有一条。"""
    auth_client.post("/categories/new", data={"name": "重名品类", "note": ""})
    second = auth_client.post(
        "/categories/new", data={"name": "重名品类", "note": ""}, follow_redirects=True
    )
    assert second.status_code == 200
    assert "已存在" in _text(second)
    with app.app_context():
        assert Category.query.filter_by(name="重名品类").count() == 1
