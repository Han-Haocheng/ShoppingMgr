# ShoppingMgr（购物管家）

[![CI](https://github.com/Han-Haocheng/ShoppingMgr/actions/workflows/ci.yml/badge.svg)](https://github.com/Han-Haocheng/ShoppingMgr/actions/workflows/ci.yml)

单用户本地记账 + 购物清单小工具：Flask 3.1 服务端渲染、中文界面、数据落在本地 SQLite。产品契约以 [SPEC.md](SPEC.md) 为唯一准绳，本文件只回答「这是什么」与「怎么开始」。

## 功能要点

- **用户与登录**：注册 / 登录 / 登出，会话 7 天，登录失败有内存限流。
- **数据归属**：所有业务数据挂在登录用户名下，跨用户访问一律按不存在处理（404）。
- **品类与商品**：增删改查；品类名同用户内唯一，商品带单位、单价、可选条码。
- **购物清单**：清单与条目增删、勾选完成、合计金额；金额一律 `Decimal` 两位小数。
- **消费记录**：按月汇总与筛选，日期 `YYYY-MM-DD`、金额 `¥` 两位小数。
- **技术形态**：Jinja2 模板 + Bootstrap 5.3（本地 vendor，无 CDN），无前端框架、无 JSON API。

## 30 秒上手

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt      # 1. 环境与依赖（Python 3.14）
cp .env.example .env                                                    # 2. 至少填 SECRET_KEY（生成命令在 .env.example 注释里）
.venv/bin/flask --app run:app init-db && .venv/bin/python run.py         # 3. 建库+示例数据，起服务 http://127.0.0.1:5000
```

第 3 步之后用 `demo` / `demo1234` 登录（仅本地演示，上线前必须删除或改密）。首次一定要先 `init-db`，否则页面会报 `no such table`。

三步之外的都在专题文档里：依赖与开发依赖、环境变量全表、CLI 命令、启动与调试、测试命令见 [docs/development.md](docs/development.md)；报错按原文查 [docs/troubleshooting.md](docs/troubleshooting.md)。

## 文档地图

| 文档 | 什么时候该读它 |
| --- | --- |
| [docs/README.md](docs/README.md) | 想先看清全部文档的职责边界与权威顺序 |
| [docs/development.md](docs/development.md) | 第一次配环境、跑命令、跑测试、调试 |
| [docs/architecture.md](docs/architecture.md) | 要在 `app/` 下加蓝图、模型或模板 |
| [docs/database.md](docs/database.md) | 建库、灌数据、跑迁移、升级既有 v1 库、备份 |
| [docs/troubleshooting.md](docs/troubleshooting.md) | 启动 / 迁移 / 登录出错，要按报错原文定位 |
| [SPEC.md](SPEC.md) | 写代码前确认契约：数据模型（第 3 节）、路由与端点（第 5 节）、模板上下文（第 7 节）、表单字段名（第 8 节） |
| [AGENTS.md](AGENTS.md) | 动手前读硬约束：禁止项、两条提交流程、被打回情形 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 准备提 issue / PR 时看流程 |

端点表、模板上下文变量、表单字段名，以及删除清单条目时用来指定来源页的隐藏域参数，均以 [SPEC.md](SPEC.md) 为准：路由见第 5 节、结算语义见第 6 节、模板见第 7 节、表单字段见第 8 节。本文件不再复制这些清单。

## 协作与许可

协作方式见 [CONTRIBUTING.md](CONTRIBUTING.md)，硬约束见 [AGENTS.md](AGENTS.md)。本项目以 [MIT 协议](LICENSE) 发布，Copyright (c) 2026 Han-Haocheng；提交 PR 即表示你同意以同一协议授权你的贡献。

[![](https://img.shields.io/badge/powered_by-dsh-4D6BFE?style=flat-square&logo=deepseek&logoColor=white)](https://github.com/deepseek-ai/deepseek-harness)
