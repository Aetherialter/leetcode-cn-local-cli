# leetcode-local-cli

面向 LeetCode 中文站的轻量本地刷题 CLI：配置一个工作区，通过 Chrome、Edge 或手动 Cookie 登录，在线获取题目，在 `solution.py` 中解题并进行本地调用、诊断和远程提交。

最近发布版本：`v0.11.0`。本文也记录当前源码中尚未发布的编辑器配置、节点转换和详细错误功能；这些新增命令需在源码目录使用 `uv run lc ...`。发布记录见 [GitHub Releases](https://github.com/Aetherialter/leetcode-local-cli/releases)。

开发本地源码使用 `uv sync --locked --all-groups`，随后用 `uv run lc ...`；未激活虚拟环境或安装全局工具时，裸 `lc` 不一定可用。

## 安装

需要 Python 3.12+、[uv](https://docs.astral.sh/uv/) 和 Chrome 或 Microsoft Edge。

Linux / macOS：

```bash
curl -LsSf https://raw.githubusercontent.com/Aetherialter/leetcode-local-cli/v0.11.0/scripts/install.sh | sh
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy ByPass -Command "irm https://raw.githubusercontent.com/Aetherialter/leetcode-local-cli/v0.11.0/scripts/install.ps1 | iex"
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

从 `0.10.x` 或更早版本升级后，请重新执行 `lc login`，并用 `lc init <原工作区完整路径> --yes` 注册工作区；已有普通 `solution.py` 会保留。旧工作区 Session 和根目录 `.leetcode-local-cli.toml` 不自动读取或迁移。旧凭据应由用户自行安全清理，不要提交或同步。

## 快速开始

```shell
lc login
lc status
lc profile
lc show
lc get 1
lc config editor zed
lc init
lc doctor
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
| `lc init <path> --repair` | 先备份，再恢复损坏的用户配置和目标工作区 marker；保留解法 |
| `lc login` | 依次尝试 Chrome、Edge 和手动 Cookie |
| `lc login --browser chrome\|edge` | 只使用指定浏览器，失败后进入手动登录 |
| `lc status` / `lc profile` | 检查登录态或展示账号信息 |
| `lc show` / `lc get <题号>` | 查看题目列表或详情 |
| `lc config editor [程序] [--arg=参数]` | 查看或设置用户编辑器；`--arg` 可重复，`--clear` 移除设置 |
| `lc solve <题号> [--editor 程序]` | 生成 `solution.py`，使用已配置或临时指定的编辑器 |
| `lc solve <题号> --no-open` | 只保存解法，不请求打开编辑器 |
| `lc test [--timeout 秒数]` | 交互调用 `Solution` 的首个公开方法 |
| `lc test --stdin` | JSON Lines 模式，适合 AI 或 CI |
| `lc test --verbose` | 显示完整异常调用栈；也可配合 `--stdin` |
| `lc doctor [--run-solution]` | 检查工作区、Session 和网络；可选择执行解法 |
| `lc submit [--wait-timeout 秒数]` | 提交 marker 区域并限时等待判题；仅 Accepted 返回 0 |
| `lc check <Submission ID>` | 查询一次已有提交的当前状态，不会重新提交代码 |

`config editor`、`login`、`status`、`profile`、`show`、`get`、`check` 和不带 `--run-solution` 的 `doctor` 不要求先初始化工作区。账号和题目命令需要有效 Session；`doctor` 在 Session 缺失时仍会诊断并返回失败。`solve`、`test`、`submit` 和 `doctor --run-solution` 需要已配置的工作区。

解法保存成功但未配置编辑器或启动失败时，`solve` 显示保存路径和警告，仍返回 0；写入失败则返回 1，并且不打开文件。

用户配置或 marker 损坏时，普通 `init` 不覆盖它们。明确修复目标后执行：

```powershell
uv run lc init D:/Projects/leetcode-local-cli --repair --yes
```

修复前会在损坏文件旁创建 `原文件名.<随机标识>.bak`，保留原始字节。后续失败会尝试回滚本次文件变化，已创建的备份保留供恢复；版本、站点或语言不受支持，以及链接或权限问题，不会被 `--repair` 强行覆盖。

## 编辑器配置

编辑器属于当前用户的个人设置，存入用户配置目录的 `config.toml`，不存入工作区 marker 或 Session。尚未初始化时也可设置；之后初始化或切换默认工作区会保留它。

用户配置格式现为 v2，工作区 marker 仍为 v1，Session 格式不变。已有 v1 用户配置（含内测编辑器设置）可继续读取，读取不改写文件；显式设置/清除编辑器或执行 `init` 时才保存为 v2。也可用 `uv run lc config editor zed` 保存并升级。升级后旧版 `lc` 会拒绝该配置，不能用旧版 `init --repair` 降级；开发期间请统一使用 `uv run lc`。

```shell
lc config editor zed
lc config editor code --arg=--reuse-window
lc config editor
lc solve 1 --editor zed
lc solve 1 --no-open
lc config editor --clear
```

`zed`、`code` 和别名 `vscode` 从 PATH 查找，也可指定可执行文件绝对路径。可重复的 `--arg` 按参数数组原样传递，路径最后追加；不支持 Shell 命令串或文件占位符。配置不自动安装编辑器。

优先级为：`--no-open` 禁止打开；否则 `--editor` 覆盖用户配置，且不继承旧编辑器的参数；没有临时参数时使用用户设置。不增加工作区或环境变量覆盖层。

未配置时只保存并提示，不使用系统 `.py` 文件关联，避免关联到 Python/uv 后意外执行代码。显式配置失败也不静默回退。Windows 的 VS Code 标准 `code.cmd` 入口会解析为安装目录的 `Code.exe`，其他 `.cmd`/`.bat` 编辑器入口拒绝执行。启动后短时间内非零退出会警告；GUI 持续运行视为请求已发出，不强行终止，也不保证窗口一定可见。

## 浏览器登录

首次使用浏览器自动登录前：

1. Chrome 打开 `chrome://inspect/#remote-debugging`；Edge 打开 `edge://inspect/#remote-debugging`。
2. 勾选 **Allow remote debugging for this browser instance**，再执行 `lc login`。
3. CLI 优先尝试日常 Chrome，再尝试日常 Edge；如果设置页面没有自动显示，请手动打开上述地址。
4. 出现 **Allow remote debugging?** 连接确认框时选择 **Allow**，并保持 LeetCode 页面已登录。
5. CLI 只获取 `leetcode.cn` 的 `LEETCODE_SESSION` 和 `csrftoken`，在线验证后保存。
6. 自动登录失败时，回退到隐藏输入的手动 Cookie。

CLI 不读取或解密浏览器 Cookie 数据库，不创建专用 profile，也不关闭日常浏览器。授权等待上限为 180 秒。

## 本地调用

`lc test` 自动选择 `Solution` 中第一个不以 `_` 开头的实例方法。输入安全 Python 字面量参数：

```text
参数 > nums = [3, 2, 4], target = 6
```

连续两次回车退出。每组默认限时 1 秒；无输入、参数错误、异常或超时返回退出码 1。退出码 0 只表示调用正常完成，不代表算法正确。

支持按入口类型注解转换节点：`ListNode`、`TreeNode`、`Optional[...]`、`... | None`，以及相应的字符串注解。普通 `list` 保持列表含义，不根据参数名猜类型；节点参数缺少注解时请补齐。嵌套节点集合及混合节点类型注解会明确拒绝。

启用 `from __future__ import annotations` 不改变这些规则，`list["ListNode"]` 同样拒绝。`Literal["ListNode"]` 中的字符串是取值，`Annotated[int, "ListNode"]` 中的字符串是元数据，均不触发节点转换；`Annotated[ListNode, ...]` 等节点包装暂不支持。

```text
l1 = [2,4,3], l2 = [5,6,4]
root = [1,null,2,3]
```

链表用整数数组；树用力扣式层序数组，`null` 与 `None` 都表示空位（字符串 `"null"` 不受影响）。空数组或 `null`/`None` 表示空节点；树中无法连接到根的非空值会被拒绝。返回节点转换回同类数组，树尾多余空位移除；有节点返回注解时空节点输出 `[]`。普通方法返回 `None` 时，展示调用后的参数，节点参数也转回数组。

生成模板提供位于提交区域外的本地节点定义，不将这些辅助定义发送给 LeetCode。第一版只支持整数节点的无环单链表和普通二叉树，不支持环、共享节点身份、随机指针、N 叉树、嵌套节点集合及设计题多方法调用。单个节点数组输入最多 100,000 项，输出最多 100,000 个节点；超过限制明确失败，不截断为成功。

非交互示例：

```shell
printf 'nums = [3, 2, 4], target = 6\n' | lc test --stdin
```

`--stdin` 的运行时启动失败（包括未初始化工作区）也输出 JSON Lines，包含 `kind: startup_error`、稳定的 `code` 和中文 `error`，退出码为 1。非法 CLI 参数仍使用标准用法错误，退出码为 2。

异常默认显示类型、原因和可定位的 `solution.py` 行号，并保留 stdout/stderr；`--verbose` 增加完整调用栈，不采集局部变量。JSON 模式通过 `error_line` 和可选 `traceback` 字段表达，不混入 Rich 文本。调用栈仍可能包含源码片段、路径及异常内容，共享前请自行检查。

某组超时后，下一组会重启 worker；若重新加载失败，该组报告失败并保留行号及可选调用栈，后续输入仍可继续尝试。

`lc submit` 取得 submission ID 后默认等待判题 30 秒。判题查询只在总预算内有限重试；初始提交 POST 不自动重试，避免重复提交。等待超时或查询失败时会保留 submission ID，并返回退出码 1。

等待超时后可执行 `lc check <Submission ID>` 重新查询。该命令只请求一次：已经判题则展示结果，仍在判题则提示稍后重试；只有结果为 Accepted 时返回退出码 0。

## 安全与限制

- 当前只支持 LeetCode 中文站和 Python3 提交。
- HTTP 凭据仅发往 `https://leetcode.cn` 的默认 HTTPS 端口，拒绝全部重定向；不自动切换到其他域名、子域名或 HTTP 地址。
- Session 包含真实 Cookie，保存在当前系统用户的本地状态目录：Windows 为 `%LOCALAPPDATA%\leetcode-local-cli\session.json`，macOS 为 `~/Library/Application Support/leetcode-local-cli/session.json`，Linux 为 `${XDG_STATE_HOME:-~/.local/state}/leetcode-local-cli/session.json`。不得提交、上传、同步或共享。
- 工作区 marker 保存在 `.leetcode_local_cli/workspace.toml`，属于本机工作区元数据；建议忽略，不提交。CLI 不自动修改用户仓库的 `.gitignore`。
- 本项目源码仓库忽略根目录 `solution.py`；开发者可将工作区与源码放在一起，个人解法不属于工具源码。普通用户仍可自选独立工作区。
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
