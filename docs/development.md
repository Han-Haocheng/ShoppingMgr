> 读者：第一次在本机把 ShoppingMgr 跑起来的人（含 AI 编码代理），以及换机器后要重新配环境的人。
> 职责：环境准备五步、环境变量全表、CLI 命令、启动与调试、测试命令与调试手段。
> 不写：表字段、路由与模板变量（链接 SPEC.md 第 3/5/7/8 节）；分支、提交与 PR 规则（链接 AGENTS.md 与 CONTRIBUTING.md）。
> 权威来源：run.py、app/config.py、app/__init__.py（CLI 定义）、requirements.txt、requirements-dev.txt；契约见 SPEC.md 第 1、10 节。

# 本地开发

## 一 前置条件

- Python 3.14（`.venv` 里实测为 3.14.10；CI 同样用 3.14）。
- git 与一个可用终端。
- 可选：`sqlite3` 命令行（看库、算备份时用），不带也能跑应用。

## 二 环境准备五步

全程在仓库根目录执行；用 `.venv/bin/xxx` 前缀就不必 `source activate`。

```bash
# 1. 建虚拟环境（Python 3.14）
python3 -m venv .venv

# 2. 装依赖：运行时 + 开发（开发依赖只有 pytest）
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

# 3. 建库并写入示例数据（会清空现有数据；语义见 ./database.md）
.venv/bin/flask --app run:app init-db

# 4. 起开发服务器，打开 http://127.0.0.1:5000
.venv/bin/python run.py

# 5. 另开一个终端跑测试
.venv/bin/python -m pytest -q
```

第 3 步之前要先让 `create_app()` 拿到 `SECRET_KEY`，否则会在导入阶段就失败——做法见下一节与第四节。

`instance/` 目录与其中的 `shop.db` 都已被 `.gitignore` 忽略；删掉 `instance/shop.db` 等于重置数据，重跑 `init-db` 即可。

## 三 环境变量全表

变量由 `app/config.py` 在 **import 期**读一次，之后不再重新求值——所以改了环境变量必须重启进程。共 6 个：

| 变量 | 是否必填 | 默认 | 作用与边界 |
| --- | --- | --- | --- |
| `SECRET_KEY` | 生产必填；本地调试可缺省 | 无（不设即 `None`） | 会话签名密钥。未设置且未开调试时 `create_app()` 直接抛 `RuntimeError`；调试开启时退回固定开发密钥并打一条警告。详见第四节 |
| `DATABASE_URL` | 可选 | `sqlite:///shop.db` | 数据库连接串。相对路径由 Flask-SQLAlchemy 解析到应用的 `instance_path`，即项目根的 `instance/shop.db` |
| `HOST` | 可选 | `127.0.0.1` | **只对 `python run.py` 生效**的监听地址；仅本机使用时不要改成 `0.0.0.0` |
| `PORT` | 可选 | `5000` | 同上，只对 `python run.py` 生效的端口 |
| `FLASK_DEBUG` | 可选 | 关闭 | 只有 `1`/`true`/`yes`（忽略大小写与首尾空白）算开启，其余一律关闭。开启后允许缺 `SECRET_KEY` 并启用调试重载；生产必须关闭 |
| `SESSION_COOKIE_SECURE` | 可选 | 关闭 | 同上的真假值规则；部署到 https 时打开，本地 http 必须关闭（否则浏览器不回传 cookie）。代码在 `app/config.py`，尚未写进 [.env.example](../.env.example) |

模板见 [.env.example](../.env.example)：

```bash
cp .env.example .env
```

## 四 `.env` 与 `SECRET_KEY` 的关系

关键事实：`.env` 在 **导入应用之前**被加载，所以 `python run.py` 与 `flask --app run:app ...` 走的是同一份配置。

- `run.py` 第 12 行调用 `load_dotenv(find_dotenv(usecwd=True))`：从**当前工作目录及其上级**找 `.env`，因此要在项目根目录执行命令。
- 没有用 `override=True`：已经存在的环境变量（shell `export`、CI 注入）始终优先于 `.env`。
- `flask --app run:app` 会先导入 `run`，导入即执行上面的加载，因此两条命令共享同一套变量。
- 生成密钥：`python -c "import secrets;print(secrets.token_hex(32))"`，把输出填进 `.env` 的 `SECRET_KEY=`。

没有 `.env`（或临时换机器）时，三条等价出路：

```bash
# 出路一：命令行临时给一个密钥（只对这一条命令有效）
SECRET_KEY=dev .venv/bin/flask --app run:app db heads

# 出路二：开调试模式，退回固定开发密钥（会打一条警告，仅限本地）
FLASK_DEBUG=1 .venv/bin/python run.py

# 出路三：正经建 .env（推荐）
cp .env.example .env && $EDITOR .env
```

判定时机与文案：`create_app()` 在合并完配置、建目录、连库**之前**就调用 `resolve_secret_key`，所以缺密钥时看到的是干净的 `RuntimeError`，而不是后续一连串导入错误。原文如下（完整排查见 [./troubleshooting.md](./troubleshooting.md) 第一节）：

```text
RuntimeError: 未设置 SECRET_KEY：请在 .env 或环境变量里配置（参考 .env.example），或设置 FLASK_DEBUG=1 用于本地开发
```

`python run.py` 与 `flask --app run:app ...` 都会在导入应用前加载项目根 `.env`：`run.py` 第 12 行执行 `load_dotenv(find_dotenv(usecwd=True))`，第 14 行才 `from app import create_app`，两条命令因此读到同一份配置。`load_dotenv` 默认不 override（环境变量优先于 `.env`）；`FLASK_DEBUG=1` 时允许缺 `SECRET_KEY` 并退回固定开发密钥，同时打一条警告。

## 五 CLI 命令清单

全部以 `flask --app run:app` 为前缀（等价写法 `.venv/bin/flask --app run:app ...`）。命令在 `app/__init__.py` 的 `_register_cli` 里定义。

```bash
# 应用自带命令
.venv/bin/flask --app run:app init-db       # drop_all + create_all + stamp head + 写入示例数据（会清空数据）
.venv/bin/flask --app run:app seed-db       # 只补示例数据，不动表结构
.venv/bin/flask --app run:app init-admin --username X --password Y [--display-name Z]   # 建账号

# Flask-Migrate 提供
.venv/bin/flask --app run:app db upgrade    # 升到最新版本（已有库/生产库的唯一升级方式）
.venv/bin/flask --app run:app db migrate -m '说明'   # 改完模型后生成迁移脚本，人工检查再提交
.venv/bin/flask --app run:app db current    # 看当前库版本，正常输出 <revision> (head)
.venv/bin/flask --app run:app db heads      # 看最新 head（应只有一行）
.venv/bin/flask --app run:app db stamp head # 把已建好的库标记成 head（无 alembic_version 的旧库用）

# Flask 自带
.venv/bin/flask --app run:app routes        # 列出全部路由与 endpoint
.venv/bin/flask --app run:app shell         # 带 app context 的交互式 shell
```

各条命令的语义差别、危险程度与升级顺序见 [./database.md](./database.md)。

`init-db` 成功时的真实输出（含示例数据规模）：

```text
演示账号：demo / demo1234（仅本地演示用，上线前必须删除或改密）
数据库已重建：品类 5 / 商品 8 / 清单 1 / 条目 3 / 消费 6
```

## 六 启动开发服务器

```bash
.venv/bin/python run.py                     # http://127.0.0.1:5000
PORT=8080 .venv/bin/python run.py           # 换端口
FLASK_DEBUG=1 .venv/bin/python run.py       # 开调试重载（改代码自动重启）
```

`run.py` 只做三件事：加载 `.env`、调用 `create_app()` 得到 `app`、在 `__main__` 里 `app.run(...)`。它同时导出 `app`，所以 `flask --app run:app ...` 能发现应用。

数据库是在首次访问前由 `init-db` 建的；没建库直接打开页面会看到 `no such table` 一类报错，处理见 [./troubleshooting.md](./troubleshooting.md) 第二节。

## 七 测试

```bash
.venv/bin/python -m pytest -q                  # 全量：62 passed（2026-11-25 实测，Python 3.14.10）
.venv/bin/python -m pytest -q tests/test_csrf.py           # 单文件
.venv/bin/python -m pytest -q -k "isolation or csrf"       # 按名字挑
.venv/bin/python -m pytest -q -x --lf                      # 上次失败先跑、遇错即停
```

- 测试用**内存 SQLite** 与 Flask test client，不连 `instance/shop.db`，也不发网络请求（夹具见 [tests/conftest.py](../tests/conftest.py)）。
- 迁移与 `run.py` 的行为用**子进程 + 临时库**验证，不会碰开发库（见 [tests/test_migrations.py](../tests/test_migrations.py)、[tests/test_run_env.py](../tests/test_run_env.py)）。
- CI 跑的就是 `.venv/bin/python -m pytest -q` 这一条（去掉 venv 前缀），见 [.github/workflows/ci.yml](../.github/workflows/ci.yml)；门禁与提交流程见 [CONTRIBUTING.md](../CONTRIBUTING.md) 与 [AGENTS.md](../AGENTS.md)。

## 八 调试方式

- **看请求与异常**：`FLASK_DEBUG=1` 启动，出错时浏览器里就是 Werkzeug 调试器（仅限本机；对外暴露等于任意代码执行）。
- **临时断点**：在视图里插 `breakpoint()` 后以 `FLASK_DEBUG=1` 启动；不要提交这行。
- **看路由表**：`.venv/bin/flask --app run:app routes`，确认新增端点真的注册上了。
- **看当前用户**：`.venv/bin/flask --app run:app shell` 里 `from app.models import User; User.query.all()`（shell 里没有请求上下文，`g.user` 不可用）。
- **看数据库**：`sqlite3 instance/shop.db '.tables'`、`select id,username from users;`。
- **看日志**：`python run.py` 直接打印到终端；退回固定开发密钥时的那条警告也在这里。

范围外的规则（分支、提交、PR、门禁）不在本文档重复，见 [AGENTS.md](../AGENTS.md) 与 [CONTRIBUTING.md](../CONTRIBUTING.md)。
