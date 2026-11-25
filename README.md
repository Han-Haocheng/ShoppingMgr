# ShoppingMgr（购物管家）

[![CI](https://github.com/Han-Haocheng/ShoppingMgr/actions/workflows/ci.yml/badge.svg)](https://github.com/Han-Haocheng/ShoppingMgr/actions/workflows/ci.yml)

买菜/囤货场景的单用户记账 + 购物清单小工具。Flask 服务端渲染，中文界面，数据落在本地
SQLite。后端按 `SPEC.md` 实现；SPEC 是唯一权威契约，本文件只描述怎么跑。

## 快速开始（五步）

```bash
# 1. 建虚拟环境（Python 3.14）
python3 -m venv .venv
source .venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt      # 只跑测试才需要（pytest）

# 3. 建库并写入示例数据（5 品类 / 8 商品 / 1 草稿清单 3 条目 / 6 笔本月消费）
flask --app run:app init-db

# 4. 启动开发服务器
python run.py                            # http://127.0.0.1:5000

# 5. 跑测试
python -m pytest -q
```

说明：

- 数据库文件为 `instance/shop.db`（`instance/` 已被 `.gitignore` 忽略），首次访问前先执行
  `init-db`。
- CLI 命令：
  - `init-db`：`drop_all + create_all + 写入示例数据`（**会清空现有数据**）。
  - `seed-db`：只写入示例数据，不动表结构；库里已有数据时跳过。
- 端口/主机可用环境变量覆盖：`HOST`、`PORT`；`FLASK_DEBUG=0` 关闭调试重载。
- 数据库地址可用 `DATABASE_URL` 覆盖（默认 `sqlite:///shop.db`，相对 Flask 的
  `instance_path`）。

## 目录说明

```
ShoppingMgr/
├── SPEC.md                 规格（唯一权威契约，Lead 维护）
├── requirements.txt        运行时依赖（Flask / Flask-SQLAlchemy / Flask-Migrate / python-dotenv）
├── requirements-dev.txt    开发依赖（pytest）
├── run.py                  入口：导出 app 供 flask 发现，直接运行则起开发服务器
├── app/
│   ├── __init__.py         create_app()：配置、db/migrate、5 个蓝图、404、CLI
│   ├── config.py           Config：SECRET_KEY、SQLALCHEMY_DATABASE_URI
│   ├── extensions.py       db（SQLAlchemy 2.0 DeclarativeBase）、migrate
│   ├── models.py           Category / Product / ShoppingList / ShoppingItem / Expense
│   ├── utils.py            parse_decimal / parse_date / parse_month / fmt_money / 月份区间 / 示例数据
│   ├── blueprints/
│   │   ├── __init__.py     ALL_BLUEPRINTS（无 url_prefix）
│   │   ├── main.py         GET /                       主页汇总
│   │   ├── categories.py   品类 CRUD
│   │   ├── products.py     商品 CRUD（支持 ?category_id= 筛选）
│   │   ├── lists.py        清单 CRUD + 条目增删勾选
│   │   └── expenses.py     消费记录 CRUD（支持 ?month=YYYY-MM）
│   ├── templates/          前端（dev-frontend 域，不在后端改动范围）
│   └── static/             Bootstrap / 自定义样式（同上）
├── tests/
│   ├── conftest.py         app / client 夹具，内存 SQLite
│   └── test_smoke.py       冒烟测试（SPEC 第 8 节）
└── instance/shop.db        运行时生成，不提交
```

## 端点一览

| 方法 | 路径 | endpoint |
| --- | --- | --- |
| GET | `/` | `main.index` |
| GET | `/categories` | `categories.list` |
| GET,POST | `/categories/new` | `categories.new` |
| GET,POST | `/categories/<int:cid>/edit` | `categories.edit` |
| POST | `/categories/<int:cid>/delete` | `categories.delete` |
| GET | `/products` | `products.list` |
| GET,POST | `/products/new` | `products.new` |
| GET,POST | `/products/<int:pid>/edit` | `products.edit` |
| POST | `/products/<int:pid>/delete` | `products.delete` |
| GET | `/lists` | `lists.list` |
| GET,POST | `/lists/new` | `lists.new` |
| GET | `/lists/<int:lid>` | `lists.detail` |
| GET,POST | `/lists/<int:lid>/edit` | `lists.edit` |
| POST | `/lists/<int:lid>/items` | `lists.add_item` |
| POST | `/lists/<int:lid>/items/<int:iid>/toggle` | `lists.toggle_item` |
| POST | `/items/<int:iid>/delete` | `lists.delete_item` |
| POST | `/lists/<int:lid>/done` | `lists.mark_done` |
| POST | `/lists/<int:lid>/delete` | `lists.delete` |
| GET | `/expenses` | `expenses.list` |
| GET,POST | `/expenses/new` | `expenses.new` |
| GET,POST | `/expenses/<int:eid>/edit` | `expenses.edit` |
| POST | `/expenses/<int:eid>/delete` | `expenses.delete` |

## 模板上下文（后端已按下表传参）

- `index.html`：`month_total`(Decimal) `month_count`(int) `recent_expenses` `active_lists`
- `categories/list.html`：`items`（每项带 `product_count`）
- `categories/form.html`：`obj` `action_url` `submit_label`
- `products/list.html`：`items` `categories` `current_category_id`
- `products/form.html`：`obj` `action_url` `submit_label` `categories`
- `lists/list.html`：`items`（每项带 `item_count` `done_count`）
- `lists/form.html`：`obj` `action_url` `submit_label`
- `lists/detail.html`：`obj` `products` `total`
- `expenses/list.html`：`items` `month` `month_total` `months`
- `expenses/form.html`：`obj` `action_url` `submit_label` `categories` `products`
- `404.html`：无额外变量

额外便利：注册了 Jinja 过滤器 `money`，模板里可写 `{{ obj.total|money }}` 得到 `¥12.34`
（非 SPEC 要求，可选使用）。

## 删除清单条目时的来源页

`POST /items/<iid>/delete` 需要知道「来源清单列表或详情」。表单可带隐藏域
`back`，取值 `list`（回 `/lists`）或 `detail`/留空（回该条目所属清单详情）。缺省回详情。

## 协作方式

协作规则见 [CONTRIBUTING.md](CONTRIBUTING.md)：本仓库用 issue + PR 推进，`main` 只接受经 CI 通过的 PR 合入。
fork 成员与 AI 编码代理的硬约束（含无写权限时的 fork 流程）见 [AGENTS.md](AGENTS.md)。

- issue 先行：缺陷 / 功能建议 / 任务三种模板，写清目标与验收标准；没有 issue 不开 PR。
- 分支：`feat/…`、`fix/…`、`chore/…`、`docs/…`，禁止直接在 `main` 上改动。
- 提交：Conventional Commits（`feat` / `fix` / `docs` / `refactor` / `test` / `chore` 前缀必填），一次提交只做一件事。
- PR：一 issue 一 PR，正文首行 `Closes #N`，合并方式 squash，合并后自动删除分支。
- 门禁：CI 的 `test` 检查（`.github/workflows/ci.yml`）必须为绿色；第二位协作者加入后由 Lead 开启「至少 1 人批准」，当前批准数为 0。
- 不提交 `instance/`、`.venv/`、`.env`、`__pycache__`；契约改动先改 `SPEC.md` 再改代码。

[![](https://img.shields.io/badge/powered_by-dsh-4D6BFE?style=flat-square&logo=deepseek&logoColor=white)](https://github.com/deepseek-ai/deepseek-harness)

## 许可证

本项目以 [MIT 协议](LICENSE) 发布，Copyright (c) 2026 Han-Haocheng。提交 PR 即表示你同意以同一协议授权你的贡献。

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 环境变量

| 变量 | 是否必填 | 说明 |
| --- | --- | --- |
| `SECRET_KEY` | 生产必填（本地调试可缺省） | 会话签名密钥。未设置且未开启调试时，`create_app()` 直接抛 `RuntimeError`；调试开启时退回固定开发密钥并打一条警告。生成：`python -c "import secrets;print(secrets.token_hex(32))"` |
| `DATABASE_URL` | 可选 | 数据库连接串，默认 `sqlite:///shop.db`（即项目根下 `instance/shop.db`） |
| `HOST` | 可选 | `python run.py` 的监听地址，默认 `127.0.0.1`；只在本机使用时不要改成 `0.0.0.0` |
| `PORT` | 可选 | 监听端口，默认 `5000` |
| `FLASK_DEBUG` | 可选 | 调试开关，**默认关闭**；只有 `1`/`true`/`yes`（忽略大小写）视为开启，`0`/`false`/`no`/未设置都关闭。生产环境必须保持关闭：Werkzeug 调试器一旦对外可访问就等于任意代码执行 |

模板见 [.env.example](.env.example)，复制后按需修改：

```bash
cp .env.example .env    # .env 已被 .gitignore 忽略，不要提交
```

- `flask --app run:app run` 与 `flask --app run:app init-db` 会自动加载项目根目录的 `.env`（依赖 `python-dotenv`），因此建库前也需先有 `SECRET_KEY` 或设 `FLASK_DEBUG=1`。
- 直接 `python run.py` 不读 `.env`，请先 `export SECRET_KEY=...` 或 source 该文件。
- 报错文案本身给了两条出路：配置真实密钥，或本地开发时设 `FLASK_DEBUG=1`（会使用固定开发密钥并打警告）。
## 数据库迁移

表结构用 Alembic（Flask-Migrate）管理，脚本在 `migrations/versions/`，基线是 v1 现状的 5 张表。
日常三条命令：

```bash
flask --app run:app db upgrade            # 升级到最新版本（已有库/生产库的唯一升级方式）
flask --app run:app db migrate -m '说明'   # 改完 app/models.py 后生成迁移脚本，人工检查后再提交
flask --app run:app db current            # 看当前库的版本，应显示 <revision> (head)
```

- `init-db` 是**开发重置**：drop_all + create_all + 示例数据，并把库 stamp 到 head（**会清空数据**）。
- 生产环境**只用 `db upgrade`**，不要执行 `init-db`：它重建表，等于清库。
- 早已存在但还没有 `alembic_version` 表的旧库（baseline 之前建的），先 `flask --app run:app db stamp head`
  把它标记为基线，再走 `db upgrade`；直接 upgrade 会因为「表已存在」失败。


