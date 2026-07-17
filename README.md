# 力扣中文站本地化刷题 CLI 工具

一个面向 LeetCode 中文站的轻量本地刷题 CLI。它复用浏览器登录态，在线获取题目，生成根目录单文件 `solution.py`，并支持本地测试和远程提交。

当前版本：`v0.6.0`

## 核心能力

- 读取 Chrome 中的 `leetcode.cn` Cookie，复用登录态。
- 在线获取题目详情和题目索引。
- 使用根目录 `solution.py` 作为唯一主要工作区。
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

```shell
git clone https://github.com/Aetherialter/leetcode-cn-local-cli.git
cd leetcode-cn-local-cli
uv sync
uv run lc --help
```

## 基本工作流

```shell
uv run lc login
uv run lc doctor
uv run lc status
uv run lc get 1
uv run lc solve 1
uv run lc test
uv run lc submit
```

常用命令：

| 命令 | 作用 |
| --- | --- |
| `lc login` | 读取或手动录入 LeetCode 中文站 Cookie |
| `lc status` | 检查当前登录态 |
| `lc profile` | 展示账号和刷题统计 |
| `lc show --limit 20 --skip 0` | 分页展示题目索引，`limit` 单次最大为 100 |
| `lc get <题号>` | 在线展示题目详情 |
| `lc solve <题号>` | 覆盖生成根目录 `solution.py` |
| `lc test` | 运行本地 `solution.py` |
| `lc doctor` | 诊断 Session、网络、Cookie 和 `solution.py` |
| `lc submit` | 提交当前 `solution.py` 的提交区域代码 |

## solution.py 规则

`lc solve` 会覆盖根目录 `solution.py`。切换题目前请自行保存当前解法。

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
- 当前只维护根目录单个 `solution.py`，不会生成每题独立目录。
- 当前不保存完整题面到本地，也不引入本地数据库。
- `lc solve` 会强制覆盖 `solution.py`。
- `lc show` 的 `limit` 必须为正整数且不超过 100，`skip` 必须为非负整数。
- `lc test` 默认隐藏 Python traceback，只展示本地测试通过或失败。
- 如果 `run_cases()` 中没有断言，`lc test` 显示通过是当前轻量化设计允许的行为。
- 树、链表等题型中，LeetCode 模板里的 `TreeNode` / `ListNode` 定义默认保持注释状态；如需本地构造用例，请自行取消注释并编写测试数据。
- `lc doctor` 会向 LeetCode 中文站发送一次登录态查询，并在本地运行语法有效的 `solution.py`；本地运行超过 10 秒会判定失败。

## 安全说明

登录态会保存到：

```text
.aether_lc/session.json
```

该文件可能包含敏感 Cookie 信息，已在 `.gitignore` 中忽略。发布前请确认根目录 `solution.py` 为空，避免把个人解法提交到公开仓库。

## 登录态说明

Aether_lc 会把浏览器 Cookie 的本地副本保存到 `.aether_lc/session.json`。本地保存的 Cookie 不会延长 LeetCode 登录态有效期；实际是否有效以 LeetCode 服务端验证为准。

如果浏览器 Cookie 刷新，或旧 Cookie 被服务端判定失效，CLI 可能在 `lc status`、`lc profile` 或 `lc submit` 时提示重新执行：

```shell
uv run lc login
```

`lc show` 和 `lc get` 访问公开题目数据，可能在登录态失效时仍然可用。遇到登录态、网络或本地解题文件问题时，可以执行：

```shell
uv run lc doctor
```

诊断输出只包含用户名、Cookie 缺失项等安全元数据，不会展示 Cookie 值。

## 开发与验证

```shell
uv run ruff format src tests
uv run ruff check src pyproject.toml tests
uv run pyright src tests
uv run pytest
```

发布前常用手动检查：

```shell
uv run lc --help
uv run lc doctor
uv run lc get 2196
uv run lc solve 1
uv run lc test
uv run ruff check solution.py
```

## 项目结构

```text
src/aether_lc/
  auth.py       Cookie 读取与本地 session
  client.py     LeetCode 中文站 HTTP 客户端
  cli.py        Typer 命令入口
  doctor.py     本地环境、网络与登录态诊断
  problem.py    题号解析与题目数据标准化
  service.py    应用层流程编排
  ui.py         Rich 终端输出
  workspace.py  solution.py 生成、解析与运行
tests/
  test_auth.py
  test_cli.py
  test_client.py
  test_doctor.py
  test_problem.py
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
- `v0.7`: 轻量缓存。
- `v0.8`: 样例提取原型。
- `v0.9`: 打包、测试与 GitHub Actions。
- `v1.0`: 稳定轻量 CLI。

## License

本项目使用 [MIT License](LICENSE) 开源。
