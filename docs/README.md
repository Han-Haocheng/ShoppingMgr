> 读者：第一次进本仓库、需要按角色找到对应文档的贡献者与 AI 编码代理。
> 职责：文档索引、五篇文档的职责边界、权威顺序与「一个事实一个出处」的维护约定。
> 不写：产品契约、协作规则、命令细节——它们各有唯一出处，本文档只负责指路。
> 权威来源：SPEC.md（产品契约）＞ AGENTS.md（硬约束）＞ CONTRIBUTING.md（流程）＞ README.md（使用说明），顺序定义见 AGENTS.md 开头。

# 文档索引

本目录只放「怎么用、怎么改、怎么修」这类工程文档；产品契约仍以仓库根的 [SPEC.md](../SPEC.md) 为唯一准绳。本文件是入口：先在这里定位，再点进专题文档。

## 一 文档地图

| 文档 | 解决什么问题 | 什么时候读 | 不在这里写什么 |
| --- | --- | --- | --- |
| [README.md](../README.md)（仓库根） | 项目定位、功能要点、30 秒上手、文档地图 | 刚进仓库第一眼 | 命令细节、迁移步骤、报错排查 |
| [docs/development.md](./development.md) | 把项目在本机跑起来：venv、环境变量、CLI、启动、测试、调试 | 第一次配环境，或换机器 | 表结构与迁移原理 |
| [docs/architecture.md](./architecture.md) | 代码怎么分层、一次请求怎么走、怎么新增蓝图/模型/模板 | 要在 `app/` 下加功能 | 字段与路由清单 |
| [docs/database.md](./database.md) | 建库、灌数据、迁移命令、v1→v2 升级、备份 | 动 `app/models.py`、升级既有库 | 报错处理（见 troubleshooting） |
| [docs/troubleshooting.md](./troubleshooting.md) | 按报错原文查原因与修复步骤 | 启动/迁移/登录失败时 | 契约内容与迁移原理 |
| [SPEC.md](../SPEC.md) | 5 张业务表字段、路由与 endpoint、模板上下文、表单字段名 | 写任何后端/前端代码之前 | 操作步骤 |
| [AGENTS.md](../AGENTS.md) | 硬性禁止项、两条提交流程（含 fork）、被打回情形、门禁细节 | 动手前必读（第 1、2、5 节） | 环境搭建 |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | issue、分支、提交、PR、依赖变更的流程说明 | 准备提交时 | 具体命令与代码结构 |
| [.env.example](../.env.example) | 环境变量模板 | 第一次建 `.env` | 变量语义解释 |
| [.github/workflows/ci.yml](../.github/workflows/ci.yml) | CI 实际执行的命令 | 想确认 CI 到底跑哪条测试命令 | 门禁规则（见 CONTRIBUTING） |

## 二 权威顺序

发生冲突时按下列顺序取上者，顺序与冲突处理要求见 [AGENTS.md](../AGENTS.md) 开头一段。本目录的文档属于最后一档，只做解释与索引。

1. [SPEC.md](../SPEC.md)：产品契约，由 Lead 定稿。
2. [AGENTS.md](../AGENTS.md)：给人与 AI 的硬约束。
3. [CONTRIBUTING.md](../CONTRIBUTING.md)：协作流程。
4. [README.md](../README.md) 与 `docs/` 下的文档：使用说明与工程解释。

契约内容的唯一详细出处是 SPEC：表字段见第 3 节、路由与 endpoint 见第 5 节、模板上下文见第 7 节、表单字段名见第 8 节。`docs/` 里的任何文件都不得复制这些清单，只能链接过去。

## 三 按角色读

- **新贡献者**：[README.md](../README.md) → [docs/development.md](./development.md) → [AGENTS.md](../AGENTS.md) 第 1、2、5 节 → [CONTRIBUTING.md](../CONTRIBUTING.md)。
- **后端改动**：[SPEC.md](../SPEC.md) 对应章节 → [docs/architecture.md](./architecture.md) → [docs/database.md](./database.md)（涉及模型时）→ [docs/troubleshooting.md](./troubleshooting.md)（跑不起来时）。
- **前端/模板改动**：[SPEC.md](../SPEC.md) 第 7、8、9 节 → [docs/architecture.md](./architecture.md) 的「新增模板」小节。
- **只想先跑起来**：[docs/development.md](./development.md) 的一节加上 [docs/troubleshooting.md](./troubleshooting.md) 的 demo 账号一节。
- **AI 编码代理**：[AGENTS.md](../AGENTS.md) 第 8 节 → 本文件 → 与任务相关的专题文档。

## 四 维护约定

1. 每篇文档开头固定四行头：`读者`、`职责`、`不写`、`权威来源`，顺序不变。这四行决定这篇文档该收什么。
2. 同一事实只允许一个详细出处，别处只留一句指针（例如「表字段见 [SPEC.md](../SPEC.md) 第 3 节」）。
3. 新增文档要同时在做这件事：写四行头、在本文件「文档地图」加一行、在散落的别处改成指针。
4. 相对链接必须指向真实存在的文件；移动文件时同步改链接，不要留死链。
5. 报错文本必须逐字来自代码或实测输出，不要凭印象改写——排查的人靠它做关键词检索。
