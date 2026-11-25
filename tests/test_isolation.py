"""归属隔离（SPEC 第 5、11 节）：B 看不到、也动不了 A 的资源。

三条线：
1. 动态遍历 app.url_map，把所有含 <int:...> 的端点用 second_client 打一遍，一律 404
   —— 以后新增带 id 的端点会自动纳入，不用改测试；
2. 未登录访问业务页 → 302 /login?next=<原路径>；
3. 显式用例：A 建品类后 B 列表看不到、B 按 id 编辑/删除 404（清单/消费同构）。
"""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import parse_qs, urlsplit

from app.models import Category, Expense, Product, ShoppingItem, ShoppingList

# 路径参数名（SPEC 第 5 节）→ 由 A 造出来的资源 id
INT_PARAM_RE = re.compile(r"<int:(\w+)>")

# 未登录也必须 302 到登录页的业务页（main.index + 各蓝图 GET 入口）
BUSINESS_PAGES = (
    "/",
    "/categories",
    "/categories/new",
    "/products",
    "/products/new",
    "/lists",
    "/lists/new",
    "/expenses",
    "/expenses/new",
)


def _seed_a_resources(app, auth_client) -> dict[str, int]:
    """用已登录的 A 造齐 5 类资源，返回 {参数名: id}。"""
    auth_client.post("/categories/new", data={"name": "A的品类", "note": ""})
    with app.app_context():
        cid = Category.query.filter_by(name="A的品类").one().id

    auth_client.post(
        "/products/new",
        data={
            "name": "A的商品",
            "category_id": str(cid),
            "unit": "件",
            "price": "1.00",
            "barcode": "",
        },
    )
    with app.app_context():
        pid = Product.query.filter_by(name="A的商品").one().id

    auth_client.post("/lists/new", data={"name": "A的清单", "note": ""})
    with app.app_context():
        lid = ShoppingList.query.filter_by(name="A的清单").one().id

    auth_client.post(
        f"/lists/{lid}/items",
        data={
            "product_id": str(pid),
            "name": "A的条目",
            "qty": "1",
            "unit_price": "1.00",
        },
    )
    with app.app_context():
        iid = ShoppingItem.query.filter_by(name="A的条目").one().id

    auth_client.post(
        "/expenses/new",
        data={
            "spent_on": date.today().isoformat(),
            "amount": "9.90",
            "category_id": str(cid),
            "product_id": str(pid),
            "note": "A的消费",
        },
    )
    with app.app_context():
        eid = Expense.query.filter_by(note="A的消费").one().id

    return {"cid": cid, "pid": pid, "lid": lid, "iid": iid, "eid": eid}


def test_int_endpoints_reject_other_users(app, auth_client, second_client):
    """遍历 url_map：所有含 <int:...> 的端点，B 请求 A 的资源 id 一律 404。"""
    ids = _seed_a_resources(app, auth_client)

    checked: list[str] = []
    for rule in app.url_map.iter_rules():
        params = INT_PARAM_RE.findall(rule.rule)
        if not params:
            continue
        path = rule.rule
        for name in params:
            path = path.replace(f"<int:{name}>", str(ids[name]))
        methods = sorted((rule.methods or set()) - {"HEAD", "OPTIONS"})
        method = "GET" if "GET" in methods else "POST"
        response = second_client.open(path, method=method)
        assert response.status_code == 404, (
            f"{method} {path} -> {response.status_code}，跨用户访问必须按不存在处理"
        )
        checked.append(f"{method} {path}")

    # 防止用例空转：端点被删光时这里必须红
    assert len(checked) >= 13, f"动态扫到的带 id 端点太少：{checked}"


def test_anonymous_business_pages_redirect_to_login(client):
    """未登录访问各业务页 → 302 /login?next=<原路径>。"""
    for path in BUSINESS_PAGES:
        response = client.get(path)
        assert response.status_code == 302, f"{path} -> {response.status_code}"
        parts = urlsplit(response.headers["Location"])
        assert parts.path == "/login", f"{path} 被送到 {parts.path}"
        assert parse_qs(parts.query).get("next") == [path], response.headers["Location"]


def test_category_invisible_and_404_for_other_user(app, auth_client, second_client):
    """A 建品类后：B 列表看不到，B 按 id 编辑/删除 → 404。"""
    auth_client.post("/categories/new", data={"name": "只属于A", "note": "隔离用例"})
    with app.app_context():
        cid = Category.query.filter_by(name="只属于A").one().id

    listing = second_client.get("/categories")
    assert listing.status_code == 200
    assert "只属于A" not in listing.get_data(as_text=True)

    assert second_client.get(f"/categories/{cid}/edit").status_code == 404
    assert second_client.post(f"/categories/{cid}/delete").status_code == 404

    # 确认没被误删：A 自己还能看到
    assert "只属于A" in auth_client.get("/categories").get_data(as_text=True)


def test_list_and_expense_invisible_for_other_user(app, auth_client, second_client):
    """清单与消费同样隔离：B 详情页 404、列表与首页都看不到 A 的数据。"""
    ids = _seed_a_resources(app, auth_client)

    assert second_client.get(f"/lists/{ids['lid']}").status_code == 404
    assert second_client.get(f"/lists/{ids['lid']}/edit").status_code == 404
    assert second_client.post(f"/lists/{ids['lid']}/done").status_code == 404
    assert (
        second_client.post(
            f"/lists/{ids['lid']}/items/{ids['iid']}/toggle"
        ).status_code
        == 404
    )
    assert second_client.get(f"/expenses/{ids['eid']}/edit").status_code == 404

    lists_page = second_client.get("/lists").get_data(as_text=True)
    assert "A的清单" not in lists_page
    expenses_page = second_client.get("/expenses").get_data(as_text=True)
    assert "A的消费" not in expenses_page
    assert "9.90" not in expenses_page

    index_page = second_client.get("/").get_data(as_text=True)
    assert "A的清单" not in index_page
    assert "9.90" not in index_page
