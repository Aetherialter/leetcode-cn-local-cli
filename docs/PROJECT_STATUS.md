# 项目状态

当前发布版本是 `v0.10.1`，主题是可靠提交、结果重查和 CLI 应用分层。

## 当前能力

- 配置单个默认工作区并安全维护 `solution.py`。
- 通过日常 Chrome、日常 Edge 或手动 Cookie 登录 LeetCode 中文站。
- 查询题目、生成 Python3 模板、本地调用、环境诊断和远程提交。
- `cli.py → commands/ → use_cases/ → core modules` 已形成单向应用边界。
- 提交使用结构化结果和单调时钟总预算；超时或轮询失败保留 submission ID。
- 可用 `lc check <Submission ID>` 单次重新查询已有提交，不会重复发送代码。

用户命令和限制见 [README](../README.md)，模块结构见 [ARCHITECTURE](ARCHITECTURE.md)。

## 当前优先级

1. **工作区标记语义**：决定 `.leetcode-local-cli.toml` 应共享、忽略还是迁移；未确认前不修改用户 `.gitignore`。
2. **日常 CI**：普通 push/PR 运行 Ruff、Pyright 和 pytest，标签工作流继续负责三平台发布门禁。
3. **结构化边界**：继续替换账号结果的裸字典，并细化 `UseCaseError` 类型。

低优先级候选：Broken Pipe、合法空分页、编辑器配置、Python 小版本范围、`ListNode`/`TreeNode` 转换和依赖审计。

## 已知风险

- Session 仍是工作区中的明文 JSON。
- 本地 worker 可限制异常和超时，但不是安全沙箱。
- 稳定 Python API 和站点适配器尚未形成。
- 本次 Windows 验收中，在 Zed 进程运行时有一次切题写入于 `os.replace` 阶段返回 `WinError 5`；旧解法得到保留，随后相同原子替换连续 3 次成功，未形成稳定复现。

详细风险见 [SECURITY_REVIEW](SECURITY_REVIEW.md)。

## 长期方向

核心边界稳定后，再评估国际站、最小 Python API、系统秘密存储和编辑器集成。这些方向不是当前排期，也不授权预先引入数据库、Web、AI 或多语言运行时。

## 最近验证

`v0.10.1` 通过 Ruff format、Ruff lint、Pyright、Windows 完整测试（333 passed、13 skipped）、wheel/sdist 构建及两种产物的隔离安装 smoke test。首次 `v0.10.0` 标签工作流因 CLI 彩色输出测试直接匹配 ANSI 文本而停止，未进入 PyPI 和 GitHub Release；测试改为去色后验证公开文案。2026-08-09 使用维护者明确授权的现有登录态，对随机选取的 10 道免费 Easy 题完成真实提交，10 次均为 Accepted；对应的 10 个 Submission ID 再次执行 `lc check` 均返回 0。测试期间未输出 Cookie，原有空 `solution.py` 已恢复。
