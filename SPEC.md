# ShoppingMgr 规格 v1

状态：Lead 定稿，后端/前端实现共同依据。改动只由 Lead 发起。

## 0 目标与非目标

MVP 四块：品类、商品、购物清单、消费记录。服务端渲染、单用户本地使用、中文界面。
本期不做：登录鉴权、多用户、前端框架、图表看板、JSON API、国际化。

## 1 技术栈

Python 3.14 + venv(.venv)；Flask 3.1.x；Flask-SQLAlchemy 3.1.x；Flask-Migrate 4.x；Flask-WTF 1.2.x（CSRFProtect）；python-dotenv；pytest(dev)。数据库 SQLite：instance/shop.db。
依赖清单由 Lead 维护（requirements.txt / requirements-dev.txt）。实施者不安装依赖、不创建 venv、不执行 git。

## 2 文件所有权

Lead：SPEC.md、.gitignore、requirements*.txt、app/static/vendor/**、.venv/**、git 操作
后端(dev-backend)：run.py、app/__init__.py、app/config.py、app/extensions.py、app/models.py、app/utils.py、app/blueprints/**、tests/**、README.md
前端(dev-frontend)：app/templates/**、app/static/css/**、app/static/js/**
只写自己域内文件；跨域改动先报 Lead。__pycache__ 不要写。

## 3 数据模型（app/models.py，SQLAlchemy 2.0 声明式 Mapped/mapped_column，db 来自 app/extensions.py）

Category: id int PK | name str(60) unique not null | note str(200) default '' | created_at datetime
Product: id int PK | name str(80) not null | category_id int FK categories.id 可空 | unit str(10) default '件' | price Numeric(10,2) default 0 | barcode str(64) default '' | note str(200) default '' | is_active bool default True | created_at datetime
ShoppingList: id int PK | name str(80) not null | note str(200) default '' | status str(10) default 'draft'（draft|done） | created_at datetime
ShoppingItem: id int PK | list_id int FK shopping_lists.id not null | product_id int FK products.id 可空 | name str(80) not null（下单名称快照） | qty Numeric(10,2) default 1 | unit_price Numeric(10,2) default 0 | done bool default False | created_at datetime
Expense: id int PK | spent_on Date not null | amount Numeric(10,2) not null | category_id int FK 可空 | product_id int FK 可空 | note str(200) default '' | created_at datetime

关系：Category.products；Product.category；ShoppingList.items（cascade='all, delete-orphan'，按 ShoppingItem.id 排序）；ShoppingItem.list、ShoppingItem.product；Expense.category、Expense.product。
派生属性：ShoppingItem.subtotal = qty*unit_price 保留两位；ShoppingList.total = 各子项 subtotal 之和，空清单返回 Decimal('0.00')。

## 4 路由与端点（url_for 用 endpoint 字符串，蓝图名与 endpoint 必须完全一致）

| 方法 | 路径 | endpoint | 模板 | 成功跳转 |
| --- | --- | --- | --- | --- |
| GET | / | main.index | index.html | - |
| GET | /categories | categories.list | categories/list.html | - |
| GET,POST | /categories/new | categories.new | categories/form.html | categories.list |
| GET,POST | /categories/<int:cid>/edit | categories.edit | categories/form.html | categories.list |
| POST | /categories/<int:cid>/delete | categories.delete | - | categories.list |
| GET | /products | products.list | products/list.html | - |
| GET,POST | /products/new | products.new | products/form.html | products.list |
| GET,POST | /products/<int:pid>/edit | products.edit | products/form.html | products.list |
| POST | /products/<int:pid>/delete | products.delete | - | products.list |
| GET | /lists | lists.list | lists/list.html | - |
| GET,POST | /lists/new | lists.new | lists/form.html | lists.detail |
| GET | /lists/<int:lid> | lists.detail | lists/detail.html | - |
| GET,POST | /lists/<int:lid>/edit | lists.edit | lists/form.html | lists.detail |
| POST | /lists/<int:lid>/items | lists.add_item | - | lists.detail |
| POST | /lists/<int:lid>/items/<int:iid>/toggle | lists.toggle_item | - | lists.detail |
| POST | /items/<int:iid>/delete | lists.delete_item | - | 来源清单列表或详情 |
| POST | /lists/<int:lid>/done | lists.mark_done | - | lists.detail |
| POST | /lists/<int:lid>/delete | lists.delete | - | lists.list |
| GET | /expenses | expenses.list | expenses/list.html | - |
| GET,POST | /expenses/new | expenses.new | expenses/form.html | expenses.list |
| GET,POST | /expenses/<int:eid>/edit | expenses.edit | expenses/form.html | expenses.list |
| POST | /expenses/<int:eid>/delete | expenses.delete | - | expenses.list |

写法约定：蓝图名 main/categories/products/lists/expenses，无 url_prefix，路径按上表写全；注册在 create_app 内。
写操作：成功 flash(msg,'success') + 302 redirect；校验失败 flash(msg,'danger') + 重新渲染同模板（HTTP 200，保留已填值）。
删除一律 POST + 页内 confirm() 确认，不用 GET。
errorhandler(404) 渲染 404.html（HTTP 404）。

## 5 模板上下文契约（后端必须传，前端必须用；不要自造变量名）

- base.html：各模板 extends；含导航（首页/品类/商品/购物清单/消费记录，用 url_for）、flash 区（get_flashed_messages(with_categories=true)）、block content。
- index.html：month_total(Decimal)、month_count(int)、recent_expenses(list[Expense])、active_lists(list[ShoppingList])
- categories/list.html：items(list[Category])，每项需 product_count(int)
- categories/form.html：obj(Category|None)、action_url(str)、submit_label(str)
- products/list.html：items(list[Product])、categories(list[Category])、current_category_id(int|None)
- products/form.html：obj(Product|None)、action_url、submit_label、categories
- lists/list.html：items(list[ShoppingList])，每项需 item_count(int)、done_count(int)
- lists/form.html：obj(ShoppingList|None)、action_url、submit_label
- lists/detail.html：obj(ShoppingList)、products(list[Product])、total(Decimal)
- expenses/list.html：items(list[Expense])、month(str|None 形如 2026-11)、month_total(Decimal)、months(list[str] 倒序可选月)
- expenses/form.html：obj(Expense|None)、action_url、submit_label、categories、products
- 404.html：无额外变量
可能为 None 的关联（category/product）在模板里用 if 判断后再取值。

## 6 表单字段名（前端写死 input name，后端按此取）

- 品类：name、note
- 商品：name、category_id、unit、price、barcode、note、is_active（checkbox，value=1）
- 购物清单：name、note
- 加清单条目：product_id、name、qty、unit_price
- 消费记录：spent_on（date，YYYY-MM-DD）、amount、category_id、product_id、note
后端取值用 request.form.get(...,'').strip()，金额/数量解析失败（含负数、非数字）走校验失败分支。
所有 POST 表单由 Flask-WTF 的 CSRFProtect 校验，必须带 csrf_token 隐藏域；缺失或过期时 flash danger 并重定向回原页。

## 7 静态资源

Bootstrap 5.3 已由 Lead 放到 app/static/vendor/bootstrap.min.css；base.html 用 url_for('static', filename='vendor/bootstrap.min.css') 引用，禁止 CDN 外链。自定义样式放 app/static/css/app.css，交互脚本放 app/static/js/app.js（可选）。
界面文案中文，金额显示 ¥ + 两位小数，日期 YYYY-MM-DD。表格 + 卡片布局，导航栏五项。

## 8 测试（后端，pytest + Flask test client，禁网络）

tests/conftest.py：app fixture（sqlite 内存或 tmp_path）+ client fixture。
tests/test_smoke.py 至少覆盖：GET / 200 且含“本月”；/categories、/products、/lists、/expenses 均 200；POST 新建品类 302 且列表含名称；POST 新建商品（带 category_id）302；新建清单 302 且详情 200；POST 记一笔消费 302 且列表含该金额。

## 9 验收（Lead 执行）

.venv 内安装 requirements 后：python -m pytest -q 全绿；python run.py 启动后 curl 首页与各列表页 200；git init + 初始提交。