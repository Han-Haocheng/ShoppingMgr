# AGENTS.md —— 本仓库的项目提示词（人机共读）

> 本文件是给「本仓库与所有 fork 的贡献者、以及被指派的 AI 编码代理」的硬约束。开 PR 前把第 1、2、5 节读完即可避免绝大多数打回。
>
> **权威顺序**：`SPEC.md`（产品契约）＞ `AGENTS.md`（本文件，硬约束）＞ `CONTRIBUTING.md`（流程说明）＞ `README.md`（使用说明）。
> 三者冲突时按此顺序取上者，并在 PR 里写明你如何处理冲突；本文件自身也只能通过 PR 修改。

## 1 硬性禁止（违反即打回）

1. **禁止直接向 `main` 推送。** main 已开启分支保护（必须 PR、必需检查 `test`、禁 force push、禁删分支、要求线性历史、`enforce_admins` 已开），`git push origin main` 一定会被拒，重试没有意义。
2. **禁止无 issue 的 PR。** 任何改动先开 issue（缺陷 / 功能建议 / 任务模板任选），PR 正文首行写 `Closes #<issue号>`。
3. **禁止一个 PR 做多件事。** 格式化、重构、功能混在一起会打回，请拆成多个 PR。
4. **禁止提交** `instance/`、`.venv/`、`.env`、`__pycache__/`、`*.db`、以及任何真实消费数据与密钥。
5. **禁止无理由新增依赖。** 新增必须在 PR 说明动机、版本约束与替代方案，并同时更新 `requirements.txt`（开发依赖进 `requirements-dev.txt`）。
6. **禁止先改代码再改契约。** 涉及路由、数据模型字段、模板上下文、错误处理等对外契约的改动，先在同一个 PR 里改 `SPEC.md`，再改实现。
7. **禁止绕过门禁**：不许用 `gh pr merge --admin`、不许临时关分支保护、不许改 `.github/workflows/ci.yml` 让检查变松。
8. **禁止在仓库里留凭据与内网信息**：token、Cookie、私有镜像地址、内网 IP 都不要出现在代码、提交信息与 issue 里。

## 2 硬性要求

- **分支从最新 `main` 切出**，命名 `<type>/<issue号>-<简短英文>`，`type` 取 `feat` / `fix` / `docs` / `refactor` / `test` / `chore` / `ci`。例：`feat/12-list-total`、`docs/3-agents-md`。
- **提交信息走 Conventional Commits**：`<type>(<scope>): <描述>`，前缀必填、描述可中文，一次提交只做一件事，例 `fix(lists): 空名称时回到详情页并提示`。
- **合并前本地必须跑通测试**，并把命令与关键输出贴进 PR：

  ```bash
  .venv/bin/python -m pytest -q          # 期望：8 passed（新增用例后数字变大）
  ```
- **PR 标题**与 issue 呼应，单独看也要能懂；**正文**按 `.github/PULL_REQUEST_TEMPLATE.md` 填（变更说明 / 关联 issue / 影响面与回滚 / 本地验证 / 检查清单）。
- **UI 一律中文**；金额一律 `Decimal` 两位小数（模板里用 `money` 过滤器或 `%.2f`）；日期 `YYYY-MM-DD`。
- **改行为必带测试**：新增或修改 `app/` 下任何逻辑，`tests/` 里要有一条能失败也能通过的断言。

## 3 仓库速览

| 项 | 内容 |
| --- | --- |
| 定位 | 单用户本地记账 + 购物清单小工具，服务端渲染（无前端框架）、中文界面 |
| 技术栈 | Python 3.14、Flask 3.1、Flask-SQLAlchemy 3.1、Flask-Migrate 4、Jinja2、Bootstrap 5.3（本地 vendor）、SQLite |
| 入口 | `run.py` 导出 `app`；工厂 `app/__init__.py` 的 `create_app()`；CLI `init-db`（重建+种子）/`seed-db`（只造数据） |
| 数据 | `instance/shop.db`（已 gitignore，首次访问前必须 `init-db`） |
| 契约 | `SPEC.md`：5 张表字段、22 条路由与 endpoint 名、模板上下文、表单字段名 |

| 路径 | 归属内容 |
| --- | --- |
| `app/models.py` | 5 个模型与派生属性（`subtotal` / `total`） |
| `app/utils.py` | 解析与格式化（`parse_decimal` / `parse_date` / `fmt_money`）、种子数据 |
| `app/blueprints/` | `main` `categories` `products` `lists` `expenses` 五个蓝图 |
| `app/templates/` | `base` `index` `404` + 四个模块的 `list`/`form` + `lists/detail` |
| `tests/` | `conftest.py`（app/client fixture）+ `test_smoke.py` |
| `.github/` | issue 表单、PR 模板、CI（作业名 `test`）、CODEOWNERS |

## 4 本地开发（五步）

```bash
python -m venv .venv                                          # 1 建环境（Python 3.14）
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt   # 2 装依赖
.venv/bin/flask --app run:app init-db                         # 3 建库（会清空现有数据）
.venv/bin/python run.py                                       # 4 起服务 http://127.0.0.1:5000
.venv/bin/python -m pytest -q                                 # 5 跑测试
```

`init-db` 会 `drop_all + create_all`，只想补示例数据用 `seed-db`。

## 5 提交流程（两条路径，按你有没有写权限选）

### 5A 有写权限的协作者

```bash
git switch main && git pull --ff-only        # 1 取最新主线（不要 rebase 别人的提交）
git switch -c feat/12-list-total             # 2 切分支
# …改代码 → 本地 pytest 全绿 → 提交…
git add -A && git commit -m 'feat(lists): 详情页显示合计金额'
git push -u origin feat/12-list-total        # 3 推分支（不是 main）
gh pr create --base main --title 'feat(lists): 详情页显示合计金额' --body 'Closes #12 …'   # 4 开 PR
gh pr checks --watch                         # 5 等 test 绿
# 6 由维护者点击 Squash and merge；合并后分支自动删除、issue 自动关闭
```

### 5B fork 成员（没有写权限）

1. Fork 本仓库，在**你自己的 fork** 上把 `main` 与上游同步，然后从上游最新 `main` 切出分支（分支名同上）。
2. 改动推到你 fork 的分支（`git push -u origin feat/12-list-total`，这里 `origin` 指你的 fork）。
3. 向**上游** `main` 开 PR：GitHub 页面选 `base repository: Han-Haocheng/ShoppingMgr`、`base: main`、`head: <你的账号>:feat/12-list-total`；或用命令 `gh pr create --repo Han-Haocheng/ShoppingMgr --base main --head <你的账号>:feat/12-list-total`。
4. **首次贡献者的工作流需要维护者批准才会跑**：PR 页面上会出现 `Approve workflows to run`（或 Merge status 面板里的等待批准提示）。批准前 `test` 一直是待跑状态，不是失败；等待超过 30 天会过期并标记为失败。
5. 合并只能由有写权限的人做（squash），你不需要也不应该请求 force push 权限。

fork PR 的两条硬事实（决定了你该怎么写 PR）：来自 fork 的工作流里 `GITHUB_TOKEN` 只有只读权限，**secrets 不会传入**；`pull_request` 等事件发到的是 base 仓库。所以：**不要在 PR 里新增依赖 secrets 的 CI 步骤**，那类改动请先开 issue 说明，由维护者在主线处理。

依据（GitHub 官方文档）：<https://docs.github.com/en/actions/managing-workflow-runs/approving-workflow-runs-from-public-forks>、<https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows>（Forked repositories 一节）。

## 6 PR 会被打回的情形

| 现象 | 原因 | 怎么改 |
| --- | --- | --- |
| `test` 红 | 测试失败或装依赖失败 | 本地 `pytest -q` 复现后修，别跳过或放宽断言 |
| 提示必须更新分支 | `test` 检查是 strict，分支落后于 main | PR 页点 `Update branch` 或本地 merge main 后再推 |
| 正文没有 `Closes #N` | 无法自动关 issue、无法追溯 | 补首行 |
| 一个 PR 里改了无关文件 | 夹带格式化/重构 | 拆 PR |
| 改了契约没改 `SPEC.md` | 实现与契约分叉 | 同 PR 补 `SPEC.md` |
| 新增依赖没更新 `requirements.txt` | 别人装不上 | 补清单与理由 |
| 提交里有 `instance/`、`.venv/` | `.gitignore` 之外被强制 add | `git rm -r --cached` 后重提 |
| 对话未解决 | 分支保护要求所有评论 resolved | 逐条回复并标记解决 |

## 7 门禁细节

- 工作流 `.github/workflows/ci.yml`：`name: CI`，push `main` 与所有 PR 触发，**作业 id 与 name 都是 `test`**（分支保护按这个上下文名匹配，改名会让保护失配）。
- 步骤：checkout → setup-python 3.14（pip 缓存）→ 装两份 requirements → `python -m pytest -q`。
- 本地查门禁状态：`gh pr checks <PR号> --watch`；查失败原因：`gh run view <run-id> --log-failed`。
- 批准数当前为 **0**（仓库只有 1 名维护者，GitHub 不允许自批）。第二位协作者加入后由维护者调到 1；届时所有 PR 都需要 1 人批准才能合并。

## 8 给 AI 编码代理的附加约定

- 只改 issue 描述范围内的文件；发现必须越界，先在 PR 描述里说明并开新 issue，不要顺手改。
- **不要自行**：`git push` 到 `main` 或 upstream、合并 PR、修改分支保护、改 `.github/workflows/ci.yml` 的门禁强度、执行 `git rebase` 改写已推送历史。
- 改任何 `app/` 逻辑前先读 `SPEC.md` 对应章节；实现与 SPEC 冲突时**以 SPEC 为准**，并把偏差写进 PR 描述。
- 遇到测试红了：先定位到具体断言，不许 `pytest.skip`、不许放宽断言、不许删用例让 CI 变绿。
- 交付时按「改了什么 / 验证命令与输出 / 未做与风险」三段落汇报，不要只贴结论。

## 9 修改本文件

本文件是项目提示词，修改也必须走 PR：标题 `docs: ...`，在 PR 描述里写清「改了哪一条规则、为什么、影响谁」。不要为了让自己这次的 PR 过审而放宽规则。
