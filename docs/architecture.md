> 读者：要在 app/ 下加功能、或第一次通读后端代码的人。
> 职责：目录与模块职责、一次请求经过哪些层、新增蓝图/模型/模板的落地步骤、当前实现与契约的差距。
> 不写：表字段、路由与 endpoint、模板上下文与表单字段名的清单（链接 SPEC.md 第 3/5/7/8 节）；分支与提交流程（AGENTS.md、CONTRIBUTING.md）。
> 权威来源：代码本身（run.py、app/、migrations/、tests/）与 SPEC.md 第 2、3、5、7 节。

# 架构

## 一 目录结构

```text
ShoppingMgr/
├── run.py                  入口：加载 .env → create_app() → 导出 app；直接运行则起开发服务器
├── app/
│   ├── __init__.py         create_app()：装配配置/扩展/蓝图/钩子/错误处理/CLI，注册 money 过滤器
│   ├── config.py           Config 与 SECRET_KEY 判定（resolve_secret_key、FLASK_DEBUG 解析）
│   ├── extensions.py       db / migrate / csrf 三个扩展实例与 DeclarativeBase
│   ├── auth.py             当前用户钩子、login_required、next 校验、登录失败限流
│   ├── models.py           6 个模型与派生属性（金额统一 Decimal）
│   ├── utils.py            解析与格式化、归属过滤、示例数据
│   ├── blueprints/         6 个蓝图（main / auth / categories / products / lists / expenses）
│   ├── templates/          Jinja2 模板（base、index、404、auth/、categories/、products/、lists/、expenses/）
│   └── static/             Bootstrap 5.3（本地 vendor）与自定义样式
├── migrations/             Alembic：env.py、versions/ 三个版本
├── tests/                  conftest + 7 个测试文件（内存 SQLite、禁网络）
└── instance/shop.db        运行时生成，不提交
```

## 二 模块职责

| 位置 | 职责 | 边界 |
| --- | --- | --- |
| `run.py` | 导入 `app` 之前先 `load_dotenv`，再 `create_app()`；`__main__` 里 `app.run(host, port, debug)` | 不含任何业务逻辑 |
| `app/__init__.py` | 应用工厂：读配置 → 判定 `SECRET_KEY` → 建 `instance/` → `init_app` 三个扩展 → 注册蓝图 → 装 `before_request` → 装错误处理与 CLI | 不写 SQL，不在模块级建 app |
| `app/config.py` | 默认配置与会话策略；`resolve_secret_key` 是纯函数，由工厂调用 | 不做 IO、不读调用栈 |
| `app/extensions.py` | 扩展实例的单例，避免循环导入 | 不配置、不查询 |
| `app/models.py` | 模型字段、关系、派生属性（`subtotal`/`total`）、密码哈希方法 | 不做权限判断，不带视图逻辑 |
| `app/auth.py` | `before_request` 钩子把会话解析成 `g.user`；`login_required`；`safe_next_target`；内存限流 | 不定义路由（路由在 `blueprints/auth.py`） |
| `app/utils.py` | 表单解析（`parse_decimal`/`parse_date`/`parse_id`/`parse_month`）、显示格式化、`owned_or_404` 归属过滤、示例数据 | 不 import 视图 |
| `app/blueprints/*` | 每个模块的路由与视图：取参 → 校验 → 查库 → flash + 跳转或重渲染 | 不建表、不改配置 |
| `app/templates/*` | 只消费视图传入的上下文，变量名以 SPEC 第 7 节为准 | 不做业务计算 |
| `migrations/versions/*` | 版本化 DDL | 不改数据模型的唯一来源（模型在 `models.py`） |
| `tests/*` | 夹具与用例，按行为分组 | 不连开发库、不发网络请求 |

## 三 一次请求经过哪些层

以「已登录用户访问某个 `/<id>/edit` 并提交表单」为例，顺序如下：

1. **Werkzeug 开发服务器**（`run.py` 的 `app.run`）把 HTTP 请求交给 WSGI 应用对象。
2. **CSRF 校验**：`CSRFProtect` 的 `before_request` 先跑。POST 缺 token 或 token 过期时直接抛 `CSRFError`，被 `errorhandler(CSRFError)` 接住：`flash` 一条 danger 文案后 302 回同源来源页（无来源或跨源回首页）。
3. **登录用户解析**：`app.before_request(load_logged_in_user)` 把 `session['user_id']` 查成 `g.user`；用户不存在或被停用时只让 `g.user` 为 `None`，不抛错。
4. **路由匹配**：Flask 用 `url_map` 把路径与方法匹配到「蓝图名.视图名」的 endpoint，路径参数（如 `<int:cid>`）以关键字参数传给视图。
5. **权限装饰器**：视图上的 `@login_required` 判断 `g.user`；未登录 302 到 `/login?next=<原路径>`。
6. **视图函数**：`request.form.get(..., "").strip()` 取参 → `app/utils.py` 的 `parse_*` 校验（失败走 `flash(danger)` + 重渲染同模板、HTTP 200）→ 按 id 取对象时统一走 `owned_or_404`（`id` + `user_id` 一起过滤，取不到即 404）。
7. **数据层**：`db.session` 查询或写入，`commit()` 收尾；`ShoppingList.total` 一类派生属性在 Python 侧算，金额一律 `Decimal` 两位小数。
8. **模板渲染**：`render_template(..., 上下文)` 交给 Jinja2，模板 `extends "base.html"`；`money` 过滤器（`app/__init__.py` 注册，实现是 `utils.fmt_money`）输出 `¥xx.xx`。
9. **响应**：成功是 `flash('...', 'success')` + 302 重定向；找不到资源进 `errorhandler(404)` 渲染 `404.html` 并返回 404。

补充两点：跨用户访问一律按「不存在」处理（404 而非 403），避免泄露资源是否存在；所有业务表都带 `user_id`，任何查询都必须带上它，否则等于越权。规则原文见 [SPEC.md](../SPEC.md) 第 3、5 节。

## 四 新增一个蓝图

顺序要求：**先改契约再改代码**（契约在哪、怎么改见 [AGENTS.md](../AGENTS.md) 与 [CONTRIBUTING.md](../CONTRIBUTING.md)，本文档不复述流程）。

1. 在 [SPEC.md](../SPEC.md) 第 5 节登记路由、endpoint 名与成功跳转，第 7 节写清模板上下文变量，第 8 节写清表单字段名。
2. 新建 `app/blueprints/<模块>.py`：`bp = Blueprint("<模块>", __name__)`，视图用 `@bp.get` / `@bp.route(..., methods=[...])`，每个视图加 `@login_required`。
3. 在 [app/blueprints/__init__.py](../app/blueprints/__init__.py) 里 import 并加入 `ALL_BLUEPRINTS`（`create_app` 只遍历这个元组注册）。
4. 模板放 `app/templates/<模块>/`，风格对齐现有 `list.html` / `form.html`；金额用 `money` 过滤器、日期用 `YYYY-MM-DD`。
5. 加测试：正常路径、校验失败、跨用户 404（`tests/test_isolation.py` 会按 `url_map` 自动覆盖带 `<int:...>` 的新端点，无需改该文件）。
6. 跑 `.venv/bin/python -m pytest -q` 与 `.venv/bin/flask --app run:app routes`，确认端点真的注册且全绿。

## 五 新增一个模型或字段

1. 先在 [SPEC.md](../SPEC.md) 第 3 节改字段与关系定义（含 `user_id`、唯一约束、派生属性），再动代码。
2. 在 [app/models.py](../app/models.py) 加类或列：字段用 `mapped_column`；业务表必须带 `user_id`（FK + `nullable=False` + `index=True`）；金额用 `Numeric(10, 2)` 并在属性里 `quantize` 到两位。
3. 生成并检查迁移脚本（命令语义见 [./database.md](./database.md)）：

   ```bash
   .venv/bin/flask --app run:app db migrate -m 'add xxx'
   # 人工检查 migrations/versions/ 下新脚本：回填、约束名、downgrade 是否可逆
   .venv/bin/flask --app run:app db upgrade
   ```

4. 给既有表加非空列时按「加可空列 → 回填 → 改非空」三步走，SQLite 用 `op.batch_alter_table`（现成范例见 [migrations/versions/8c1f4b7d9e02_v2_user_id_on_business_tables.py](../migrations/versions/8c1f4b7d9e02_v2_user_id_on_business_tables.py)）。
5. 迁移测试要同时断言「表存在」与「列齐全」（见 [tests/test_migrations.py](../tests/test_migrations.py)）。

## 六 新增一个模板

1. 新模板 `extends "base.html"`，在 `block content` 里写内容；导航与 flash 区由 base 提供。
2. 只使用视图实际传入的变量名——变量清单以 [SPEC.md](../SPEC.md) 第 7 节为准，不要在模板里自造后端没传的变量。
3. 金额用 `{{ value|money }}`，日期用 `YYYY-MM-DD`，界面文案中文。
4. 表单必须带 CSRF 隐藏域（字段名以 [SPEC.md](../SPEC.md) 第 8 节为准）；删除操作用 POST + `confirm()`。
5. 静态资源只用 `url_for('static', filename=...)`，禁止 CDN 外链（Bootstrap 已在本地 vendor）。

## 七 当前实现与契约的差距

截至本文档编写时（2026-11-25），代码与 [SPEC.md](../SPEC.md) 第 3、5、6 节尚有缺口，属于未开工的 issue，不是文档写错：

- [SPEC.md](../SPEC.md) 第 5 节里的 `purchases` 蓝图与 `lists.settle` 端点尚未实现：`app/blueprints/` 现有 6 个蓝图，没有 `purchases.py`。
- [SPEC.md](../SPEC.md) 第 3 节里的 `Purchase` / `PurchaseItem` 两个模型尚未实现：`app/models.py` 现有 `User` 与 5 个业务模型。
- [SPEC.md](../SPEC.md) 第 6 节的结算流程因此还无法从界面上走到。

判断某个功能是否已落地，以 `app/blueprints/` 的实际文件、`app/models.py` 的类与 `.venv/bin/flask --app run:app routes` 的输出为准。
