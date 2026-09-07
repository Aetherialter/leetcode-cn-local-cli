# 项目状态

当前版本是 `v0.11.0`，主题是用户状态解耦、凭据边界与职责分层。实际发布记录见 [GitHub Releases](https://github.com/Aetherialter/leetcode-local-cli/releases) 和 [PyPI](https://pypi.org/project/leetcode-local-cli/)。

## 当前能力

- 配置单个默认工作区并安全维护 `solution.py`。
- 通过日常 Chrome、日常 Edge 或手动 Cookie 登录 LeetCode 中文站。
- 查询题目、生成 Python3 模板、本地调用、环境诊断和远程提交。
- `cli.py → commands/ → use_cases/` 与 `models / storage / integrations / execution` 已形成职责分层，依赖方向由 AST 测试约束。
- 提交使用结构化结果和单调时钟总预算；超时或轮询失败保留 submission ID。
- 可用 `lc check <Submission ID>` 单次重新查询已有提交，不会重复发送代码。

## 未发布变化

- 新增 `lc config editor`：支持 Zed、VS Code 和可执行文件路径/参数数组。用户配置不再强制含默认工作区，编辑器设置可在初始化前保存，之后 `init` 保留设置。
- `solve --editor` 临时覆盖用户设置，`--no-open` 优先；未配置只保存并提示，不再使用可能执行 `.py` 的系统文件关联。显式编辑器失败仍为保存成功加警告。
- `test` 支持通过 `ListNode` / `TreeNode` 可空或字符串注解进行节点数组转换，兼容 `null` / `None`，输出节点和原地修改参数可读。模板辅助定义位于提交区域外。
- 节点支持限定为整数值、无环单链表和普通二叉树；拒绝环、共享节点身份、嵌套集合及超限输入输出，不扩展到复杂节点或设计题协议。
- 本地异常增加用户代码行号；`test --verbose` 提供不采集局部变量的调用栈，JSON Lines 增加对应结构化字段。
- wheel/sdist 隔离 smoke test 新增编辑器设置跨初始化保留、节点模板资源和树数组调用验证。
- 审查修复：用户配置独立写为 v2，marker 保持 v1、Session 不变；已有 v1 用户配置只读可用，显式设置/清除编辑器或初始化时才升级，防止旧版误用修复流程丢失新版字段。
- 编辑器参数补齐 TOML 控制字符转义，用户配置在原子替换前验证 UTF-8、TOML 与结构；序列化或替换失败保留原件。
- 普通与延迟注解一致拒绝包含引号的嵌套节点类型，`Literal` 取值与 `Annotated` 元数据不误判为类型引用；worker 超时后的重启加载错误保留行号与可选调用栈，后续输入仍可恢复。
- 发布工作流的三平台前置任务补齐 wheel/sdist 完整隔离安装验收，覆盖配置、初始化及节点调用；发布任务仍复验它自身构建的产物。已新增门禁契约测试，远端矩阵尚未执行。

新增能力目前属于尚未发布的源码变化，版本仍为 `0.11.0`；开发验收使用 `uv run lc`，没有修改全局工具安装。本次维护者只授权提交和推送源码，不创建版本标签或发布包。

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

1. **新版体验收尾**：维护者方便时确认真实 Zed 窗口打开行为；本轮按要求不干扰其他项目，没有启动编辑器或操作浏览器。
2. **准备下一版发布**：审查问题已修复，本地门禁和产物验收通过，三平台发布产物门禁已补齐；本次仅提交推送源码并检查普通 CI，整理新版本、标签发布与公共安装验收另需明确授权。本地检查不能替代远端平台结果。

低优先级候选：Broken Pipe、合法空分页、Python 小版本范围、复杂节点协议和依赖审计。

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

2026-09-07，发布前收尾补齐三平台产物门禁，通过发布/仓库卫生定向测试（26 passed、1 skipped）、Ruff format/lint、Pyright（0 errors）及完整 Windows 测试（578 passed、18 skipped）。使用 `uv build --no-sources --force-pep517` 按声明范围内的后端成功构建，未出现版本范围警告；生成的 wheel/sdist 分别通过隔离安装 smoke test。sdist 安装阶段仍走本机 uv 内置快路径并提示版本范围警告，不能将单独的 PEP 517 构建通过描述为全链路告警已消除。依赖与全局工具未修改；远端工作流、真实编辑器窗口仍未验收，未提交、推送或发布。

2026-09-07，以上四项审查修复通过 Ruff format（79 个文件）、Ruff lint、Pyright（0 errors）及完整 Windows 测试（574 passed、18 skipped），比上轮增加 57 项回归检查。覆盖配置版本独立与显式升级、拒绝未来版本和旧版本写入、控制字符往返与失败保留原件、普通/延迟节点注解及普通字符串、真实 worker 超时后加载失败与再次恢复，以及交互/JSON 的行号和可选调用栈。

通过 `uv build --no-sources`、`uv run lc --version` / `--help` 和 wheel/sdist 隔离安装 smoke test。18 项跳过仍为 Windows 符号链接权限与 POSIX/Bash 平台限定；未执行远端三平台 CI。构建仍提示 uv 0.12.5 与 `uv_build <0.12.0` 的声明范围不一致，未改依赖。本轮测试仅使用临时配置与解法，没有访问真实账号、改写本机用户配置/Session 或打开编辑器；版本仍为 0.11.0，未提交、推送或发布。

2026-09-06，编辑器设置与本地节点能力通过 Ruff format（79 个文件）、Ruff lint、Pyright（0 errors）及完整 Windows 测试（517 passed、18 skipped）。通过 `uv build --no-sources`、版本/帮助入口和 wheel/sdist 隔离安装 smoke test；验证新命令、编辑器设置在初始化前后保留、包内节点定义及树数组输入输出。18 项跳过为本机符号链接权限限制和 POSIX/Bash 平台限定；本轮未执行 Linux/macOS CI。构建仍有 uv 0.12.5 与声明的 `uv_build <0.12.0` 版本范围警告，未变更依赖。

同日经维护者明确授权，复用现有账号和源码工作区，`status`、`profile`、`show`、`get` 成功；隔离用户配置路径但保留原 Session 位置，`profile` 成功而 `test --stdin` 正确返回工作区缺失，证明登录态不依赖工作区初始化。第 2、94、1 题均用真实模板切题，分别验证 3、4、4 组本地输入，结果符合预期。第 1 题仅提交一次，Submission ID `747241009` 返回 Accepted（65/65），再执行 `check` 同样 Accepted。

原有空 `solution.py` 已按原始字节恢复，Session 未重写或输出；用户编辑器设置为 `zed`。未调用电脑控制、重新登录或启动真实编辑器，编辑器启动仅以替身及无界面的参数记录进程验收。链表和树题仅本地运行，未额外远端提交。以上不代表重新登录流程、编辑器窗口或所有节点题型已完成实机验收。

2026-09-05，分层重构和安全边界修复通过 Ruff format、Ruff lint、Pyright（0 errors）和 Windows 测试（443 passed、18 skipped），并通过 `uv build --no-sources`、版本/帮助入口及 wheel/sdist 隔离安装 smoke test。产物验收包含临时工作区初始化、无工作区 JSON 错误、本地 worker 的实际调用与返回值检查。

18 项跳过包括本机缺少符号链接权限的 11 项及仅适用 POSIX/Bash 的 7 项；Windows junction/reparse point 检查已运行。三平台 CI 尚未远端执行，真实浏览器、登录和远端提交未验收，本轮未读取真实 Cookie。构建时本机 uv 0.12.5 对 `uv_build <0.12.0` 声明给出版本警告，但构建和隔离产物验收成功；未变更依赖或发布版本。

2026-09-04，用户状态/工作区路径拆分、初始化前命令和新 marker 通过完整 Ruff format、Ruff lint、Pyright 和 Windows 测试（346 passed、14 skipped），并通过 `uv build --no-sources`、`lc --version`、`lc --help` 与隔离的无工作区 `lc profile` Smoke Test。自动化验证未读取真实 Cookie、执行真实登录或远程提交。

2026-09-04，未发布的浏览器登录提示和文档变更通过完整 Ruff format、Ruff lint、Pyright 和 Windows 测试（335 passed、13 skipped）。自动化验证未执行真实 Cookie 读取或远程提交。

`v0.10.1` 通过 Ruff format、Ruff lint、Pyright、Windows 完整测试（333 passed、13 skipped）、wheel/sdist 构建及两种产物的隔离安装 smoke test。首次 `v0.10.0` 标签工作流因 CLI 彩色输出测试直接匹配 ANSI 文本而停止，未进入 PyPI 和 GitHub Release；测试改为去色后验证公开文案。2026-08-09 使用维护者明确授权的现有登录态，对随机选取的 10 道免费 Easy 题完成真实提交，10 次均为 Accepted；对应的 10 个 Submission ID 再次执行 `lc check` 均返回 0。测试期间未输出 Cookie，原有空 `solution.py` 已恢复。
