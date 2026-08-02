# Project Scope

`leetcode-local-cli` 是面向 LeetCode 中文站的轻量、本地刷题 CLI。当前正式范围是单默认工作区、单个 `solution.py`、Python3、在线查询、本地调用、诊断和远程提交；数据库、完整题库、Web、AI、多语言和国际站不在当前范围。

# Sources of Truth

- `README.md`：用户安装、命令和公开限制。
- `docs/PROJECT_STATUS.md`：当前版本、未发布变化、优先级和验证状态。
- `docs/ARCHITECTURE.md`：当前模块、依赖方向和数据流。
- `docs/PRODUCT_BOUNDARIES.md`：不得由实现偶然改变的行为及待定语义。
- `docs/SECURITY_REVIEW.md`：凭据、文件、浏览器、代码执行和发布风险。
- `docs/TECH_DECISIONS.md`：需要长期保留原因的技术选择。
- `docs/RELEASING.md`：唯一发布流程。

普通修复只读状态、相关源码和测试。模块边界变化再读架构；公开行为变化再读产品边界；凭据、文件写入、浏览器、网络或用户代码执行再读安全文档。不要为小改动固定加载全部文档。

冲突时按 `PRODUCT_BOUNDARIES → PROJECT_STATUS → ARCHITECTURE → TECH_DECISIONS` 判断，并以真实源码和测试校验文档是否过期。

# Architecture Rules

- 保持 `cli.py → commands/ → use_cases/ → core modules` 单向依赖。
- `cli.py` 只创建 Typer 应用、处理全局回调并注册命令。
- `commands/` 负责参数、终端输入、Rich 渲染和退出码，不承载可复用业务规则。
- `use_cases/` 负责编排业务流程，不得导入 Typer、Rich、`ui.py`、`commands` 或 `cli`。进度和阶段性输出通过窄回调注入。
- `auth.py`、`browser.py`、`client.py`、`workspace.py` 等底层模块暂时保持扁平；只有真实子域包含多个内聚模块时才拆包。
- 路径必须由 `AppPaths` 或显式参数传递，不得在导入时捕获 `Path.cwd()`。
- 新的稳定结果优先使用不可变类型；不得继续扩散裸 `dict`、无约束 `Any` 或传输层响应。
- 用例错误通过项目异常或结构化结果表达，CLI 再映射中文文案和退出码；不得解析中文错误文本判断类型。

# Safety Boundaries

- `solution.py`、配置和 Session 的写入必须拒绝符号链接、断链、目录、junction 和 reparse point，并保护旧文件不被失败写入破坏。
- Cookie 不得写入日志、异常、测试 fixture、报告或 Git；真实登录和提交必须由维护者明确授权。
- 外部字符串只能按纯文本渲染，不得解释为 Rich markup、控制序列、Shell 命令或隐式链接。
- 子进程使用参数数组，不使用 `shell=True`。本地 worker 不是安全沙箱，只能运行可信工作区代码。
- 不提交缓存、构建产物、真实解法、Session、密钥、本机配置或与任务无关的用户改动。

# Verification

先运行直接相关测试；跨模块或高风险改动再运行完整门禁：

```shell
uv run ruff format --check src tests scripts
uv run ruff check src tests scripts pyproject.toml
uv run pyright src tests scripts
uv run pytest
```

影响入口、安装或包内容时，再运行 `uv build --no-sources`、`uv run lc --version` 和 `uv run lc --help`。真实浏览器或远端行为无法自动验证时，必须明确记录未验证范围。

# Documentation and Mentor Mode

只在事实变化时更新对应文档：用户行为更新 README/产品边界，模块变化更新架构，风险变化更新安全文档，优先级或验证状态更新项目状态，重大技术取舍更新技术决策，发布更新 Release Notes。

默认使用中文交流。教学任务解释 Why、How 和 Trade-off；用户明确要求完整实现时可以连续完成设计、实现和验证，但仍需说明关键决策与剩余风险。
