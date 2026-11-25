# 贡献指南（CONTRIBUTING）

本文件是本仓库的协作规则：分支、提交、PR 与门禁都以这里为准。流程细节与接口契约以 [SPEC.md](SPEC.md) 为唯一权威。

给 fork 成员与 AI 编码代理看的硬约束（禁止项、两条提交流程、被打回情形）集中在 [AGENTS.md](AGENTS.md)，动手前请先读。

## 1 仓库与技术栈速览

- 项目：ShoppingMgr（购物管家），单用户本地记账 + 购物清单小工具，服务端渲染、中文界面。
- 技术栈：Python 3.14 + venv（`.venv`）；Flask 3.1.x；Flask-SQLAlchemy 3.1.x；Flask-Migrate 4.x；python-dotenv；SQLite（`instance/shop.db`）；pytest（开发依赖）。
- 结构：`run.py` 入口导出 `app`；`app/` 内 `models.py`、`utils.py`、`blueprints/`（main / categories / products / lists / expenses）、`templates/`、`static/`；测试在 `tests/`。
- 权威顺序：`SPEC.md`（契约）＞ [AGENTS.md](AGENTS.md)（硬约束，人机共读）＞ 本文件（流程）＞ 代码注释。

## 2 本地开发五步

```bash
# 1. 建虚拟环境
python -m venv .venv

# 2. 装依赖（运行时 + 开发）
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

# 3. 建库并写入示例数据（会清空现有数据）
.venv/bin/flask --app run:app init-db

# 4. 起开发服务器（http://127.0.0.1:5000）
.venv/bin/python run.py

# 5. 跑测试
.venv/bin/python -m pytest -q
```

说明：`instance/` 已被忽略，数据库不会进版本库；`init-db` 会 drop 重建，只想补示例数据用 `seed-db`。

## 3 issue 先行规则

- 没有 issue 不开 PR。任何改动先开 issue（缺陷 / 功能建议 / 任务三种模板任选），写清目标与验收标准。
- issue 里的验收标准要能直接判定：写命令与期望输出，不写「体验更好」这类无法验收的表述。
- 一个 issue 描述一件可独立验收的事；范围太大就先拆。

## 4 分支命名

- 统一前缀：`feat/`（新功能）、`fix/`（缺陷修复）、`chore/`（构建、脚手架、杂务）、`docs/`（文档）。
- 分支名用小写英文加连字符，带上 issue 号，例：`feat/12-list-total`、`fix/18-empty-name`。
- **禁止直接在 `main` 上改**：main 只接受经 PR 合入的提交。

## 5 提交规范

- 采用 Conventional Commits：`<type>(<scope>): <描述>`，type 为必填前缀，取 `feat` / `fix` / `docs` / `refactor` / `test` / `chore` 之一。
- 描述可写中文，例：`feat(lists): 详情页显示合计金额`。
- 一次提交只做一件事：格式化、重构、功能改动不要混在同一个提交里。
- 提交信息里不要写「fix bug」这类无法追溯的表述；关联 issue 号写在 PR 正文，不强制写在提交里。

## 6 PR 规则

- 一个 issue 对应一个 PR；不要在一个 PR 里夹带无关改动。
- **PR 正文首行必须是 `Closes #N`**，合并时自动关闭对应 issue；缺这一行不予合并。
- 标题与 issue 呼应，建议沿用 `<type>(<scope>): <描述>`，让标题单独看也能懂。
- 合并方式统一 **squash**，合并后自动删除分支（仓库设置里已开启 `Automatically delete head branches`）。
- 正文按 `.github/PULL_REQUEST_TEMPLATE.md` 填写：变更说明、关联 issue、影响面与回滚、本地验证（命令 + 关键输出）、检查清单。

## 7 评审与门禁

- CI 的 **test** 检查（`.github/workflows/ci.yml` 的 job `id` 与 `name` 均为 `test`）必须为绿色才能合并；红了先修，不要跳过或放宽断言。
- 第二位协作者加入后，由 Lead 在分支保护里开启「Require approvals: 至少 1 人批准」。**当前启用批准数为 0**（单人阶段只要求 CI 绿），规则一旦变更由 Lead 更新本节。
- 评审看两件事：是否符合 `SPEC.md`，是否带可复现的本地验证输出。

## 8 不要提交的东西

- `instance/`（含 `shop.db` 等运行时数据库）
- `.venv/`
- `.env`（本地环境变量；需要新变量时写进 `README.md` 说明）
- `__pycache__/`、`.pytest_cache/`（编辑器/构建产物同理）

## 9 契约变更

- 涉及路由、数据模型、模板上下文、错误处理等对外契约的改动：**先改 `SPEC.md`**，再改代码，同一个 PR 里体现。
- `SPEC.md` 由 Lead 定稿；协作者如需变更契约，先在 issue 里说明影响面，经 Lead 同意后再动。

## 10 依赖变更

- 新增或升级依赖时，同时更新 `requirements.txt`（开发依赖进 `requirements-dev.txt`）。
- 在 PR 的「变更说明」里写清引入理由、版本约束与替代方案取舍；没有理由的依赖变更不予合并。

## 11 许可证

本项目以 [MIT 协议](LICENSE) 发布。提交 PR 即表示你同意以 MIT 协议授权你的贡献（inbound = outbound）；
如需其它授权安排，请先开 issue 说明，不要直接提交。
