# Copilot 指令

本仓库唯一的规则来源是根目录 [AGENTS.md](../AGENTS.md)，请先完整读取。摘要（详版以 AGENTS.md 为准）：

- 禁止直接推 `main`：main 受分支保护，必须 PR 且检查 `test` 为绿。
- 每个 PR 对应一个 issue，正文首行 `Closes #N`；一个 PR 只做一件事。
- 提交信息用 Conventional Commits，前缀 `feat|fix|docs|refactor|test|chore|ci`，描述可中文。
- 改行为必须带测试，改契约先改 `SPEC.md`；金额用 `Decimal` 两位小数，界面中文。
- 不要提交 `instance/`、`.venv/`、`.env`、`__pycache__/`、`*.db` 与任何凭据。
- 不要用 `--admin` 或关保护的方式绕过门禁。
