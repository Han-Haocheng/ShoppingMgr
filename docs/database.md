> 读者：需要建库、灌示例数据、改模型生成迁移、升级已有库或做备份的人。
> 职责：三条 CLI 的语义差别、迁移命令与版本链、v1→v2 升级路径、SQLite DDL 非事务这条已知限制、备份与恢复。
> 不写：表字段与关系（链接 SPEC.md 第 3 节）；`SECRET_KEY` 报错处理（见 troubleshooting.md）；分支与提交流程（AGENTS.md、CONTRIBUTING.md）。
> 权威来源：app/__init__.py 的 CLI 定义、migrations/versions/ 下的迁移脚本、tests/test_migrations.py；契约见 SPEC.md 第 3、10 节。

# 数据库与迁移

## 一 库在哪

- 默认路径是项目根的 `instance/shop.db`（`instance/` 已被 `.gitignore` 忽略，运行时自动创建）。
- 连接串可用 `DATABASE_URL` 覆盖，默认 `sqlite:///shop.db`；相对路径由 Flask-SQLAlchemy 解析到应用的 `instance_path`。
- 首次访问业务页面前必须先建库，否则会看到 `no such table`（处理见 [./troubleshooting.md](./troubleshooting.md)）。

## 二 三条自带 CLI 的语义

定义在 `app/__init__.py` 的 `_register_cli`，都以 `flask --app run:app` 为前缀。

| 命令 | 做什么 | 动表结构 | 会丢数据 |
| --- | --- | --- | --- |
| `init-db` | `drop_all` + `create_all` + 把库 `stamp` 到迁移 head + 写入示例数据（示例数据挂在 `demo` 账号下） | 是（重建） | **是**：先清空再建 |
| `seed-db` | 只写示例数据；该用户名下已有品类时跳过 | 否 | 否 |
| `init-admin` | 只建一个账号，供升级存量库时当归属用户 | 否 | 否 |

`init-db` 成功输出（真实文本）：

```text
演示账号：demo / demo1234（仅本地演示用，上线前必须删除或改密）
数据库已重建：品类 5 / 商品 8 / 清单 1 / 条目 3 / 消费 6
```

`seed-db` 在已有数据时输出：

```text
库中已有数据，跳过写入。
```

`init-admin` 的校验与失败退出（均为退出码 1，错误打到 stderr）：

```text
密码至少 8 位。
密码不能与用户名相同。
用户名最长 60 个字符。
用户“X”已存在（id=N），未做改动。
```

三点必须记住：

1. `init-db` 是**开发重置**，不是升级手段；它建完表必须 `stamp` 到 head，否则后续 `db upgrade` 会重放基线并在「表已存在」上失败。
2. 生产库只用 `db upgrade`，永远不跑 `init-db`。
3. `init-admin` 要求 `users` 表已存在——在真正的 v1 库上直接跑会报 `no such table: users`，正确顺序见第五节。

## 三 迁移命令

```bash
# 日常三条
.venv/bin/flask --app run:app db upgrade            # 升到最新版本
.venv/bin/flask --app run:app db migrate -m '说明'   # 改完 app/models.py 后生成脚本，人工检查再提交
.venv/bin/flask --app run:app db current            # 看当前版本，正常输出 <revision> (head)

# 辅助
.venv/bin/flask --app run:app db heads              # 最新 head，应只有一行
.venv/bin/flask --app run:app db stamp head         # 把「已建好但没有 alembic_version」的库标到 head
.venv/bin/flask --app run:app db downgrade          # 回退一个版本（要确认脚本里 downgrade 可逆）
```

`db current` 正常输出（末尾那行才是版本）：

```text
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
8c1f4b7d9e02 (head)
```

这些命令都要 `SECRET_KEY`（`--app run:app` 会导入 `run` 并建应用），缺了会先报 `未设置 SECRET_KEY`，见 [./development.md](./development.md) 第四节与 [./troubleshooting.md](./troubleshooting.md) 第一节。

## 四 版本链

迁移脚本在 `migrations/versions/`，当前 head 是 `8c1f4b7d9e02`，链是线性的：

| 顺序 | revision | 内容 |
| --- | --- | --- |
| 1 | `b4ed9413adcc` | 基线：v1 现状的 5 张业务表（无 `user_id`） |
| 2 | `0554acb803f0` | 新建 `users` 表 |
| 3 | `8c1f4b7d9e02` | 5 张业务表加 `user_id` 并回填，换唯一约束、放开 `products.barcode` 为可空 |

每个脚本头部都写了它守的是 [SPEC.md](../SPEC.md) 第 10 节的哪条规则；读脚本比读文档更准。

## 五 v1 库升级到 v2

存量 v1 库（有数据、没有 `user_id`）必须按下面四步走，**不能**直接 `init-admin` 再 `db upgrade`：

```bash
# 1. 先只升到 users 表那一版（此步只建表，不动业务表）
.venv/bin/flask --app run:app db upgrade 0554acb803f0

# 2. 现在 users 表存在了，建一个归属账号
.venv/bin/flask --app run:app init-admin --username legacy --password '至少8位密码' --display-name 老用户

# 3. 升到 head：5 张业务表加 user_id 并把存量数据回填到 id 最小的用户
.venv/bin/flask --app run:app db upgrade

# 4. 验证：应输出 head，且业务表的 user_id 都等于该账号的 id
.venv/bin/flask --app run:app db current
sqlite3 instance/shop.db "select 'categories', count(*), user_id from categories group by user_id;"
```

规则与坑：

- **存量数据统一归属到 id 最小的用户**（第 2 步只建了一个账号时，就是它）。
- 如果库里有业务数据但 `users` 表为空，第 3 步会**直接失败且不留半成品**，报错里带着要你执行的命令：

  ```text
  RuntimeError: 回填 user_id 需要至少一个归属用户，但 users 表为空。请先运行 flask --app run:app init-admin --username X --password Y 建好账号，再执行迁移。
  ```

- 回填时 `products.barcode` 的空串会一并改成 `NULL`，否则新的「同用户内条码唯一」约束会在第二行空条码上撞车。
- 前置检查放在所有 DDL 之前，失败时库还停在 `0554acb803f0`，不会出现「删了列却没回填」的中间态；这一点由 [tests/test_migrations.py](../tests/test_migrations.py) 的用例 (g) 守着。
- 全新空库不需要归属用户，直接 `db upgrade` 也能建出全表。

升级前先备份（下一节），升级后用 `db current` + 一条 `count` 查询验收。

## 六 SQLite 的 DDL 非事务：一条已知限制

每次跑迁移都会看到这行，它不是警告噪音，而是事实声明：

```text
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
```

含义与后果：

- SQLite 的 `ALTER TABLE` / `CREATE TABLE` 等 DDL 不在事务里回滚，Alembic 因此按「每条 DDL 立即生效」处理。
- 一个迁移脚本里若有多条 DDL，中途失败（例如回填时违反约束、被中断）**可能留下改了一半的表结构**，且 `alembic_version` 还停在上一版。
- 本项目的对策有三条：把「能不能做」的前置检查放在所有 DDL 之前；加列一律走 `op.batch_alter_table`（它按新结构重建表再换名，避免 SQLite 不支持的 `ALTER COLUMN`）；每个 `upgrade` 都配套写明可逆的 `downgrade`。
- 真遇到中途失败：**从备份或临时库重来**，不要手工 `ALTER TABLE` 去补，也不要直接删 `alembic_version` 里的行——那会让迁移和实际结构彻底对不上。先 `db current` 看停在哪一版，再决定重跑到哪一步。

## 七 备份与恢复

`instance/` 与 `*.db` 都被忽略，不进版本库；备份放在仓库外或同样被忽略的路径。

```bash
# 方案一：停掉开发服务器后直接复制（最简单，一致性好）
cp instance/shop.db ~/backup/shop-$(date +%Y%m%d-%H%M).db

# 方案二：不停服务时用 SQLite 的在线备份（会正确处理正在写入的情况）
sqlite3 instance/shop.db ".backup '$HOME/backup/shop-$(date +%Y%m%d-%H%M).db'"
```

恢复与验收：

```bash
cp ~/backup/shop-20261125-2000.db instance/shop.db
.venv/bin/flask --app run:app db current    # 应输出 8c1f4b7d9e02 (head) 或该备份对应的版本
```

要做「结构变更前」的保险，光有数据备份不够：连同迁移版本一起记下来（`db current` 的输出），否则恢复后不知道该不该再 `db upgrade`。

## 八 相关文档

- 建库后在页面里操作需要用账号登录：demo 账号与登录失败见 [./troubleshooting.md](./troubleshooting.md) 第五节。
- 报错原文索引（`no such table: users`、`Can't locate revision identified by ...`、`flask db current` 没有任何版本行）见 [./troubleshooting.md](./troubleshooting.md) 第二、四节。
- 命令背后的环境变量与 `.env` 加载规则见 [./development.md](./development.md) 第三、四节。
