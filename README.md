# leetcode-local-cli

面向 LeetCode 中文站的轻量本地刷题 CLI：配置一个工作区，通过 Chrome、Edge 或手动 Cookie 登录，在线获取题目，在 `solution.py` 中解题并进行本地调用、诊断和远程提交。

当前已发布版本：`v0.10.0`。

## 安装

需要 Python 3.12+、[uv](https://docs.astral.sh/uv/) 和 Chrome 或 Microsoft Edge。

Linux / macOS：

```bash
curl -LsSf https://raw.githubusercontent.com/Aetherialter/leetcode-local-cli/v0.10.0/scripts/install.sh | sh
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy ByPass -Command "irm https://raw.githubusercontent.com/Aetherialter/leetcode-local-cli/v0.10.0/scripts/install.ps1 | iex"
```

也可以直接安装并初始化：

```shell
uv tool install leetcode-local-cli
lc init
```

自动化验收可以显式指定完整工作区路径：

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
lc check <Submission ID>
```

`lc solve` 会覆盖默认工作区中的普通 `solution.py`，切题前请自行保存解法。符号链接、目录、junction 和其他 reparse point 会被拒绝。

生成模板用 `raise NotImplementedError("请实现题目方法")` 标记待实现方法；开始解题后将它替换为实际返回逻辑。

## 命令

| 命令 | 作用 |
| --- | --- |
| `lc init [path]` | 配置或复用默认工作区；显式路径是完整工作区路径 |
| `lc login` | 依次尝试 Chrome、Edge 和手动 Cookie |
| `lc login --browser chrome\|edge` | 只使用指定浏览器，失败后进入手动登录 |
| `lc status` / `lc profile` | 检查登录态或展示账号信息 |
| `lc show` / `lc get <题号>` | 查看题目列表或详情 |
| `lc solve <题号>` | 生成并打开 `solution.py` |
| `lc test [--timeout 秒数]` | 交互调用 `Solution` 的首个公开方法 |
| `lc test --stdin` | JSON Lines 模式，适合 AI 或 CI |
| `lc doctor [--run-solution]` | 检查工作区、Session 和网络；可选择执行解法 |
| `lc submit [--wait-timeout 秒数]` | 提交 marker 区域并限时等待判题；仅 Accepted 返回 0 |
| `lc check <Submission ID>` | 查询一次已有提交的当前状态，不会重新提交代码 |

## 浏览器登录

执行 `lc login` 后：

1. CLI 优先尝试日常 Chrome，再尝试日常 Edge。
2. 浏览器会打开 Remote debugging 页面与 LeetCode。
3. 勾选 **Allow remote debugging for this browser instance**；出现确认框时选择 **Allow**。
4. CLI 只获取 `leetcode.cn` 的 `LEETCODE_SESSION` 和 `csrftoken`，在线验证后保存。
5. 自动登录失败时，回退到隐藏输入的手动 Cookie。

CLI 不读取或解密浏览器 Cookie 数据库，不创建专用 profile，也不关闭日常浏览器。授权等待上限为 180 秒。

## 本地调用

`lc test` 自动选择 `Solution` 中第一个不以 `_` 开头的实例方法。输入安全 Python 字面量参数：

```text
参数 > nums = [3, 2, 4], target = 6
```

连续两次回车退出。每组默认限时 1 秒；无输入、参数错误、异常或超时返回退出码 1。退出码 0 只表示调用正常完成，不代表算法正确。链表和二叉树暂不自动转换。

非交互示例：

```shell
printf 'nums = [3, 2, 4], target = 6\n' | lc test --stdin
```

`lc submit` 取得 submission ID 后默认等待判题 30 秒。判题查询只在总预算内有限重试；初始提交 POST 不自动重试，避免重复提交。等待超时或查询失败时会保留 submission ID，并返回退出码 1。

等待超时后可执行 `lc check <Submission ID>` 重新查询。该命令只请求一次：已经判题则展示结果，仍在判题则提示稍后重试；只有结果为 Accepted 时返回退出码 0。

## 安全与限制

- 当前只支持 LeetCode 中文站和 Python3 提交。
- Session 保存在工作区 `.leetcode_local_cli/session.json`，包含真实 Cookie，不得提交、上传、同步或共享。
- `solution.py` 只接受 UTF-8 或 UTF-8 BOM。
- `lc test` 与 `lc doctor --run-solution` 会执行本地代码，只能用于可信工作区。
- 判题等待超时不代表提交失败，应使用终端显示的 submission ID 到 LeetCode 查看最终结果。

## 维护者文档

- [当前状态](docs/PROJECT_STATUS.md)
- [架构](docs/ARCHITECTURE.md)
- [产品边界](docs/PRODUCT_BOUNDARIES.md)
- [安全边界](docs/SECURITY_REVIEW.md)
- [技术决策](docs/TECH_DECISIONS.md)
- [发布流程](docs/RELEASING.md)

## License

[MIT License](LICENSE)
