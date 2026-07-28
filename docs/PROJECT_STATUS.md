# 项目状态

最近更新：2026-07-28

当前发行版本：`v0.7.2`

本文是项目长期开发上下文的状态入口，只记录已经由源码、测试和现有文档确认的事实。用户可见行为以 [README](../README.md) 和 [产品边界与待定决策](PRODUCT_BOUNDARIES.md) 为准；安全问题以 [安全审计与修复清单](SECURITY_REVIEW.md) 为准。

## 当前项目目标

当前产品是面向 LeetCode 中文站的轻量、在线优先、本地刷题 CLI。它复用浏览器或手动输入的登录 Cookie，在 CLI 启动目录维护单个 `solution.py`，支持题目查询、本地测试和远程提交，不以本地题库、数据库或多题目录为当前产品目标。

[v1.0 总体设计大纲](PROJECT_DESIGN.md)提出的长期目标是：在保持轻量 CLI 的同时，形成可复用的 Python 核心、稳定 Python API、中文站与国际站双站点支持，以及明确的配置、凭据和工作区边界。该文档仍处于 `Draft 0.2`，不能把其中尚未实施的接口视为当前能力。

## 已完成功能

### 用户工作流

- `lc login`：自动读取 Chrome 中属于 `leetcode.cn` 的必要 Cookie，失败时允许无回显手动输入，并在线验证登录态。
- `lc status`：验证并显示当前登录账号。
- `lc profile`：显示账号公开资料和按难度统计的解题数据。
- `lc show`：分页显示题目索引，并校验 `limit` 与 `skip`。
- `lc get <题号>`：按展示题号在线查找并显示题目详情。
- `lc solve <题号>`：生成当前启动目录中的 `solution.py`，写入题目元数据、提交区域和本地 `run_cases()` 模板。
- `lc test`：静态检查后，以当前 Python 解释器执行整个 `solution.py`。
- `lc doctor`：检查 Session、中文站连通性、Cookie 登录态和解题文件；默认不执行工作区代码。
- `lc doctor --run-solution`：在显式请求时额外执行 `solution.py`，并使用 10 秒超时。
- `lc submit`：仅提交 marker 区域代码，并轮询远端判题结果。

### 工程能力

- 使用 `src` 布局和 `pyproject.toml` 管理 Python 包。
- 使用 uv 管理锁文件、开发环境、构建和工具安装。
- 使用 Ruff、Pyright 和 pytest 作为格式、Lint、类型和测试门禁。
- 使用 `httpx.MockTransport` 验证 HTTP 错误和响应结构边界，不在 CI 保存真实 LeetCode Cookie。
- Linux、macOS 和 Windows 安装脚本都要求预先安装 uv，不自动执行远端安装脚本。
- 标签触发的 GitHub Actions 在三种操作系统上验证代码、测试、构建和安装器，再通过 PyPI Trusted Publisher 发布。
- 外部文本以纯文本方式交给 Rich，过滤 ANSI、OSC 和其他不安全终端控制字符。
- Session 诊断结果不包含 Cookie 值；Cookie 域名使用标签边界匹配。
- `lc solve` 只创建或覆盖普通 `solution.py`；符号链接、断链、目录、目录链接和 Windows reparse point 会在写入前被拒绝，并返回无 traceback 的 CLI 错误。
- 项目文档集中维护在 `docs/`，由 `docs/README.md` 提供入口；旧 `ROADMAP.md` 已退出，开发路线只在 `DEVELOPMENT_PLAN.md` 维护。

## 当前开发阶段

项目处于 `v0.7.2` 发布后的稳定化与 `v0.8` 设计准备阶段。

当前版本已经形成“登录 → 查询 → 生成 → 本地测试 → 提交 → 诊断”的主流程，但还没有达到长期设计所要求的可复用 Python 核心。当前主要工作不是继续增加表层命令，而是处理已知安全问题、拍板尚未确定的行为语义，并消除路径、界面和业务逻辑之间的耦合。

2026-07-28 的本地基线结果：

- `uv run ruff format --check src tests scripts`：通过，22 个文件已格式化。
- `uv run ruff check src tests scripts pyproject.toml`：通过。
- `uv run pyright src tests scripts`：通过，0 errors。
- `uv run pytest -q`：144 passed，10 skipped；当前 Windows 环境跳过 7 项 POSIX/Bash 专项测试，并因系统未授予符号链接权限跳过 3 项链接测试；实际 Windows junction 测试通过。
- `uv run lc --version` 和 `uv run lc --help`：通过。
- 从本地 wheel 隔离执行 `uv tool install` 后，安装版 `lc --version` 和已安装包的普通文件创建、目录目标拒绝验证通过。

## 未完成任务

### 已确认但尚未实现

- 将用户配置、凭据和工作区路径解耦。
- 移除模块导入时固定 `Path.cwd()` 的路径状态。
- 将工作区明文 Cookie 迁移到跨平台用户配置与系统秘密存储边界。

### 需要先做产品决策

- `lc test` 是否必须验证或主动调用 `run_cases()`。
- 本地测试成功、失败和详细 traceback 的输出策略。
- `lc submit` 对 Accepted、非 Accepted、请求失败和轮询超时的退出码。
- 提交前是否进行静态编译或 marker 区域校验。
- 工作区写入失败时的数据完整性与原子替换保证。
- 非 UTF-8 `solution.py` 的支持范围。
- 编辑器配置优先级和安全命令模型。
- `v0.8` 的工作区根目录、子目录调用、文件位置和初始化语义。
- 系统秘密存储不可用时是否以及如何显式降级。
- 合法空分页、Broken Pipe 和受支持 Python 小版本的行为。

完整清单见 [产品边界与待定决策](PRODUCT_BOUNDARIES.md)。

### 长期架构任务

- 建立显式运行上下文和路径对象。
- 建立结构化领域模型与异常层级，逐步替换成功结果中的裸 `dict` 和 `Any`。
- 让核心代码不依赖 Typer、Rich 或终端退出行为。
- 提供预览并最终稳定的 Python API。
- 通过站点适配器支持 LeetCode 中文站与国际站，并严格隔离凭据。
- 在核心迁移完成后，再实施题面结构、图片降级、UI 改造和源码收口。

## 当前问题

### 安全与数据完整性

- `SR-002`：Cookie 以明文 JSON 保存在 CLI 启动目录，存在误提交、同步和共享泄露风险。
- `SR-003`：`solve` 通过系统文件关联打开 `.py`；Windows 上文件关联可能不是编辑器。该风险当前已被产品接受，等待显式编辑器配置替代。
- `SR-004`：`solution.py` 已拒绝静态可识别的非普通目标，但 `lstat()` 与直接写入之间仍有竞争窗口，且尚未实现原子替换；Session 固定临时文件写入仍会跟随链接目标。

### 行为与可靠性

- 非空且语法合法、但没有有效测试入口的脚本可能被 `lc test` 判定为通过。
- `lc test` 没有超时，而 Doctor 的显式执行有 10 秒超时。
- 非 Accepted 判题和轮询超时可能仍以进程退出码 0 结束。
- `lc solve` 的权限、占用等写入异常已转换为工作区错误；非 UTF-8 解题文件和完整的失败后旧文件保证仍未收敛。
- 极大但合法的分页偏移和 Broken Pipe 行为尚未定界。

### 架构与维护

- `auth.py` 和 `workspace.py` 在导入时捕获当前目录。
- `service.py` 直接导入 `typer.Exit` 和 UI 函数，应用流程尚不能作为独立库复用。
- CLI 命令并未统一通过 service 或未来公开 API，存在多条编排路径。
- 当前 GitHub Actions 只在 `v*` 标签推送时运行，普通分支和 Pull Request 缺少持续验证。
- 项目文档已集中到 `docs/`，未来实施路线以 `DEVELOPMENT_PLAN.md` 为唯一入口，长期目标以 `PROJECT_DESIGN.md` 为准。

## 下一步计划

1. 拍板 `PB-005`，明确失败时是否字节级保留原文件、是否使用同目录随机临时文件和原子替换，再完成工作区写入事务。
2. 按 `PB-001`、`PB-003`、`PB-006`、`PB-002`、`PB-004` 的顺序明确测试、提交、编码和输出语义。
3. 为普通 push 和 Pull Request 增加日常 CI，把标签工作流保留为发布门禁。
4. 开始 `v0.8`：显式运行上下文、配置边界、最小 `lc init`、秘密存储入口和旧 Session 迁移。

每完成一个功能，应同步更新本文的基线、已完成功能、开放问题和下一步计划。
