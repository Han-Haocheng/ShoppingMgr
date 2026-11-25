<!-- 正文首行必须是关联句：Closes #<issue号>（例如 Closes #12）。缺这一行的 PR 不予合并。 -->

## 变更说明

<!-- 做了什么、为什么这么做；跨域改动先说明是否已与 Lead 对齐 -->

## 关联 issue

Closes #

## 影响面与回滚

- 影响模块 / 页面：
- 是否改动数据模型或迁移：
- 回滚方式：（revert 本次 squash 提交，或将 SPEC.md 与代码恢复到上一个 commit）

## 本地验证（命令 + 关键输出）

```bash
.venv/bin/python -m pytest -q
```

```text
# 粘贴关键输出，例如：8 passed in 0.42s
```

## 检查清单

- [ ] pytest 全绿（本地 `python -m pytest -q` 无 failed / error）
- [ ] 未提交 `instance/` 与 `.venv`
- [ ] 改动过契约时已同步 `SPEC.md`
- [ ] 依赖变更已更新 `requirements.txt`（并在变更说明里写了理由）
