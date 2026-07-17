# 力扣中文站本地化刷题 CLI 工具后续版本规划

本文档是力扣中文站本地化刷题 CLI 工具的 GitHub CLI 版本路线草案，当前仓库名为 `leetcode-cn-local-cli`，用于在正式实现前确认大方向。当前产品定位是轻量、在线优先、单文件工作区的 LeetCode 中文站 CLI 工具。

## 产品边界

力扣中文站本地化刷题 CLI 工具应保持轻量 CLI 工具定位，不应默认演变成本地题库生成器。

- 保持 `solution.py` 作为唯一主要工作文件。
- 默认不生成每道题独立目录。
- 在缓存方案明确前，不保存完整题面到本地。
- 优先做小版本、可发布、能改善真实工作流的功能。
- 简历项目版的后端、数据库、前端、AI 工作流应作为另一条产品线，不混入当前 GitHub CLI 版本。

## 当前状态

- `v0.1`: 登录、session 校验、账号详情展示。
- `v0.2`: 在线题目索引和题目详情查询。
- `v0.3`: 在线解题模板工作流，生成根目录 `solution.py`。
- `v0.4`: 单文件本地测试工作流，通过 `run_cases()` 和 `lc test` 运行本地断言。
- `v0.5`: 远程提交与判题轮询，通过 `lc submit` 提交 `solution.py` 中 marker 包裹的代码。
- `v0.5.1`: 修复按题号查询高题号时只能搜索前 100 题的问题。
- `v0.5.2`: 修复远程提交使用展示题号导致提交目标不一致的问题。
- `v0.5.3`: 改善 `solution.py` 编辑体验，减少静态分析告警并补充空模板占位。
- `v0.5.4`: 修复 GraphQL `data: null` 导致 traceback，并精简 README。
- `v0.5.5`: 引入客户端错误结果类型，收敛 service 层错误处理并补充边界测试。
- `v0.5.6`: 收束 `lc show` 参数校验，避免非法分页参数触发远端接口异常提示。
- `v0.5.7`: 修复非 Windows 环境导入 `os.startfile` 导致 CLI 无法启动的问题。
- `v0.6.0`: 新增 `lc doctor`，完善网络、登录态、本地文件和接口结构诊断。

## 已实现版本

### v0.5: 远程提交与判题轮询

目标：允许用户把当前 `solution.py` 中的解法提交到 LeetCode 中文站，并在 CLI 中查看判题结果。

计划范围：

- 新增 `lc submit`，不强制传题号。
- 从根目录 `solution.py` 读取题目元信息并提取待提交代码。
- 初版提交代码提取策略：只提交 `# @lc submit_begin` 与 `# @lc submit_end` 之间的代码。
- 将 Python3 解法提交到 LeetCode 中文站。
- 轮询判题结果，直到通过、失败或超时。
- 展示判题状态、运行时间、内存占用和失败用例信息。

不做内容：

- 暂不支持多语言提交。
- 暂不生成本地题目目录。
- 暂不做自动重试策略。
- 暂不从其他本地文件中猜测提交内容。
- 暂不支持从提交区域外提取用户自定义 import、全局常量或 helper 函数。

工程建议：

- HTTP 提交接口放在 `client.py`。
- 提交流程编排放在 `service.py`。
- 判题结果展示放在 `ui.py`。
- `solution.py` 仍然是唯一提交来源。
- `lc submit` 需要从 `solution.py` 中读取题目元信息，用于确认当前提交目标。
- `solution.py` 应在 `lc solve` 阶段写入题号、标题和 `title_slug` 等元信息。
- `solution.py` 应在 `lc solve` 阶段写入 `# @lc submit_begin` 和 `# @lc submit_end`，用于界定提交代码区域。

已知限制：

- 初版 `lc submit` 只提交 `# @lc submit_begin` 与 `# @lc submit_end` 之间的代码。
- 如果用户在提交区域外定义全局常量、helper 函数或自定义 import，提交时会被丢弃。
- 该限制是为了保持 v0.5 实现简单，后续版本可继续完善代码提取策略。

### v0.5.1: 高题号查询修复

目标：修复 `lc get` 和 `lc solve` 按题号查询时只能在前 100 道题中查找的问题。

更新内容：

- 按题号获取题目详情时改为分页查询 LeetCode 中文站题目索引。
- 修复高题号如 `2196` 无法通过 `lc get` 或 `lc solve` 找到的问题。
- 非法题号输入时保持简化错误提示，避免继续触发 Python traceback。

不做内容：

- 暂不引入本地题目索引缓存。
- 暂不改变 `lc show` 的分页展示语义。
- 暂不扩大远程提交或本地测试能力。

### v0.5.2: 远程提交目标修复

目标：修复远程提交时将展示题号当作 LeetCode 内部提交 ID 使用的问题，避免提交目标和网页端记录不一致。

更新内容：

- 题目详情查询新增 LeetCode 内部 `questionId`。
- `solution.py` 元信息新增 `submit_question_id`，用于远程提交。
- `problem_id` 保持为展示题号，继续用于用户识别当前题目。
- `lc submit` 改为使用 `submit_question_id` 作为提交 payload 中的 `question_id`。
- 补充题目详情标准化和提交元信息解析测试。

不做内容：

- 暂不改变 `lc submit` 的命令参数设计。
- 暂不支持多语言提交。
- 暂不做提交前目标确认交互。

### v0.5.3: solution.py 编辑体验修复

目标：降低刚生成 `solution.py` 后 VSCode/Pylance 和 Ruff 的编辑器提示干扰，让单文件刷题工作区更适合直接编辑。

更新内容：

- 生成 `solution.py` 时加入 Pyright 文件级配置，关闭未使用导入和未使用变量提示。
- 生成 `solution.py` 时加入 Ruff 文件级配置，关闭刷题工作区中的未使用导入和未使用变量提示。
- 将 `from typing import *` 改为显式 `typing` 导入，避免 star import 相关静态分析告警。
- 为 LeetCode 返回的空 Python 方法模板追加轻量 `pass` 占位，避免刚执行 `lc solve` 后立即 `lc test` 因空方法体失败。

不做内容：

- 暂不实现复杂模板规范化器。
- 暂不改变 `run_cases()` 的本地测试入口设计。
- 暂不处理链表、二叉树等注释类型定义的自动展开；用户需要本地测试复杂结构题时，可自行取消注释 `TreeNode` / `ListNode` 等模板定义。

### v0.5.4: GraphQL data:null 防御与文档精简

目标：修复 LeetCode GraphQL 返回 `data: null` 时 CLI 直接 traceback 的问题，并让 GitHub README 更适合首页阅读。

更新内容：

- `user_status()`、`problem_list()`、`problem_detail()` 对 GraphQL `data` 字段增加类型检查。
- 当 `data` 不是字典时返回简化失败结果，由 service 层展示现有错误提示。
- 精简 README，保留项目定位、快速开始、核心命令、`solution.py` 规则、限制和开发验证。
- 在 README 中明确树、链表题本地测试需要用户按需取消注释 `TreeNode` / `ListNode`。

不做内容：

- 暂不引入完整错误结果类型。
- 暂不区分网络异常、参数错误和接口异常的具体原因。
- 暂不自动展开复杂题型的注释类型定义。

### v0.5.5: 客户端错误结果与 service 边界测试

目标：在不扩大功能范围的前提下，收敛 LeetCode HTTP 客户端和 service 层之间的错误处理契约，减少网络异常、接口异常和登录态异常被误判或触发 traceback 的风险。

更新内容：

- 新增 `ClientResult` 和 `ClientErrorKind`，让 `client.py` 用统一结果对象返回数据或错误类型。
- 将网络错误、HTTP 状态错误、JSON 解析失败、接口结构异常、未登录和缺少 CSRF token 做基础分类。
- `service.py` 统一读取 `ClientResult`，并将客户端错误类型映射为用户可读提示。
- 修复 `ClientResult` 迁移过程中 dict 和结果对象混用的风险点。
- 补充 service 层测试，覆盖客户端错误、题目索引结构异常和提交轮询返回值边界。

不做内容：

- 暂不新增 `lc doctor`。
- 暂不引入详细 debug 模式。
- 暂不把底层 HTTP 状态码和接口原始响应直接展示给普通用户。

### v0.5.6: show 参数校验收束

目标：修复 `lc show` 在分页参数不合法时仍请求 LeetCode 并显示接口结构异常的问题，让用户输入错误在本地被直接拦截。

更新内容：

- `lc show` 的 `limit` 必须为正整数。
- `lc show` 的 `limit` 单次最大为 100。
- `lc show` 的 `skip` 必须为非负整数。
- 参数不合法时在 service 层直接退出，不再读取 session 或请求 LeetCode。
- 补充 service 层测试，覆盖 `limit=0`、`limit>100` 和 `skip<0`。

不做内容：

- 暂不改变 `lc get` 和 `lc solve` 内部分页查找策略。
- 暂不引入缓存。
- 暂不抽象 `client.py` 的 HTTP 请求封装。

### v0.6.0: 诊断命令与稳定性

目标：提升 CLI 在 Cookie 失效、网络异常、接口变化和本地文件异常时的可诊断性。

更新内容：

- 新增 `lc doctor`。
- 检查 session 文件是否存在、格式是否正确。
- 检查 Cookie 是否有效。
- 检查 LeetCode 中文站基础连通性。
- 检查 `solution.py` 是否存在、语法与提交结构是否有效，并通过带超时的子进程验证是否可运行。
- 改进网络失败、session 过期、缺少 Python3 模板、题号非法等错误提示。
- 在 `lc submit` 提交前展示当前提交目标，便于用户确认题号、标题和 `title_slug`。
- 为纯逻辑模块补充基础自动化测试。
- 统一 HTTP 请求、状态码、JSON 和响应结构校验，避免接口异常触发 traceback。
- 以原子写入和仅限当前用户的文件权限保存 Session。
- 移除未使用的 `requests` 依赖，并将 Pyright 固定为开发依赖。

不做内容：

- 暂不引入数据库。
- 暂不做自动浏览器登录。
- 默认不做依赖真实 LeetCode 账号的端到端测试。

实现约束：

- 远端诊断只复用一次 `userStatus` 请求完成连通性和 Cookie 验证。
- `solution.py` 运行诊断最长 10 秒，且不回显其标准输出或错误输出。
- 诊断输出不得泄露 Cookie 或 Session 敏感值。

### v0.7: uv 全局安装与跨平台引导

目标：让用户无需克隆仓库即可安装 `lc`，并为后续工作区初始化与 PyPI 发布建立稳定入口。

计划范围：

- 新增 Linux/macOS `scripts/install.sh`。
- 新增 Windows `scripts/install.ps1`。
- 未检测到 uv 时，通过 uv 官方 HTTPS 安装器自动引导。
- 使用 `uv tool install` 安装或替换 `aether-lc`。
- 新增 `lc --version`，并在安装结束后验证可执行命令。
- 支持通过 `AETHER_LC_INSTALL_SPEC` 指向本地 wheel，完成发布前端到端验收。
- 让默认工作目录来自 CLI 启动目录，避免全局安装后写入 uv 工具环境。
- 在安装器和包结构稳定后接入 PyPI Trusted Publisher。

不做内容：

- 本阶段暂不实现 `lc init`。
- 暂不实现题目缓存或数据库。
- 暂不自动迁移现有工作区文件。

工程建议：

- 安装脚本不得使用 sudo，也不得保存用户凭据。
- 所有远程下载必须使用 HTTPS。
- uv 安装失败、包安装失败或版本验证失败时必须返回非零退出码。
- 发布前同时验证 wheel、源码包和隔离的 uv 工具目录。

### v0.8: 工作区初始化

目标：通过 `lc init` 初始化独立刷题目录，并正式分离工具安装目录、用户配置和本地工作区。

计划范围：

- 新增 `lc init [目录]`。
- 使用工作区配置文件识别根目录。
- 默认不覆盖现有 `solution.py`。
- 将 Session 移入跨平台用户配置目录。
- 为旧版 `.aether_lc/session.json` 提供明确迁移策略。

### v0.9: 轻量缓存

目标：提升重复查询题目索引和题目详情时的速度，同时避免项目变成本地题库。

计划范围：

- 缓存题目索引元信息和更新时间。
- 可选缓存 `solve` 所需的最小题目详情元信息。
- 新增 `lc cache clear`。
- 增加缓存过期策略。

### v0.10: 样例提取原型

目标：尝试从题面中提取简单样例，并在安全时预填到 `solution.py` 的 `run_cases()` 中。

计划范围：

- 在 `problem.py` 中新增 `SampleCase` 数据模型。
- 从题面 HTML 中提取常见的输入和输出示例。
- 在 `solution.py` 中生成可编辑的断言建议。
- 对无法稳定解析的样例明确标记，而不是强行猜测。

不做内容：

- 不保证支持链表、二叉树、图、自定义判题等复杂题型。
- 不做复杂 Markdown 或自然语言解析器。
- 不声称自动生成的样例完整覆盖题目。

工程建议：

- 该功能应定位为 best effort。
- 生成内容必须允许用户手动编辑。
- `lc test` 不应依赖网络请求。

### v0.11: 持续集成与发布加固

目标：提升仓库作为公开 GitHub 项目的可靠性和发布质量。

计划范围：

- 添加 GitHub Actions，执行 lint 和测试。
- 为题号解析、工作区生成、CLI 命令注册补充有意义的测试。
- 保持 README 中的安装命令、仓库名和 Release 说明与真实 GitHub 仓库一致。
- 增加 release checklist。
- 增加 changelog 或 release notes 模板。

不做内容：

- PyPI 发布已在 v0.7 明确时，持续完善自动发布与安装包验证。
- 暂不建设大型文档站。

工程建议：

- CI 不应依赖真实 LeetCode 登录态。
- 真实接口检查应保持手动或显式启用。

### v1.0: 稳定轻量 CLI

目标：形成完整、稳定、轻量的 LeetCode 中文站本地刷题 CLI 工作流。

预期工作流：

```powershell
uv run lc login
uv run lc profile
uv run lc show
uv run lc get 1
uv run lc solve 1
uv run lc test
uv run lc submit
```

预期质量：

- 命令行为清晰。
- 单文件解题工作流稳定。
- 错误提示和诊断能力可用。
- 支持远程提交和判题轮询。
- 具备基础自动化测试和 CI。
- README 足够支撑新用户安装和使用。

## 简历项目版方向

简历项目版可以复用该 CLI 中沉淀出的接口理解、工作流设计和题目数据处理经验，但应作为独立产品线。

可能范围：

- 后端 API。
- 数据库记录题目、提交、复盘和练习历史。
- 前端 Dashboard。
- AI 读题、提示、复盘或 Review 工作流。
- Docker 部署。
- CI/CD 和完整文档。

在 CLI 版本达到稳定 `v1.0` 前，不建议将这些能力混入当前轻量 GitHub CLI。

## 待确认决策

- `solution.py` 的提交区域 marker 是否需要支持自定义名称？
- `lc test` 是否永久保持隐藏 traceback，还是未来提供调试开关？
- 缓存功能使用 JSON，还是在需求明确后直接引入 SQLite？
- 样例提取应放在远程提交之前实现，还是延后到 `v1.0` 之后？
