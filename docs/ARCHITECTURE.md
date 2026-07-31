# 当前架构

最近更新：2026-08-01

本文描述 `v0.9.0` 的真实架构。长期 API、双站点和 UI 方向见 [PROJECT_DESIGN](PROJECT_DESIGN.md)，未实现内容不得视为当前能力。

## 整体架构

程序仍是同步 Python CLI，但路径解析已经从业务模块中抽离。Typer 命令在执行具体业务前读取用户配置，构造一个不可变 `AppPaths`，再把明确的 Session 和 `solution.py` 路径传给认证、service、Doctor 与工作区模块。

```mermaid
flowchart TD
    USER["用户或安装脚本"] --> CLI["Typer CLI"]
    CLI --> CONFIG["config 配置与初始化"]
    CONFIG --> PATHS["AppPaths 运行路径"]
    CONFIG --> USERCFG["用户 config.toml"]
    CONFIG --> WORKCFG["工作区 .leetcode-local-cli.toml"]
    CLI --> SERVICE["service 流程编排"]
    CLI --> AUTH["auth 登录与 Session"]
    CLI --> BROWSER["浏览器选择与授权发现"]
    CLI --> WORKSPACE["workspace 解题文件"]
    SERVICE --> AUTH
    SERVICE --> CLIENT["LeetCodeClient"]
    SERVICE --> DOCTOR["doctor 结构化诊断"]
    SERVICE --> WORKSPACE
    WORKSPACE --> TESTRUNNER["持久本地执行 worker"]
    TESTRUNNER --> SOLUTION
    AUTH --> SESSION["工作区 Session JSON"]
    BROWSER --> CHROME["日常 Chrome DevToolsActivePort"]
    BROWSER --> EDGE["日常 Edge DevToolsActivePort"]
    BROWSER --> AUTH
    WORKSPACE --> SOLUTION["工作区 solution.py"]
    AUTH --> SAFEFILES["safe_files 安全写入"]
    CONFIG --> SAFEFILES
    WORKSPACE --> SAFEFILES
    CLIENT --> CN["leetcode.cn HTTPS API"]
    CLI --> UI["Rich UI"]
```

工具安装目录不参与用户文件定位。通过 uv、wheel、源码或模块入口启动时，普通命令都读取同一份默认工作区配置。

## 模块职责

| 模块 | 当前职责 | 边界 |
| --- | --- | --- |
| `paths.py` | 跨平台用户配置目录、工作区文件名和不可变 `AppPaths` | 只依赖标准库，不导入 CLI、auth 或 workspace |
| `config.py` | 版本化 TOML 解析、默认工作区解析、非破坏初始化 | 不负责交互文案；配置损坏时拒绝覆盖 |
| `safe_files.py` | 普通目标校验、链接/reparse 拒绝、排他创建、随机临时文件和原子替换 | 不理解 LeetCode 业务，只提供文件系统安全原语 |
| `solution_source.py` | 统一读取 UTF-8/UTF-8 BOM 的 `solution.py`，把解码失败转换为专用异常 | 不猜测编码、不替换非法字节、不修改用户文件 |
| `cli.py` | 命令、参数、交互确认、路径解析、错误和退出码映射 | `--help`、`--version` 不解析工作区；业务命令需要有效默认工作区 |
| `browser.py` | 浏览器选择、日常 Chrome/Edge 可执行文件与 `DevToolsActivePort`、浏览器身份检查 | 不读取 Cookie、不使用 Shell、不拥有或关闭日常浏览器 |
| `auth.py` | 浏览器无关的受限 DevTools Cookie 请求、手动 Cookie，以及 Session 保存读取与静态检查 | DevTools 只连接回环端口；Session 路径必须由调用者传入；当前只支持 `leetcode.cn` |
| `workspace.py` | 模板、原子写入、打开、执行、静态检查和提交 marker 解析 | 所有公开工作区操作必须接收明确文件路径 |
| `local_testing.py` | 安全解析 `name = value` 参数，并编码 worker JSON 协议 | 只接受受支持的 Python 字面量；不执行用户输入 |
| `_test_runner.py` | 持久 worker：加载解题文件、发现 `Solution` 首个公开实例方法并处理逐组调用 | 每组创建新的 `Solution` 实例；不接收 Shell 或直接 Python 表达式 |
| `service.py` | 账号、题目、Doctor 和提交流程编排 | 仍直接依赖 Typer 与 UI，是后续架构阶段需要继续解耦的过渡层 |
| `doctor.py` | 把 Session、工作区和远端状态转成结构化检查结果 | 默认不执行用户代码 |
| `client.py` | 中文站 HTTP、GraphQL、提交和判题查询 | 同步 httpx、固定 Python3 |
| `problem.py` | 题号解析与题目模型标准化 | 基本是无 IO 的纯逻辑 |
| `ui.py` | 外部文本安全过滤和 Rich 展示 | 不决定业务规则 |

## 配置与目录

Windows 示例：

```text
C:/Users/<user>/AppData/Roaming/leetcode-local-cli/
└── config.toml

D:/Projects/leetcode-local-cli/
├── .leetcode-local-cli.toml
├── solution.py
└── .leetcode_local_cli/
    └── session.json
```

用户配置只保存非秘密字段：

```toml
version = 1
default_workspace = "D:/Projects/leetcode-local-cli"
default_site = "cn"
```

工作区配置只保存当前版本、站点和语言：

```toml
version = 1
site = "cn"
language = "python3"
```

Cookie 仍只存在 Session JSON。这个 v0.8 阶段性决定服务于维护者授权的真实验收，不代表长期安全架构。

## 核心数据流

### 初始化

1. `lc init` 先读取现有用户配置；损坏时立即停止，不覆盖。
2. 无显式路径且已有有效默认工作区时，直接返回复用结果。
3. 无路径时交互读取父目录并追加 `leetcode-local-cli`；显式路径按完整工作区处理。
4. `config.initialize_workspace()` 验证工作区、标记文件和 `solution.py` 均不是链接、目录或 reparse point。
5. 缺少的工作区配置和空 `solution.py` 被创建；已有普通文件保持不变。
6. 最后原子写入用户配置。失败时只清理本次创建的工作区文件，不删除预先存在内容。

### 普通命令

```text
CLI 命令
→ resolve_app_paths()
→ 用户 config.toml
→ 工作区标记验证
→ AppPaths
→ 将 session_file / solution_file 显式传给用例
```

因此当前终端目录不再决定业务文件位置。没有有效配置时，命令以非零状态提示执行 `lc init`。

### 登录

`lc login` 解析默认工作区后，默认先尝试当前日常 Chrome，再尝试当前日常 Edge。两条路径由 `browser.py` 共用同一授权发现逻辑：读取各自默认用户数据目录中的普通 `DevToolsActivePort`；缺少授权时用 `--new-window` 打开 `chrome://inspect/#remote-debugging` 或 `edge://inspect/#remote-debugging` 和 LeetCode，等待用户勾选 **Allow remote debugging for this browser instance**。授权前不会产生端口文件，CLI 只轮询等待，不尝试绕过这一步用户同意。

approval-only 端点可能让传统 `/json/version` 返回 404，因此 CLI 直接连接文件给出的浏览器 WebSocket，在同一连接中依次调用 `Browser.getVersion`、`Target.getTargets`、`Target.attachToTarget` 和页面会话内的 `Network.getCookies`。Chrome 身份必须报告 `Chrome/`，Edge 身份必须报告 `Edg/`。`DevToolsActivePort` 可能在浏览器关闭后暂时遗留，因此“文件存在”不等于“实例可连接”：端点暂时不可达或后台实例返回 403 时，CLI 只打开一次可见窗口，并在同一个 180 秒单调时钟预算内重新读取文件、有限重试临时连接错误；浏览器身份、协议结构等确定性错误立即失败。日常浏览器不是 CLI 持有的进程，因此任何结果下都保持运行。

显式 `--devtools-port` 仍由 `auth.py` 访问 `127.0.0.1:<端口>/json/list` 并选择页面 WebSocket。日常浏览器则使用上段的 approval-only 浏览器 WebSocket。所有路径都验证端点属于同一个回环端口，调用 `Network.getCookies` 时仅请求 `https://leetcode.cn/`，并只提取两个必需 Cookie，随后复用相同的在线验证和 Session 原子写入链路。HTTP 发现禁用环境代理和重定向。CLI 不关闭日常浏览器或显式外部端口对应的实例。

### 题目生成与写入

`lc solve` 获取题目后，把内容交给 `workspace.write_solution_file(paths.solution_file, ...)`。写入先验证目标，然后在同目录创建不可预测的排他临时文件，完整写入并 `fsync`，再次验证目标后使用 `os.replace` 原子替换。旧文件在写入失败时保持不变。

### 测试、Doctor 与提交

- `solution_source.read_solution_source()` 是三条链路共享的解码边界；非 UTF-8 在任何编译、执行或提交解析之前转换为 `INVALID_ENCODING` 或 `WorkspaceError`。
- `lc test` 先静态检查明确的 `solution.py`，再由 `workspace.LocalExecutionWorker` 启动 `_test_runner` 子进程。
- runner 使用共享 UTF-8 解码边界执行解题文件，在 `Solution.__dict__` 的定义顺序中选择第一个不以 `_` 开头的实例方法；其他类与后续公开辅助方法不作为入口。
- CLI 使用 `local_testing.parse_parameter_assignments()` 将 `name = value` 输入限制为安全字面量，再经 JSON 行协议发送给 worker。每一组在新的 `Solution` 实例上执行，结果、stdout、stderr 与被原地修改的参数可受控返回。
- 每组调用独立使用默认 1 秒超时；超时时父进程终止 worker，下一组输入自动重新加载。CLI 在交互模式安全渲染 Rich 文本，在 `--stdin` 模式输出 JSON Lines；任一输入错误、异常或超时使最终退出码为 1。
- Doctor 使用同一 Session/solution 路径，默认只静态检查。
- 提交只读取明确路径中的 marker 区域并使用同工作区 Session，不调用 `lc test` 或执行本地输入。
- 提交结果先由 UI 展示，再由 CLI 映射退出码：仅 `status_msg == "Accepted"` 返回 0；其他终态、缺失终态和轮询超时返回 1。

## 模块依赖关系

```text
__main__ -> cli
cli -> config, paths, browser, auth, service, ui, workspace
browser -> paths, safe_files, auth, subprocess
config -> paths, safe_files, tomllib
service -> paths, auth, client, doctor, problem, ui, workspace, typer
doctor -> auth, client result types, workspace
auth -> httpx, websockets, safe_files
workspace -> safe_files, local_testing, subprocess, platform file opener
workspace -> solution_source
_test_runner -> local_testing, solution_source, Python standard library
solution_source -> Python standard library
client -> httpx
ui -> rich, doctor result types
problem -> Python standard library
paths -> Python standard library
safe_files -> Python standard library
```

禁止 `paths` 或 `safe_files` 反向导入 CLI 和业务模块。

## 设计原则

1. 路径由运行上下文提供，不从导入时当前目录推断。
2. 安装位置、用户配置、工作区和凭据是不同生命周期的资源。
3. 初始化幂等且非破坏；业务切题命令才允许覆盖普通解题文件。
4. 外部配置和文件系统目标是不可信输入，损坏或不支持时拒绝猜测。
5. 文件写入使用随机同目录临时文件和原子替换，链接与 reparse point 不可作为目标。
6. 核心路径、配置和文件原语不依赖 Typer/Rich。
7. Cookie 不得进入输出、异常、测试 fixture、提交或发布产物。
8. 当前保持单文件、中文站、Python3 和同步实现，不借 v0.8 扩大产品范围。
9. 本地交互执行是用户主动选择的代码执行；入口发现、安全参数解析、每组独立超时和受控错误必须由 CLI 保证，远程提交不依赖它。
10. 用户解题文件只按 UTF-8/UTF-8 BOM 解码；编码不确定时拒绝，不通过猜测、替换或自动改写掩盖错误。
11. 终端文案与机器退出码必须表达同一业务结果；显示错误不能同时返回成功状态。

## 仍需演进的边界

- service 仍通过 `typer.Exit` 和 UI 函数控制错误与展示。
- Session 仍是工作区明文 JSON，系统秘密存储延后。
- Python API、双站点适配器和稳定异常模型尚未实现。
- 单文件工作区是当前阶段决定，v0.14 API 冻结前仍需评估长期模型。
