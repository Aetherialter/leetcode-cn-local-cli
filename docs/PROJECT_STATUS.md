# 项目状态

当前版本是 `v0.11.0`，主题是用户状态解耦、凭据边界与职责分层。实际发布记录见 [GitHub Releases](https://github.com/Aetherialter/leetcode-local-cli/releases) 和 [PyPI](https://pypi.org/project/leetcode-local-cli/)。

## 当前能力

- 配置单个默认工作区并安全维护 `solution.py`。
- 通过日常 Chrome、日常 Edge 或手动 Cookie 登录 LeetCode 中文站。
- 查询题目、生成 Python3 模板、本地调用、环境诊断和远程提交。
- `cli.py → commands/ → use_cases/` 与 `models / storage / integrations / execution` 已形成职责分层，依赖方向由 AST 测试约束。
- 提交使用结构化结果和单调时钟总预算；超时或轮询失败保留 submission ID。
- 可用 `lc check <Submission ID>` 单次重新查询已有提交，不会重复发送代码。

用户命令和限制见 [README](../README.md)，模块结构见 [ARCHITECTURE](ARCHITECTURE.md)。

## v0.11.0 变化

- 浏览器自动登录会先显示 Chrome/Edge 的 Remote debugging 设置地址，并明确要求勾选 **Allow remote debugging for this browser instance**；自动打开页面未显示或授权端点不可用时，也会提示用户手动打开对应地址。
- README 已记录 Chrome 的 `chrome://inspect/#remote-debugging` 和 Edge 的 `edge://inspect/#remote-debugging` 首次授权步骤。
- Session 已从工作区迁移到平台用户状态目录；账号、题目查询、提交结果查询和默认诊断不再依赖工作区初始化。
- 工作区 marker 已迁移为 local-only 的 `.leetcode_local_cli/workspace.toml`；内测阶段不兼容旧 Session 和旧 marker。
- HTTP 凭据发送限制为精确 LeetCode CN HTTPS 地址，关闭并拒绝全部重定向，测试使用可注入 transport。
- Session 统一为单次读取、校验与类型化结果；Doctor 不再为正常业务提供前置校验，凭据默认 repr 脱敏。
- 原 `workspace.py` 拆成解法存储、执行 worker 和编辑器集成；底层按职责分包，不保留旧根模块转发。`solve --no-open` 只保存，打开失败警告但保存成功仍退出 0。
- 账号聚合放入用例，HTTP 返回冻结的账号、题目分页和详情模型；业务错误带稳定类别，`test --stdin` 的路径解析失败也输出 JSON。
- 新增 `init <完整路径> --repair`：损坏配置先同目录原字节备份，失败尝试回滚；不支持的版本、站点和语言优先拒绝，不覆盖解法。
- 新增普通 push/PR 的三平台 Python 3.12 CI，固定 Actions SHA，不授予发布权限。
- 源码仓库停止跟踪根目录 `solution.py` 并忽略它，本地解法保留；普通用户仍可自由选择工作区位置。

## 当前优先级

1. **发布验收**：通过日常及标签工作流检查 Linux/macOS/Windows 的真实运行结果，发布成功后验证 PyPI 的安装与升级通道。
2. **内测体验验收**：由维护者明确授权后检查真实浏览器登录、保存后打开和 LeetCode 接口；自动化结果不能替代真实账号验收。

低优先级候选：Broken Pipe、合法空分页、编辑器配置、Python 小版本范围、`ListNode`/`TreeNode` 转换和依赖审计。

## 已知风险

- Session 已离开工作区，但仍是用户本地状态目录中的明文 JSON。
- 本地 worker 可限制异常和超时，但不是安全沙箱。
- 稳定 Python API 和站点适配器尚未形成。
- HTTP 的全部重定向拒绝策略可能在接口迁移时使命令暂时失败，需要显式更新适配器；这是保护凭据和避免重放提交的取舍。
- 配置修复提供异常回滚和原始字节备份，不提供断电时的跨文件事务或多进程锁。
- 本次 Windows 验收中，在 Zed 进程运行时有一次切题写入于 `os.replace` 阶段返回 `WinError 5`；旧解法得到保留，随后相同原子替换连续 3 次成功，未形成稳定复现。

详细风险见 [SECURITY_REVIEW](SECURITY_REVIEW.md)。

## 长期方向

核心边界稳定后，再评估国际站、最小 Python API、系统秘密存储和编辑器集成。这些方向不是当前排期，也不授权预先引入数据库、Web、AI 或多语言运行时。

## 最近验证

2026-09-05，分层重构和安全边界修复通过 Ruff format、Ruff lint、Pyright（0 errors）和 Windows 测试（443 passed、18 skipped），并通过 `uv build --no-sources`、版本/帮助入口及 wheel/sdist 隔离安装 smoke test。产物验收包含临时工作区初始化、无工作区 JSON 错误、本地 worker 的实际调用与返回值检查。

18 项跳过包括本机缺少符号链接权限的 11 项及仅适用 POSIX/Bash 的 7 项；Windows junction/reparse point 检查已运行。三平台 CI 尚未远端执行，真实浏览器、登录和远端提交未验收，本轮未读取真实 Cookie。构建时本机 uv 0.12.5 对 `uv_build <0.12.0` 声明给出版本警告，但构建和隔离产物验收成功；未变更依赖或发布版本。

2026-09-04，用户状态/工作区路径拆分、初始化前命令和新 marker 通过完整 Ruff format、Ruff lint、Pyright 和 Windows 测试（346 passed、14 skipped），并通过 `uv build --no-sources`、`lc --version`、`lc --help` 与隔离的无工作区 `lc profile` Smoke Test。自动化验证未读取真实 Cookie、执行真实登录或远程提交。

2026-09-04，未发布的浏览器登录提示和文档变更通过完整 Ruff format、Ruff lint、Pyright 和 Windows 测试（335 passed、13 skipped）。自动化验证未执行真实 Cookie 读取或远程提交。

`v0.10.1` 通过 Ruff format、Ruff lint、Pyright、Windows 完整测试（333 passed、13 skipped）、wheel/sdist 构建及两种产物的隔离安装 smoke test。首次 `v0.10.0` 标签工作流因 CLI 彩色输出测试直接匹配 ANSI 文本而停止，未进入 PyPI 和 GitHub Release；测试改为去色后验证公开文案。2026-08-09 使用维护者明确授权的现有登录态，对随机选取的 10 道免费 Easy 题完成真实提交，10 次均为 Accepted；对应的 10 个 Submission ID 再次执行 `lc check` 均返回 0。测试期间未输出 Cookie，原有空 `solution.py` 已恢复。
