> 读者：正卡在一条报错上、需要立刻恢复的人（含 AI 编码代理）。
> 职责：按报错原文索引的排查步骤——每条给「现象原文 → 原因 → 修复 → 验证」。
> 不写：契约内容（链接 SPEC.md）、迁移原理与备份（链接 database.md）、环境搭建全流程（链接 development.md）。
> 权威来源：代码里的报错文案（app/config.py、app/__init__.py、migrations/versions/8c1f4b7d9e02_v2_user_id_on_business_tables.py）与 2026-11-25 在 Python 3.14 / Flask 3.1 下的实测输出。

# 报错排查

## 一 怎么用

先在下面的索引里搜你**看到的那一行**（报错原文逐字来自代码，可直接当关键词），再跳到对应小节。

| 你看到的片段 | 去哪节 |
| --- | --- |
| `未设置 SECRET_KEY` | 第二节 |
| `no such table: users` / `no such table: categories` | 第三节 |
| `表单已过期，请刷新页面重试` | 第四节 |
| `flask db current` 报错或什么都不显示 | 第五节 |
| `用户名或密码不正确` / demo 账号登不进去 | 第六节 |
| `Address already in use` / `Port ... is in use by another program` | 第七节 |

通用前提：本章所有命令都在**仓库根目录**执行，用 `.venv/bin/` 前缀；换目录会导致 `.env` 找不到。

## 二 `未设置 SECRET_KEY`

现象（`python run.py`、`flask --app run:app ...` 都会这样，栈底就是这行）：

```text
RuntimeError: 未设置 SECRET_KEY：请在 .env 或环境变量里配置（参考 .env.example），或设置 FLASK_DEBUG=1 用于本地开发
```

原因：`create_app()` 在合并配置后立刻调用 `resolve_secret_key`，此时 `SECRET_KEY` 既没有环境变量、也没有 `.env` 提供，且 `FLASK_DEBUG` 未开启。它发生在建目录、连库之前，所以看不到数据库相关报错是正常的。

修复（任选一条）：

```bash
# A. 建 .env 并填真实密钥（推荐）
cp .env.example .env
python -c "import secrets;print(secrets.token_hex(32))"   # 输出填进 SECRET_KEY=

# B. 只给这一条命令临时密钥
SECRET_KEY=dev .venv/bin/flask --app run:app db heads

# C. 本地开发改用固定开发密钥（会打一条警告，生产禁用）
FLASK_DEBUG=1 .venv/bin/python run.py
```

验证：

```bash
.venv/bin/flask --app run:app db heads      # 应输出 8c1f4b7d9e02 (head)
```

避坑：`.env` 只在**当前工作目录及其上级**里查找（`find_dotenv(usecwd=True)`），所以在 `/tmp` 或 `app/` 里执行命令等于没有 `.env`；`.env` 也不会覆盖已存在的环境变量（没有 `override=True`），shell 里 `export SECRET_KEY=`（空值也算存在但为空）会挡住 `.env` 的值。机制细节见 [./development.md](./development.md) 第四节。

## 三 `no such table: users`

现象（栈底长这样，SQL 语句主体是查 `users`）：

```text
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: users
[SQL: SELECT users.id AS users_id, users.username AS users_username, ... FROM users WHERE users.username = ? ...]
```

原因（按可能性排序）：

1. 还没建库就启动了应用或跑了 CLI——`instance/shop.db` 不存在或只有空文件。
2. 在**真正的 v1 库**上直接跑 `init-admin`：v1 没有 `users` 表，而 `init-admin` 只建账号、不建表。
3. `DATABASE_URL` 指向了另一个空库文件（例如临时路径、相对路径解析到了别处）。

修复：

```bash
# 情况 1 / 3（本地开发，可丢数据）：重建库并灌示例数据
.venv/bin/flask --app run:app init-db

# 情况 2（v1 存量库，不能丢数据）：先只升到 users 表那一版，再建账号，再升到 head
.venv/bin/flask --app run:app db upgrade 0554acb803f0
.venv/bin/flask --app run:app init-admin --username legacy --password '至少8位密码'
.venv/bin/flask --app run:app db upgrade
```

验证：

```bash
.venv/bin/flask --app run:app db current      # 应输出 8c1f4b7d9e02 (head)
sqlite3 instance/shop.db '.tables'            # 应包含 users 与 5 张业务表
```

升级顺序的完整说明与备份做法见 [./database.md](./database.md) 第五、七节。

## 四 `表单已过期，请刷新页面重试`

现象：页面顶部出现这条 danger 提示，并被重定向回来源页（跨站来源或没有来源时回首页）。

```text
表单已过期，请刷新页面重试
```

原因：`CSRFProtect` 校验失败——POST 携带的 CSRF 隐藏域缺失、过期，或与当前会话里的 token 不匹配（字段名见 [SPEC.md](../SPEC.md) 第 8 节）。常见触发方式：

- 页面开着很久（会话 7 天到期）或重启/清空过会话后再提交。
- 换了 `SECRET_KEY`（包括 `.env` 里改了值、有时有 `.env` 有时没有），旧会话签名失效。
- 用 `curl` / Postman 直接发 POST，没先 `GET` 页面取 token。
- 从别的站点（或从 `file://`）打开表单再提交。

修复：

1. 刷新表单页重新取一次 token，再提交一次（绝大多数情况到此为止）。
2. 仍反复失败时，确认这次运行的 `SECRET_KEY` 与生成页面时一致：`.env` 与 shell 变量不要同时给两个值；改完密钥要重启进程（配置在 import 期只读一次）。
3. 不要为了「跑通」关掉 CSRF：测试里放开 CSRF 只在 `tests/conftest.py` 的夹具中，且 CSRF 行为由 [tests/test_csrf.py](../tests/test_csrf.py) 单独验证。

验证：浏览器开发者工具里看 POST 的 Form Data 里带着 CSRF 隐藏域，提交后返回 302 且页面出现业务成功的 success 提示。

## 五 `flask db current` 的三种「报错」

`db current` 失败有三种完全不同的形态，先分类再动手。

### 5.1 栈底是 `未设置 SECRET_KEY`

说明命令根本没到 Alembic——`--app run:app` 要导入应用，而应用起不来。按第二节处理。

### 5.2 `Can't locate revision identified by '<revision>'`

```text
ERROR [flask_migrate] Error: Can't locate revision identified by 'deadbeef1234'
```

原因：库里的 `alembic_version` 表记录了一个本地不存在的版本号（`migrations/versions/` 里没有这个 revision）。常见于换了分支/拉错了迁移目录，或有人手工改过这行。

修复：

```bash
sqlite3 instance/shop.db "select * from alembic_version;"    # 先看它记的是什么
.venv/bin/flask --app run:app db heads                       # 再看本地真实 head
```

- 记录值与本地某个迁移文件名（前缀）对不上、且你确认是脏数据：把它改回真实 head（`update alembic_version set version_num='8c1f4b7d9e02';`），或从备份恢复。
- 记录值是**别的分支**的迁移：先 `git log -- migrations/versions/` 确认丢失了哪个脚本，找回脚本比改库安全。
- 改之前先备份库（见 [./database.md](./database.md) 第七节）。

### 5.3 不报错，但只有两行 INFO、没有版本

```text
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
```

这是「库存在但没有任何版本记录」的正常表现，不是崩溃。原因：库是在 Alembic 之外建的（手工 `create_all`、老版本 `init-db`、或从别处拷来的 `.db`），没有 `alembic_version` 表。

修复：

```bash
# 结构已经是当前模型的样子 → 直接标记到 head
.venv/bin/flask --app run:app db stamp head

# 结构停留在 v1 → 走上节「v1 库升级到 v2」的四步，不要 stamp
```

判断依据：`sqlite3 instance/shop.db "PRAGMA table_info(categories);"` 里有没有 `user_id` 列。

## 六 demo 账号与登录失败

本地演示账号由 `init-db` 建立：用户名 `demo`、密码 `demo1234`、显示名「演示用户」，示例数据全部挂在该账号名下（`init-db` 的输出里有这句提示）。**它只用于本地演示，上线前必须删除或改密。**

登录失败时页面统一显示（不区分用户不存在/密码错误/账号停用）：

```text
用户名或密码不正确
```

按顺序排查：

1. 库不是 `init-db` 建的 → demo 账号不存在。重建：

   ```bash
   .venv/bin/flask --app run:app init-db      # 会清空现有数据
   ```

2. 只想加账号、不想清库 → 用 `init-admin`（同名已存在时报错退出，不覆盖原密码）：

   ```bash
   .venv/bin/flask --app run:app init-admin --username me --password '至少8位密码' --display-name 我
   ```

3. 刚才连续输错 5 次以上 → 同一用户名在 60 秒内会被一律按失败处理（内存限流）。等窗口过去，或重启进程（限流状态在内存里，重启即清空）。

验证：

```bash
sqlite3 instance/shop.db "select id, username, is_active from users;"
.venv/bin/python run.py     # 打开 http://127.0.0.1:5000 ，用 demo / demo1234 登录
```

登录规则本身（密码最短长度、限流窗口、回跳限制）以 [SPEC.md](../SPEC.md) 第 4 节为准，本文档不复制。

## 七 端口被占用

现象（Werkzeug 直接以退出码 1 结束）：

```text
Address already in use
Port 5000 is in use by another program. Either identify and stop that program, or start the server with a different port.
```

原因：上一次的 `python run.py` 还在跑（调试重载会留子进程），或别的服务占了 `PORT`。

修复：

```bash
# 谁占了 5000
ss -ltnp 'sport = :5000'          # 或 lsof -i :5000

# 换端口起服务（HOST/PORT 只对 python run.py 生效）
PORT=8080 .venv/bin/python run.py
```

验证：终端出现 `Running on http://127.0.0.1:8080`，浏览器能打开新端口。别忘了改浏览器地址；端口不写进 `.env` 时默认 5000。

## 八 附：页面莫名其妙跳到登录页

看不到报错，但访问业务页时被 302 到 `/login?next=...`，说明当前会话没有有效用户（未登录、会话过期、用户被删或 `is_active` 为假）。按第六节确认账号存在并重新登录即可；这是设计行为，不是故障，规则见 [SPEC.md](../SPEC.md) 第 4 节。
