# ShoppingMgr 规格 v2

状态：Lead 定稿，后端/前端实现共同依据。改动只由 Lead 发起。
v1 → v2 变更见文末第 11 节。

## 0 目标与非目标

MVP 四块：品类、商品、购物清单、消费记录；v2 增加：用户与登录、购买记录（清单结算）。服务端渲染、中文界面。
本期不做：第三方登录（OAuth）、找回密码邮件、角色与权限分级、前端框架、图表看板、JSON API、国际化。

## 1 技术栈

Python 3.14 + venv(.venv)；Flask 3.1.x；Flask-SQLAlchemy 3.1.x；Flask-Migrate 4.x；Flask-WTF 1.2+（CSRFProtect）；python-dotenv；pytest(dev)。数据库 SQLite：instance/shop.db。
密码哈希用标准库生态内的 `werkzeug.security`（随 Flask 安装），不引入新依赖。
依赖清单由 Lead 维护（requirements.txt / requirements-dev.txt）。实施者不安装依赖、不创建 venv、不执行 git。

## 2 文件所有权

Lead：SPEC.md、.gitignore、requirements*.txt、app/static/vendor/**、.venv/**、git 操作
后端：run.py、app/__init__.py、app/config.py、app/extensions.py、app/models.py、app/utils.py、app/auth.py、app/blueprints/**、migrations/**、tests/**、README.md
前端：app/templates/**、app/static/css/**、app/static/js/**
只写自己域内文件；跨域改动先报 Lead。__pycache__ 不要写。

## 3 数据模型（app/models.py，SQLAlchemy 2.0 声明式，db 来自 app/extensions.py）

**所有业务表都带** `user_id int FK users.id NOT NULL`，并建索引；所有查询必须按 `user_id` 过滤。

User（表名 users）: id int PK | username str(60) unique not null | password_hash str(255) not null | display_name str(60) default '' | is_active bool default True | last_login_at datetime 可空 | created_at datetime
Category: id | user_id | name str(60) not null（**同用户内唯一**：(user_id, name) unique） | note str(200) default '' | created_at
Product: id | user_id | name str(80) not null | category_id FK 可空 | unit str(10) default '件' | price Numeric(10,2) default 0 | barcode str(64) **可空**（空输入存 NULL；同用户内唯一 (user_id, barcode)） | note str(200) default '' | is_active bool default True | created_at
ShoppingList: id | user_id | name str(80) not null | note str(200) default '' | status str(10) default 'draft'（draft|done） | created_at
ShoppingItem: id | user_id | list_id FK shopping_lists.id not null | product_id FK 可空 | name str(80) not null（下单名称快照） | qty Numeric(10,2) default 1 | unit_price Numeric(10,2) default 0 | done bool default False | created_at
Expense: id | user_id | spent_on Date not null | amount Numeric(10,2) not null | category_id FK 可空 | product_id FK 可空 | **purchase_id FK purchases.id 可空**（由结算生成时有值，手工记账为 NULL） | note str(200) default '' | created_at
Purchase（表名 purchases，购买单）: id | user_id | **list_id FK shopping_lists.id 可空且 unique**（一张清单只能结算一次） | purchased_on Date not null | total Numeric(10,2) not null | note str(200) default '' | created_at
PurchaseItem（表名 purchase_items，购买明细）: id | user_id | purchase_id FK purchases.id not null（cascade='all, delete-orphan'） | product_id FK 可空 | name str(80) not null（名称快照） | qty Numeric(10,2) | unit_price Numeric(10,2) | subtotal 派生属性 = qty*unit_price 两位

关系：Category.products；Product.category；ShoppingList.items（cascade，按 ShoppingItem.id 排序）；ShoppingItem.list/.product；Expense.category/.product/.purchase；Purchase.items（cascade）、Purchase.expense（一对一，uselist=False）、Purchase.list。
派生属性：ShoppingItem.subtotal；ShoppingList.total；Purchase.total 与明细小计之和一致（写入时计算并校验，读取时可用属性复核）。

## 4 用户与登录（app/auth.py + blueprints/auth.py）

- 会话：登录成功写 `session['user_id']` 并 `session.permanent = True`；`PERMANENT_SESSION_LIFETIME = 7 天`；`SESSION_COOKIE_SAMESITE='Lax'`；`SESSION_COOKIE_SECURE` 由环境变量 `SESSION_COOKIE_SECURE=1` 打开（本地 http 不能开）。
- `app/auth.py` 提供：`before_app_request` 钩子把当前用户放进 `g.user`（未登录为 None）、`login_required` 装饰器、`get_current_user()`。
- **除静态资源、`auth.login`、`auth.register`、404 页外，所有视图都必须登录**；未登录访问 → 302 `/login?next=<原路径>`，登录成功回跳 `next`（**仅接受站内相对路径**，以 `/` 开头且不以 `//` 开头，否则回首页）。
- 已登录访问 `/login`、`/register` → 302 首页。
- 密码：`werkzeug.security.generate_password_hash` / `check_password_hash`；最短 8 位，不得与用户名相同；原始密码不入库、不写日志。
- 登录失败统一提示「用户名或密码不正确」（不区分用户不存在/密码错误）；`is_active=False` 同样按失败处理。
- 限流：同一 username 60 秒内失败累计 5 次 → 该 username 在 60 秒内一律按失败返回（内存字典实现，重启失效可接受）。

## 5 路由与端点（url_for 用 endpoint 字符串）

| 方法 | 路径 | endpoint | 模板 | 成功跳转 |
| --- | --- | --- | --- | --- |
| GET,POST | /register | auth.register | auth/register.html | main.index |
| GET,POST | /login | auth.login | auth/login.html | next 或 main.index |
| POST | /logout | auth.logout | - | auth.login |
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
| POST | /lists/<int:lid>/settle | lists.settle | - | purchases.detail |
| POST | /lists/<int:lid>/delete | lists.delete | - | lists.list |
| GET | /purchases | purchases.list | purchases/list.html | - |
| GET | /purchases/<int:pid> | purchases.detail | purchases/detail.html | - |
| POST | /purchases/<int:pid>/delete | purchases.delete | - | purchases.list |
| GET | /expenses | expenses.list | expenses/list.html | - |
| GET,POST | /expenses/new | expenses.new | expenses/form.html | expenses.list |
| GET,POST | /expenses/<int:eid>/edit | expenses.edit | expenses/form.html | expenses.list |
| POST | /expenses/<int:eid>/delete | expenses.delete | - | expenses.list |

写法约定：蓝图名 auth/main/categories/products/lists/purchases/expenses，无 url_prefix，路径按上表写全；注册在 create_app 内。
写操作：成功 flash(msg,'success') + 302 redirect；校验失败 flash(msg,'danger') + 重新渲染同模板（HTTP 200，保留已填值）。
删除一律 POST + 页内 confirm() 确认，不用 GET。
**跨用户访问按不存在处理**：按 id 查询时一律 `filter_by(id=..., user_id=g.user.id).first_or_404()`，返回 404 而非 403，避免泄露资源是否存在。
errorhandler(404) 渲染 404.html（HTTP 404）。

## 6 清单结算（lists.settle）语义

1. 取该清单所有 `done=False` 的条目；为空 → flash danger「没有待结算条目」+ 302 回详情，不生成任何记录。
2. 清单已有 Purchase（`purchases.list_id` 唯一）→ flash danger「该清单已结算」+ 302 回详情。
3. 生成 Purchase：`purchased_on` 取表单值（默认今天）、`total` = 明细小计之和；生成同数量 PurchaseItem（名称/数量/单价快照）。
4. 同步生成 1 条 Expense：`amount=Purchase.total`、`spent_on=purchased_on`、`purchase_id=Purchase.id`、`note='清单结算：<清单名>'`。
5. 清单 `status` 置 `done`；ShoppingItem 原样保留（不删除，明细在 PurchaseItem 里另有快照）。
6. 整个过程在一个事务内完成；任一步失败整体回滚。
7. `purchases.delete`：删除购买单与其明细，并删除关联 Expense（同一事务）。

## 7 模板上下文契约（后端必须传，前端必须用；不要自造变量名）

- base.html：各模板 extends；导航：首页/品类/商品/购物清单/购买/消费记录；右侧显示 `g.user.display_name or g.user.username` 与登出按钮（POST 表单）；未登录显示登录/注册链接；flash 区（with_categories）；block content。
- auth/login.html：`next`(str|None)（登录表单的隐藏域）
- auth/register.html：无额外变量
- index.html：month_total(Decimal)、month_count(int)、recent_expenses(list[Expense])、active_lists(list[ShoppingList])、recent_purchases(list[Purchase] 最近 5 张)
- categories/list.html：items(list[Category])，每项需 product_count(int)
- categories/form.html：obj(Category|None)、action_url(str)、submit_label(str)
- products/list.html：items(list[Product])、categories(list[Category])、current_category_id(int|None)、q(str|None)
- products/form.html：obj(Product|None)、action_url、submit_label、categories
- lists/list.html：items(list[ShoppingList])，每项需 item_count(int)、done_count(int)
- lists/form.html：obj(ShoppingList|None)、action_url、submit_label
- lists/detail.html：obj(ShoppingList)、products(list[Product])、total(Decimal)、purchase(Purchase|None 该清单已结算的购买单)
- purchases/list.html：items(list[Purchase])（每项需 item_count(int)）、month(str|None)、month_total(Decimal)、months(list[str] 倒序)
- purchases/detail.html：obj(Purchase)（`obj.items` 明细、`obj.expense` 关联消费可空）
- expenses/list.html：items(list[Expense])、month、month_total、months
- expenses/form.html：obj(Expense|None)、action_url、submit_label、categories、products
- 404.html：无额外变量
可能为 None 的关联（category/product/purchase/expense）在模板里用 if 判断后再取值。

## 8 表单字段名（前端写死 input name，后端按此取）

- 注册：username、display_name、password、password2
- 登录：username、password、next（隐藏域）
- 品类：name、note
- 商品：name、category_id、unit、price、barcode、note、is_active（checkbox，value=1）
- 购物清单：name、note
- 加清单条目：product_id、name、qty、unit_price
- 结算：purchased_on（date，默认今天）、note
- 消费记录：spent_on、amount、category_id、product_id、note
后端取值用 request.form.get(...,'').strip()，金额/数量解析失败（含负数、非数字）走校验失败分支。
所有 POST 表单由 Flask-WTF 的 CSRFProtect 校验，必须带 csrf_token 隐藏域；缺失或过期时 flash danger 并重定向回原页。

## 9 静态资源与界面

Bootstrap 5.3 在 app/static/vendor/bootstrap.min.css，base.html 用 url_for('static', filename='vendor/bootstrap.min.css') 引用，禁止 CDN 外链。自定义样式放 app/static/css/app.css。
界面文案中文，金额 ¥ + 两位小数，日期 YYYY-MM-DD。表格 + 卡片布局。

## 10 迁移策略（migrations/，Alembic）

- 以 v1 现状（无 user_id）为 `baseline` 迁移；v2 增量迁移逐个交付，不做一次性大迁移。
- `init-db` 保持「drop_all + create_all + 种子数据」，但必须在 create_all 后 `alembic stamp head`，否则迁移与建库两条路径会冲突。
- 加 `user_id` 的迁移写三步：先加可空列 → 回填（取 id 最小的用户）→ 改非空 + 建索引；**回填前要求库中已存在用户**，否则迁移直接报错并提示先运行 `flask --app run:app init-admin --username X --password Y`。
- 存量 v1 数据统一归属到 id 最小的用户。
- 迁移必须可重复执行且失败不留半成品（单事务）。

## 11 测试要求（pytest + Flask test client，禁网络）

- `tests/conftest.py`：`app`/`client` fixture + `auth_client`（已登录客户端）+ `second_client`（第二个用户的客户端）；`WTF_CSRF_ENABLED=False`。
- 认证：注册成功 302、重名失败回渲染、登录成功、密码错误统一提示、限流 5 次后拒绝、登出后受保护页 302、未登录访问带 `next` 回跳、外域 `next` 回首页。
- 归属隔离：用户 A 建数据 → 用户 B 列表为空、按 id 访问 404。
- 越权门禁 `tests/test_isolation.py`：遍历 `app.url_map` 中所有含 `<int:...>` 的端点，用第二个用户请求第一个用户的资源，断言 404；新增端点自动纳入。
- 结算：金额与小计一致、清单转 done、重复结算被拒、无待结算条目被拒、关联 Expense 金额一致、删除购买单连带删 Expense。
- 既有 8 条 smoke 用例在加登录后仍须通过（改用 `auth_client`）。

## 12 验收（Lead 执行）

.venv 内：`python -m pytest -q` 全绿；`flask --app run:app init-db` 后可启动；`python run.py` 后 curl 首页/登录页/受保护页（未登录 302）；`flask db upgrade` 在 v1 库上可成功升级；git 提交走 PR。

## 13 v1 → v2 变更摘要

- 新增：`users`、`purchases`、`purchase_items` 三表；`auth`、`purchases` 两个蓝图；登录/注册/登出/结算/购买列表/购买详情/删除购买单 7 条路由。
- 修改：5 张业务表加 `user_id`；`expenses` 加 `purchase_id`；`categories.name` 唯一性改为同用户内；`products.barcode` 改为可空且同用户内唯一。
- 规则：全部视图需登录（除静态、登录、注册、404）；跨用户 id 一律 404；结算一次性且事务化。
- 影响：`tests/conftest.py` 需新增已登录客户端 fixture；既有 8 条 smoke 用例改走 `auth_client`。
