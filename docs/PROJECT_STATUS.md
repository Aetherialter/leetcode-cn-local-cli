# 项目状态

当前已发布版本是 `v0.9.0`。当前工作树在此基础上完成了尚未发布的 CLI 分层与文档轻量化。

## 当前能力

- 配置单个默认工作区并安全维护 `solution.py`。
- 通过日常 Chrome、日常 Edge 或手动 Cookie 登录 LeetCode 中文站。
- 查询题目、生成 Python3 模板、本地调用、环境诊断和远程提交。
- `cli.py → commands/ → use_cases/ → core modules` 已形成单向应用边界。

用户命令和限制见 [README](../README.md)，模块结构见 [ARCHITECTURE](ARCHITECTURE.md)。

## 当前优先级

1. **提交总超时**：用单调时钟控制完整判题预算，覆盖慢判题、未知状态和请求异常。
2. **工作区标记语义**：决定 `.leetcode-local-cli.toml` 应共享、忽略还是迁移；未确认前不修改用户 `.gitignore`。
3. **日常 CI**：普通 push/PR 运行 Ruff、Pyright 和 pytest，标签工作流继续负责三平台发布门禁。
4. **结构化边界**：逐步替换账号与提交结果的裸字典，并细化 `UseCaseError` 类型。

低优先级候选：Broken Pipe、合法空分页、编辑器配置、Python 小版本范围、`ListNode`/`TreeNode` 转换和依赖审计。

## 已知风险

- Session 仍是工作区中的明文 JSON。
- 提交仍固定轮询 10 次。
- 本地 worker 可限制异常和超时，但不是安全沙箱。
- 稳定 Python API 和站点适配器尚未形成。

详细风险见 [SECURITY_REVIEW](SECURITY_REVIEW.md)。

## 长期方向

核心边界稳定后，再评估国际站、最小 Python API、系统秘密存储和编辑器集成。这些方向不是当前排期，也不授权预先引入数据库、Web、AI 或多语言运行时。

## 最近验证

CLI 分层重构通过 Ruff format、Ruff lint、Pyright、Windows 完整测试（289 passed、13 skipped）、wheel/sdist 构建、全部子命令帮助检查和隔离 wheel smoke test。真实浏览器登录和远程提交未在该重构后重复执行；最近的真实 Chrome/Edge 登录证据来自 `v0.9.0` 发布验收。
