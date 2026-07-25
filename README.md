# 力扣中文站本地化刷题 CLI 工具

一个面向 LeetCode 中文站的轻量本地刷题 CLI。它复用浏览器登录态，在线获取题目，在当前工作目录生成单文件 `solution.py`，并支持本地测试和远程提交。

当前版本：`v0.7.2`

## 长期开发手册

[v1.0 总体设计大纲](PROJECT_DESIGN.md)记录了从当前版本演进到稳定 CLI 与 Python API 的长期架构、版本阶段和验收标准。该文档目前处于 Draft 状态，具体实施前仍需按阶段审查。

[安全审计与修复清单](SECURITY_REVIEW.md)记录了当前源码的风险等级、攻击前提和建议修复顺序；其中列出的问题尚未全部修复。

## 核心能力

- 读取 Chrome 中的 `leetcode.cn` Cookie，复用登录态。
- 在线获取题目详情和题目索引。
- 使用当前工作目录的 `solution.py` 作为唯一主要工作区。
- `lc solve <题号>` 生成可编辑的 Python 解题模板。
- 生成模板后会按当前系统尝试打开 `solution.py`。
- `lc test` 运行 `solution.py` 中的 `run_cases()`。
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
curl -LsSf https://raw.githubusercontent.com/Aetherialter/leetcode-local-cli/v0.7.2/scripts/install.sh | sh
```

Windows PowerShell 一键安装：

```powershell
powershell -ExecutionPolicy ByPass -Command "irm https://raw.githubusercontent.com/Aetherialter/leetcode-local-cli/v0.7.2/scripts/install.ps1 | iex"
```

安装器要求系统已安装 uv；如果未检测到 uv，会安全退出并提示访问 [uv 官方文档](https://docs.astral.sh/uv/)，不会自动下载或执行第三方远端安装脚本。检测到 uv 后，安装器会使用 `uv tool install` 安装 `leetcode-local-cli`，并执行 `lc --version` 验证结果。安装过程不使用 `sudo`，也不会保存 PyPI 或 GitHub 凭据。

已经安装 uv 时，也可以直接安装：

```shell
uv tool install leetcode-local-cli
```

升级或卸载：

```shell
uv tool upgrade leetcode-local-cli
uv tool uninstall leetcode-local-cli
```

如果安装完成后当前终端仍找不到 `lc`，请重新打开终端，或执行 `uv tool update-shell` 后重载 shell 配置。

## 基本工作流

```shell
lc login
lc doctor
lc status
lc get 1
lc solve 1
lc test
lc submit
```

常用命令：

| 命令 | 作用 |
| --- | --- |
| `lc login` | 读取或手动录入 LeetCode 中文站 Cookie |
| `lc status` | 检查当前登录态 |
| `lc profile` | 展示账号和刷题统计 |
| `lc show --limit 20 --skip 0` | 分页展示题目索引，`limit` 单次最大为 100 |
| `lc get <题号>` | 在线展示题目详情 |
| `lc solve <题号>` | 覆盖生成当前目录的 `solution.py` |
| `lc test` | 运行本地 `solution.py` |
| `lc doctor` | 诊断 Session、网络、Cookie 和 `solution.py`，默认不执行代码 |
| `lc doctor --run-solution` | 额外运行当前工作区的 `solution.py` |
| `lc submit` | 提交当前 `solution.py` 的提交区域代码 |

## solution.py 规则

`lc solve` 会覆盖当前目录的 `solution.py`。切换题目前请自行保存当前解法。

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

## 当前限制

- 当前仅支持 LeetCode 中文站。
- 当前仅自动读取 Chrome Cookie。
- `lc solve` 生成模板后会尝试打开 `solution.py`；Windows 使用系统默认打开方式，macOS 使用 `open`，Linux 使用 `xdg-open`。
- 当前远程提交仅支持 Python3。
- 当前只维护 CLI 启动目录中的单个 `solution.py`，不会生成每题独立目录。
- 当前不保存完整题面到本地，也不引入本地数据库。
- `lc solve` 会强制覆盖 `solution.py`。
- `lc show` 的 `limit` 必须为正整数且不超过 100，`skip` 必须为非负整数。
- `lc test` 默认隐藏 Python traceback，只展示本地测试通过或失败。
- 如果 `run_cases()` 中没有断言，`lc test` 显示通过是当前轻量化设计允许的行为。
- 树、链表等题型中，LeetCode 模板里的 `TreeNode` / `ListNode` 定义默认保持注释状态；如需本地构造用例，请自行取消注释并编写测试数据。
- `lc doctor` 会向 LeetCode 中文站发送一次登录态查询，并静态检查 `solution.py` 的存在性、可读性、Python 语法和提交结构；默认不会执行文件。
- `lc doctor --run-solution` 会额外运行语法有效的 `solution.py`，本地运行超过 10 秒会判定失败。
- `lc test` 和 `lc doctor --run-solution` 会以当前用户权限执行本地 Python 代码，请勿在不可信工作区中运行。

## 安全说明

登录态会保存到：

```text
.leetcode_local_cli/session.json
```

该文件可能包含敏感 Cookie 信息，已在 `.gitignore` 中忽略。v0.7 首次读取登录态时会把旧版 `.aether_lc/session.json` 自动迁移到新目录；迁移过程不会输出 Cookie 值。发布前请确认仓库根目录的 `solution.py` 为空，避免把个人解法提交到公开仓库。

## 登录态说明

`leetcode-local-cli` 会把浏览器 Cookie 的本地副本保存到 CLI 启动目录下的 `.leetcode_local_cli/session.json`。本地保存的 Cookie 不会延长 LeetCode 登录态有效期；实际是否有效以 LeetCode 服务端验证为准。v0.8 的 `lc init` 会进一步将用户登录态与工作区分离。

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

维护者发布流程见 [RELEASING.md](https://github.com/Aetherialter/leetcode-local-cli/blob/main/RELEASING.md)。标签触发的发布工作流会在 Linux、macOS 和 Windows 上验收安装器，分别验证 wheel 与源码包，通过 PyPI Trusted Publisher 上传发行包，并创建 GitHub Release。

## 项目结构

```text
src/leetcode_local_cli/
  auth.py       Cookie 读取与本地 session
  client.py     LeetCode 中文站 HTTP 客户端
  cli.py        Typer 命令入口
  doctor.py     本地环境、网络与登录态诊断
  problem.py    题号解析与题目数据标准化
  service.py    应用层流程编排
  ui.py         Rich 终端输出
  version.py    已安装发行版版本读取
  workspace.py  solution.py 生成、解析与运行
scripts/
  install.sh    Linux/macOS 一键安装器
  install.ps1   Windows PowerShell 一键安装器
  smoke_test.py wheel 与源码包发布验收
.github/workflows/
  release.yml   跨平台验证、PyPI 发布与 GitHub Release
tests/
  test_auth.py
  test_cli.py
  test_client.py
  test_doctor.py
  test_install_scripts.py
  test_problem.py
  test_release.py
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
- `v0.8`: `lc init` 与正式工作区管理。
- `v0.9`: 轻量缓存。
- `v0.10`: 样例提取原型。
- `v1.0`: 稳定轻量 CLI。

## License

本项目使用 [MIT License](LICENSE) 开源。
