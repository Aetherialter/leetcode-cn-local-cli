# leetcode-local-cli

面向 LeetCode 中文站的轻量本地刷题 CLI：通过 Chrome 或 Edge 获取登录态，在线获取题目，在一个明确配置的工作区维护 `solution.py`，并支持本地执行、诊断和远程提交。

当前版本：`v0.9.0`。具体状态见 [项目状态](docs/PROJECT_STATUS.md)。

## 安装

需要 Python 3.12+、[uv](https://docs.astral.sh/uv/) 和 Chrome 或 Microsoft Edge。

Linux / macOS：

```bash
curl -LsSf https://raw.githubusercontent.com/Aetherialter/leetcode-local-cli/v0.9.0/scripts/install.sh | sh
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy ByPass -Command "irm https://raw.githubusercontent.com/Aetherialter/leetcode-local-cli/v0.9.0/scripts/install.ps1 | iex"
```

也可以直接安装：

```shell
uv tool install leetcode-local-cli
lc init
```

自动化或 AI 验收可显式指定工作区：

```shell
lc init D:/Projects/leetcode-local-cli --yes
```

升级或卸载：

```shell
uv tool upgrade leetcode-local-cli
uv tool uninstall leetcode-local-cli
```

## 快速开始

```shell
lc init
lc login
lc doctor
lc get 1
lc solve 1
lc test
lc submit
```

`lc solve` 会覆盖默认工作区中的普通 `solution.py`，切换题目前请自行保存解法。符号链接、目录、junction 和其他 reparse point 会被拒绝，普通文件使用原子替换写入。

生成模板中的待实现方法使用：

```python
raise NotImplementedError("请实现题目方法")
```

开始解题后删除它并返回题目要求的结果。

## 常用命令

| 命令 | 作用 |
| --- | --- |
| `lc init [path]` | 配置或复用默认工作区；显式路径是完整工作区路径 |
| `lc login` / `lc status` | 自动按 Chrome、Edge、手动 Cookie 的顺序登录，并检查在线状态 |
| `lc login --browser chrome` | 只使用当前日常 Chrome，失败后进入手动登录 |
| `lc login --browser edge` | 只使用当前日常 Edge，失败后进入手动登录 |
| `lc login --browser chrome --devtools-port 9222` | 高级用法：连接指定浏览器的本机 DevTools |
| `lc profile` | 展示账号与刷题统计 |
| `lc show --limit 20 --skip 0` | 展示题目列表 |
| `lc get <题号>` | 获取题目详情和 Python 模板 |
| `lc solve <题号>` | 写入并打开 `solution.py` |
| `lc test [--timeout 秒数]` | 交互执行 `Solution` 的首个公开实例方法 |
| `lc test --stdin` | JSON Lines 模式，适合 AI 或 CI |
| `lc doctor` | 检查 Session、网络、登录态和解题文件 |
| `lc submit` | 提交 marker 区域；仅 Accepted 返回退出码 0 |

## 浏览器授权登录

新版 Chrome 可能阻止第三方程序直接解密默认配置中的 Cookie。执行以下命令即可让 Chrome 自己读取登录态：

```shell
lc login
```

默认 `lc login` 先尝试当前日常 Google Chrome，失败后再尝试当前日常 Microsoft Edge。CLI 会为目标浏览器打开 `chrome://inspect/#remote-debugging` 或 `edge://inspect/#remote-debugging` 和 LeetCode；用户必须勾选 **Allow remote debugging for this browser instance**，浏览器才会生成 CLI 等待的 `DevToolsActivePort`。连接时如果出现 **Allow remote debugging?**，还需要点击 **Allow**。浏览器未运行、授权文件指向已关闭的旧实例，或只有后台进程无法显示确认框时，CLI 会自动打开一个可见窗口，并在 180 秒总时限内等待浏览器启动和用户授权，不会因第一次连接竞态立即切换浏览器。

CLI 不创建专用浏览器配置、不读取或解密 Cookie 数据库，也不拥有或关闭日常浏览器。浏览器重启后可能需要重新授权当前实例。两条路径都只允许回环地址，只请求 `https://leetcode.cn/` 适用的 Cookie，并只保留 `LEETCODE_SESSION` 与 `csrftoken`。如果 Chrome、Edge 均不可用或没有取得所需 Cookie，命令回退到隐藏输入的手动 Cookie 登录。网络故障和 Session 写入故障不会通过切换浏览器掩盖。

## `lc test`

`lc test` 自动选择 `Solution` 中第一个不以 `_` 开头的实例方法。把主方法放在前面；辅助方法使用 `_dfs`、`_helper` 等私有命名，或放在主方法后面。

输入是一组安全 Python 字面量参数：

```text
参数 > nums = [3, 2, 4], target = 6
```

它显示实际返回值；每组调用默认限时 1 秒，异常、输入错误或超时都会使最终退出码为 `1`，但不会中断交互。退出码 `0` 只表示调用正常完成，**不代表算法正确**。链表和二叉树暂不自动转换。

AI/CI 可以逐行输入相同参数，并读取 JSON Lines：

```shell
printf 'nums = [3, 2, 4], target = 6\n' | lc test --stdin
```

## 安全与限制

- 当前仅支持 LeetCode 中文站、Chrome/Edge 浏览器登录和 Python3 提交。
- `lc login` 不读取浏览器 Cookie 数据库，也不关闭日常 Chrome 或 Edge；未知端口或浏览器身份会被拒绝。
- Session 保存在默认工作区的 `.leetcode_local_cli/session.json`；它包含 Cookie，绝不能提交、上传或放入共享目录。
- `solution.py` 只接受 UTF-8（兼容 UTF-8 BOM）。
- `lc test` 与 `lc doctor --run-solution` 会执行本地代码；只在可信工作区运行。
- `lc submit` 当前仍使用固定次数轮询；判题较慢时请以 LeetCode 网站结果为准。

## 文档与开发

- [文档索引](docs/README.md)
- [项目状态](docs/PROJECT_STATUS.md)
- [架构](docs/ARCHITECTURE.md)
- [产品边界](docs/PRODUCT_BOUNDARIES.md)
- [开发计划](docs/DEVELOPMENT_PLAN.md)
- [安全审计](docs/SECURITY_REVIEW.md)
- [发布流程](docs/RELEASING.md)

本地验证：

```shell
uv run ruff format --check src tests scripts
uv run ruff check src tests scripts pyproject.toml
uv run pyright src tests scripts
uv run pytest
uv build --no-sources
```

## License

[MIT License](LICENSE)
