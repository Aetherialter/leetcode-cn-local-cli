# 力扣中文站本地化刷题 CLI 工具

一个面向 LeetCode 中文站的轻量本地刷题 CLI。它复用浏览器登录态，在线获取题目，在显式配置的默认工作区维护单文件 `solution.py`，并支持本地测试和远程提交。

当前已发布版本：`v0.8.0`；当前源码包含尚未发布的 `lc test` 可靠性修复。

## 长期开发手册

[完整文档索引](docs/README.md)集中列出项目状态、架构、产品边界、技术决策、开发计划、安全审计和发布手册。

[v1.0 总体设计大纲](docs/PROJECT_DESIGN.md)记录了从当前版本演进到稳定 CLI 与 Python API 的长期架构、版本阶段和验收标准。该文档目前处于 Draft 状态，具体实施前仍需按阶段审查。

[产品边界与待定决策](docs/PRODUCT_BOUNDARIES.md)记录当前已经确认的行为，以及必须先由维护者拍板才能实现的测试、提交、工作区、编辑器和兼容性语义。[安全审计与修复清单](docs/SECURITY_REVIEW.md)记录当前源码仍需处理的风险。

## 核心能力

- 读取 Chrome 中的 `leetcode.cn` Cookie，复用登录态。
- 在线获取题目详情和题目索引。
- 使用 `lc init` 配置的默认工作区和单个 `solution.py`。
- `lc solve <题号>` 生成可编辑的 Python 解题模板。
- 生成模板后会按当前系统尝试打开 `solution.py`。
- `lc test` 在独立子进程中执行用户编写的 `run_cases()`，展示自测输出，并对空实现、异常和超时返回非零状态。
- `lc doctor` 一次检查 Session 文件、站点连通性、Cookie 登录态和本地解题文件。
- `lc submit` 提交 marker 区域代码到 LeetCode 中文站，并轮询判题结果。
- 生成模板时写入 `problem_id` 和 `submit_question_id`，避免展示题号和 LeetCode 内部提交 ID 混用。
- 生成模板时加入 Pyright/Ruff 文件级配置，减少刷题工作区的未使用导入、未使用变量和 star import 相关提示。
- 使用统一的客户端错误结果类型区分网络、HTTP、JSON、接口结构和登录态错误。

## 环境要求

- Windows / Linux / macOS
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- 已在浏览器中登录 LeetCode 中文站

## 安装

Linux / macOS 一键安装：

```bash
curl -LsSf https://raw.githubusercontent.com/Aetherialter/leetcode-local-cli/v0.8.0/scripts/install.sh | sh
```

Windows PowerShell 一键安装：

```powershell
powershell -ExecutionPolicy ByPass -Command "irm https://raw.githubusercontent.com/Aetherialter/leetcode-local-cli/v0.8.0/scripts/install.ps1 | iex"
```

安装器要求系统已安装 uv；如果未检测到 uv，会安全退出并提示访问 [uv 官方文档](https://docs.astral.sh/uv/)，不会自动下载或执行第三方远端安装脚本。检测到 uv 后，安装器会使用 `uv tool install` 安装 `leetcode-local-cli`，执行绝对路径的 `lc --version` 验证结果，并在可交互终端继续运行 `lc init`。安装过程不使用 `sudo`，也不会保存 PyPI 或 GitHub 凭据。

已经安装 uv 时，也可以直接安装：

```shell
uv tool install leetcode-local-cli
```

直接执行 `uv tool install` 不会运行项目自定义的安装后交互。首次使用前还需要手动执行：

```shell
lc init
```

自动化或 AI 验收可以显式指定完整工作区路径：

```shell
lc init D:/Projects/leetcode-local-cli --yes
```

官方安装器在非交互环境中不会等待输入，而是提示稍后手动执行 `lc init`。CI 可设置 `LEETCODE_LOCAL_CLI_NO_INIT=1` 显式跳过。版本更新发现有效默认工作区时会直接复用，不会重新询问、清空 `solution.py` 或修改工作区配置。

升级或卸载：

```shell
uv tool upgrade leetcode-local-cli
uv tool uninstall leetcode-local-cli
```

如果安装完成后当前终端仍找不到 `lc`，请重新打开终端，或执行 `uv tool update-shell` 后重载 shell 配置。

## 基本工作流

```shell
lc init
lc login
lc doctor
lc status
lc get 1
lc solve 1
lc test
# 慢用例可显式调整总超时
lc test --timeout 30
lc submit
```

常用命令：

| 命令 | 作用 |
| --- | --- |
| `lc init` | 交互输入父目录并创建或复用默认 `leetcode-local-cli` 工作区 |
| `lc init <完整路径> --yes` | 非交互配置明确的完整工作区路径，适合 AI/CI 验收 |
| `lc login` | 读取或手动录入 LeetCode 中文站 Cookie |
| `lc status` | 检查当前登录态 |
| `lc profile` | 展示账号和刷题统计 |
| `lc show --limit 20 --skip 0` | 分页展示题目索引，`limit` 单次最大为 100 |
| `lc get <题号>` | 在线展示题目详情 |
| `lc solve <题号>` | 原子覆盖生成默认工作区的 `solution.py` |
| `lc test [--timeout 秒数]` | 执行一次 `run_cases()`；默认总超时 1 秒 |
| `lc doctor` | 诊断 Session、网络、Cookie 和 `solution.py`，默认不执行代码 |
| `lc doctor --run-solution` | 额外运行当前工作区的 `solution.py` |
| `lc submit` | 提交当前 `solution.py` 的提交区域代码 |

## solution.py 规则

`lc init` 会创建不存在的空 `solution.py`，但已有普通文件会完整保留。`lc solve` 会创建不存在的 `solution.py`，也会原子覆盖默认工作区中的普通 `solution.py`。切换题目前请自行保存当前解法。

如果工作区、配置或同名文件是符号链接、断链、目录链接、Windows junction 或其他 reparse point，初始化或写入会拒绝并以非零状态退出。普通文件覆盖使用同目录随机临时文件和原子替换，写入失败不会先截断旧解法。

生成文件会包含题目元信息和提交区域：

```python
# pyright: reportUnusedImport=false, reportUnusedVariable=false
# ruff: noqa: F401, F841
# @lc problem_id: 1
# @lc submit_question_id: 1
# @lc title: Two Sum
# @lc title_slug: two-sum

# @lc submit_begin
class Solution:
    def twoSum(self, nums: List[int], target: int) -> List[int]: pass
# @lc submit_end
```

`lc submit` 只提交：

```text
# @lc submit_begin
...
# @lc submit_end
```

之间的代码。

## 本地自测契约

`run_cases()` 是用户维护的可选本地调试入口。你可以在其中直接构造变量、打印结果并编写 `assert`：

```python
def run_cases() -> None:
    solution = Solution()
    result = solution.twoSum([2, 7, 11, 15], 9)
    print(result)
    assert result == [0, 1]
```

主动执行 `lc test` 时，CLI 会在独立 Python 子进程中加载 `solution.py`，并且只调用一次同步、无参数的 `run_cases()`。以下情况都会返回退出码 1：入口缺失或不可调用、模板仍是默认空实现、断言失败、运行时异常，以及超过默认 1 秒总超时。用户的 stdout 和简化错误会显示，但不会输出 Python traceback。测试子进程不读取交互式终端输入；测试变量应直接写在 `run_cases()` 中。`--timeout` 只接受大于 0 的有限秒数，非法参数返回退出码 2。

本地自测不是远程提交的前置条件。确认当前代码正确时可以直接执行 `lc submit`；提交命令不会检查或运行 `run_cases()`，而且 marker 外的本地测试代码不会发送到 LeetCode。

## 当前限制

- 当前仅支持 LeetCode 中文站。
- 当前仅自动读取 Chrome Cookie。
- `lc solve` 生成模板后会尝试打开 `solution.py`；Windows 使用系统默认打开方式，macOS 使用 `open`，Linux 使用 `xdg-open`。
- 当前远程提交仅支持 Python3。
- 当前只维护用户配置所指向的单个默认工作区和单个 `solution.py`，不会生成每题独立目录，也不提供全局 `--workspace`。
- 当前不保存完整题面到本地，也不引入本地数据库。
- `lc solve` 会强制覆盖普通 `solution.py`，但拒绝符号链接、断链、目录、目录链接和 Windows reparse point。
- `lc show` 的 `limit` 必须为正整数且不超过 100，`skip` 必须为非负整数。
- `solution.py` 只接受 UTF-8，并兼容 UTF-8 BOM；其他编码会在 `test`、`doctor` 和 `submit` 中受控失败，不执行文件、不发送提交请求，也不展示 `UnicodeDecodeError` traceback。
- `lc test` 默认采用 1 秒严格总超时，近似 LeetCode 的限时运行体验，但它还包含本地 Python 进程启动、导入和测试数据构造时间，并不等同于远端判题的算法运行时间；慢用例可显式使用 `--timeout`。本地代码仍以当前用户权限运行，不是安全沙箱。
- 当前 `lc submit` 在非 Accepted 或轮询超时时仍可能返回退出码 0；自动化流程不能只根据退出码判断提交通过。
- 在 Git 仓库根目录执行 `lc init` 会创建 `.leetcode-local-cli.toml`，项目当前不会自动修改 `.gitignore`；该标记的提交与忽略策略仍在确认。
- 树、链表等题型中，LeetCode 模板里的 `TreeNode` / `ListNode` 定义默认保持注释状态；如需本地构造用例，请自行取消注释并编写测试数据。
- `lc doctor` 会向 LeetCode 中文站发送一次登录态查询，并静态检查 `solution.py` 的存在性、可读性、Python 语法和提交结构；默认不会执行文件。
- `lc doctor --run-solution` 会额外运行语法有效的 `solution.py`，本地运行超过 10 秒会判定失败。
- `lc test` 和 `lc doctor --run-solution` 会以当前用户权限执行本地 Python 代码，请勿在不可信工作区中运行。

## 安全说明

登录态会保存到默认工作区：

```text
.leetcode_local_cli/session.json
```

该文件包含敏感 Cookie 信息，当前仓库已在 `.gitignore` 中忽略。v0.8 不读取、迁移或删除旧 `.aether_lc/session.json`，也暂不接入操作系统凭据管理器；这是为维护者授权 AI 使用真实账号验收而保留的阶段性方案，不是长期安全终点。不要把工作区放进同步盘或共享目录，不要输出、暂存、提交或上传 Session 内容。发布前请确认仓库根目录的 `solution.py` 为空。

仓库还会忽略常见个人编辑器目录、`.env*` 和常见凭据 JSON 文件名，并通过测试检查已跟踪 JSON 中的高风险秘密字段。不要使用 `git add -f` 强制添加这些文件；提交前仍应检查 `git status`，因为 `.gitignore` 不能替代秘密扫描，也不能保护已经被跟踪的文件。

## 登录态说明

`leetcode-local-cli` 会把浏览器 Cookie 的本地副本保存到默认工作区的 `.leetcode_local_cli/session.json`。本地保存的 Cookie 不会延长 LeetCode 登录态有效期；实际是否有效以 LeetCode 服务端验证为准。`lc init`、版本更新和工具卸载都不会覆盖或删除该文件。

如果浏览器 Cookie 刷新，或旧 Cookie 被服务端判定失效，CLI 可能在 `lc status`、`lc profile` 或 `lc submit` 时提示重新执行：

```shell
lc login
```

`lc show` 和 `lc get` 访问公开题目数据，可能在登录态失效时仍然可用。遇到登录态、网络或本地解题文件问题时，可以执行：

```shell
lc doctor
```

诊断输出只包含用户名、Cookie 缺失项等安全元数据，不会展示 Cookie 值。

## 开发与验证

```shell
uv run ruff format src tests scripts
uv run ruff check src tests scripts pyproject.toml
uv run pyright src tests scripts
uv run pytest
uv build --no-sources
```

发布前常用手动检查：

```shell
uv run lc --help
uv run lc --version
uv run lc doctor
uv run lc get 2196
uv run lc solve 1
uv run lc test
uv run ruff check solution.py
```

维护者发布流程见 [发布手册](docs/RELEASING.md)。标签触发的发布工作流会在 Linux、macOS 和 Windows 上验收安装器，分别验证 wheel 与源码包，通过 PyPI Trusted Publisher 上传发行包，并创建 GitHub Release。

## 项目结构

```text
src/leetcode_local_cli/
  auth.py       Cookie 读取与本地 session
  _test_runner.py 隔离加载并执行 run_cases 的子进程入口
  client.py     LeetCode 中文站 HTTP 客户端
  cli.py        Typer 命令入口
  config.py     版本化配置读取与工作区初始化
  doctor.py     本地环境、网络与登录态诊断
  paths.py      跨平台路径与 AppPaths 运行上下文
  problem.py    题号解析与题目数据标准化
  safe_files.py 非普通目标拒绝与原子文件写入
  solution_source.py solution.py 的 UTF-8/BOM 读取与编码错误边界
  service.py    应用层流程编排
  ui.py         Rich 终端输出
  version.py    已安装发行版版本读取
  workspace.py  solution.py 生成、解析、运行与本地测试结果映射
scripts/
  install.sh    Linux/macOS 一键安装器
  install.ps1   Windows PowerShell 一键安装器
  smoke_test.py wheel 与源码包发布验收
.github/workflows/
  release.yml   跨平台验证、PyPI 发布与 GitHub Release
docs/
  README.md            文档索引与权威顺序
  PROJECT_STATUS.md    当前实现状态
  ARCHITECTURE.md      当前架构与数据流
  PRODUCT_BOUNDARIES.md 已确认边界与待定决策
  TECH_DECISIONS.md    技术决策记录
  DEVELOPMENT_PLAN.md  唯一长期开发路线
  PROJECT_DESIGN.md    v1.0 长期架构设计
  SECURITY_REVIEW.md   当前安全与可靠性问题
  RELEASING.md         发布流程
  release-notes/       版本化发布说明
tests/
  test_auth.py
  test_cli.py
  test_client.py
  test_config.py
  test_doctor.py
  test_install_scripts.py
  test_problem.py
  test_paths.py
  test_release.py
  test_safe_files.py
  test_service.py
  test_ui.py
  test_workspace.py
```

## 版本路线

- `v0.5.x`: 远程提交上线后的 bugfix patch 线。
- `v0.5.4`: 修复 GraphQL `data: null` 导致 traceback，并精简 README。
- `v0.5.5`: 引入客户端错误结果类型，收敛 service 层错误处理并补充边界测试。
- `v0.5.6`: 收束 `lc show` 参数校验，避免非法分页参数触发远端接口异常提示。
- `v0.5.7`: 修复非 Windows 环境导入 `os.startfile` 导致 CLI 无法启动的问题。
- `v0.6.0`: 新增 `lc doctor`，完善客户端边界校验、本地文件诊断、错误提示和提交目标展示。
- `v0.7.0`: uv 全局工具安装、跨平台引导脚本和 PyPI Trusted Publisher 发布流程。
- `v0.7.1`: 修正安装版 CLI 的命令建议，并引入版本化 GitHub Release Notes。
- `v0.7.2`: 收紧安全边界，避免诊断命令默认执行解题文件，并移除安装器的远端脚本执行。
- `v0.8.0`: 新增显式运行上下文、版本化配置、`lc init`、默认工作区和安装后初始化。
- `v0.9`: 领域模型、异常与 Python API 预览。
- `v0.10`: 双站点客户端与独立账号体系。
- 后续版本：CLI 迁移、题面与 UI、源码收口和发布加固，详见[长期开发计划](docs/DEVELOPMENT_PLAN.md)。
- `v1.0`: 稳定轻量 CLI。

## License

本项目使用 [MIT License](LICENSE) 开源。
