# 项目状态

最近更新：2026-07-31

当前开发状态：`v0.8.0` 之后的未发布修复

当前发布状态：`v0.8.0` 已发布到 PyPI 和 GitHub Releases。

本文是项目长期开发上下文的状态入口，只记录源码、测试和当前文档已经确认的事实。用户可见行为以 [README](../README.md) 和 [产品边界](PRODUCT_BOUNDARIES.md) 为准；安全问题以 [安全审计](SECURITY_REVIEW.md) 为准。

## 当前项目目标

`leetcode-local-cli` 是面向 LeetCode 中文站的轻量、在线优先、本地刷题 CLI。当前版本通过一个显式配置的默认工作区维护单个 `solution.py`，支持登录、题目查询、本地测试、诊断和远程提交，不引入本地数据库、完整题库或每题独立目录。

长期目标仍是形成共享核心实现的稳定 CLI 与 Python API，并支持中文站和国际站。长期设计中的双站点、系统秘密存储、图片和 UI 改造尚未实现。

## 已完成功能

### v0.8 运行上下文与工作区

- 新增不可变 `AppPaths`，集中描述用户配置、工作区配置、`solution.py` 和 Session 路径。
- `auth.py`、`workspace.py`、`doctor.py` 和 service 调用链都显式接收路径，不再在模块导入时捕获 `Path.cwd()`。
- 跨平台用户配置位置遵循 Windows `%APPDATA%`、macOS `Application Support` 和 Linux `XDG_CONFIG_HOME`/`~/.config`。
- 新增版本化用户配置 `config.toml` 和工作区标记 `.leetcode-local-cli.toml`。
- 新增 `lc init [path]`：无路径时交互输入父目录并追加 `leetcode-local-cli`；显式路径表示完整工作区路径；`--yes` 仅允许与显式路径组合。
- 初始化不存在的工作区时创建目录、工作区配置和空 `solution.py`；已有普通 `solution.py` 保持原内容；重复初始化幂等。
- 损坏配置、符号链接、断链、目录目标、junction 和 Windows reparse point 会被拒绝，不会绕过验证或静默覆盖。
- 所有普通命令从用户配置读取默认工作区；当前版本不提供全局 `--workspace`。
- 官方安装脚本安装并验证绝对 `lc` 路径后，在可交互终端调用 `lc init`；非交互环境或 `LEETCODE_LOCAL_CLI_NO_INIT=1` 会跳过并给出手动命令。
- 更新安装时，`lc init` 检测到有效默认工作区后直接复用，不重新询问或修改工作区文件。

### 文件与 Session 安全

- `solution.py` 覆盖改用同目录随机临时文件、完整写入和原子替换；写入失败保留旧文件。
- Session 写入同样使用随机临时文件和原子替换，并拒绝非普通目标。
- Session 暂时按已确认的阶段性方案保存在默认工作区的 `.leetcode_local_cli/session.json`，以支持维护者授权的真实账号验收。
- 不迁移或删除旧 `.aether_lc/session.json`；当前无人使用旧版本，用户需要重新登录。
- `.leetcode_local_cli/` 继续由仓库 `.gitignore` 排除，诊断和错误输出不得包含 Cookie 值。

### 既有用户工作流

- `lc login`、`status`、`profile`、`show`、`get`、`solve`、`test`、`doctor` 和 `submit` 的核心能力保持。
- 当前仍只正式支持 LeetCode 中文站和 Python3 提交。
- `lc doctor` 默认不执行用户代码；只有 `--run-solution` 才执行。
- `lc solve` 仍表示切换当前题目，因此可以无确认覆盖普通 `solution.py`。

### 未发布：`lc test` 可靠性修复

- `lc test` 现在在独立子进程中以非 `__main__` 名称加载 `solution.py`，并显式调用一次同步、无参数的 `run_cases()`。
- `run_cases()` 缺失、不可调用、仍为空实现、断言失败、运行时异常或超时都会返回退出码 1，不再产生“假通过”。
- 默认总超时为 10 秒；`--timeout` 可接受大于 0 的有限秒数，非法参数返回退出码 2。
- stdout 和简化错误会经过终端文本过滤后展示，用户异常不输出 traceback。
- `run_cases()` 仍是可选的本地调试能力；`lc submit` 不检查或执行它，并继续只提交 marker 区域。

## 当前开发阶段

v0.8 的运行上下文、配置、工作区初始化和安装器集成已经实现、发布并完成 Windows 与 Linux/WSL 双平台验收。当前源码已完成验收中 `lc test` 假通过与无限等待问题的修复，仍需收敛非 UTF-8 错误边界和远程提交退出码，再进入 v0.9 的领域模型、异常边界和 Python API 预览。

2026-07-30 验收结果：

- Windows 11：Ruff、Pyright、构建、wheel/sdist、隔离 uv tool 安装和全部 CLI 入口通过；`pytest` 为 198 passed、13 skipped。
- Windows 真实流程：隐藏手动 Cookie 登录、`status`、`profile`、`show`、`get`、`solve`、`test`、`doctor --run-solution` 均通过；经维护者授权对第 1 题执行一次真实提交，结果 Accepted。
- Ubuntu 26.04 WSL2：隔离源码、构建、安装器、默认工作区复用、符号链接边界和在线只读流程通过；`pytest` 为 210 passed、1 skipped。通过数差异来自 Windows 专属 junction 用例与 Linux 可执行符号链接用例的跳过条件不同，总收集数一致。
- `v0.8.0` 标签发布工作流在 Ubuntu、macOS 和 Windows 全部通过，随后成功发布 PyPI 和 GitHub Release。

2026-07-31 当前源码验证：

- Ruff format、Ruff lint 和 Pyright 全部通过。
- Windows 完整 pytest 为 231 passed、13 skipped。
- wheel 与源码包构建通过，构建产物包含内部 `_test_runner.py`；`lc --version` 和 `lc test --help` 入口通过。
- 定向测试确认默认/旧/等价空实现不会假通过，已填写入口只执行一次，stdout、异常、非交互 stdin、中文路径、超时和提交隔离符合 `PB-C12`。

## 未完成任务

### 下一批产品决策

- `lc test --verbose` 与 `lc doctor --run-solution` 的扩展调试输出策略。
- `lc submit` 对 Accepted、非 Accepted 和轮询超时的退出码。
- 提交前静态校验范围。
- 非 UTF-8 `solution.py` 的处理边界。
- 编辑器配置优先级和安全命令模型。
- 合法空分页、Broken Pipe 和正式支持的 Python 小版本。

### 长期任务

- 将 service 中的 Typer/Rich 依赖迁出核心业务层。
- 以类型模型和项目异常逐步替换裸字典与 `typer.Exit`。
- 提供 Python API 预览并建立站点适配器。
- 在后续版本重新设计系统秘密存储；v0.8 的明文 Session 不是长期安全终点。

## 当前问题

- `.leetcode_local_cli/session.json` 仍包含明文 Cookie；放入同步盘、共享目录或其他 Git 仓库存在泄露风险。
- 非 UTF-8 `solution.py` 会让 `lc test`、`lc doctor` 和 `lc submit` 暴露 `UnicodeDecodeError` traceback，尚未形成稳定编码错误边界。
- `lc submit` 对非 Accepted 判题和轮询超时仍可能返回退出码 0，Shell/CI 不能只依赖退出码判断通过。
- 在 Git 仓库根目录执行 `lc init` 会生成未自动忽略的 `.leetcode-local-cli.toml`，使工作树出现未跟踪文件；该标记应提交、忽略还是迁移尚未形成产品结论。
- Windows 上系统默认 `.py` 关联可能不是编辑器；当前行为仍按既有兼容边界保留。
- 普通 push 和 Pull Request 尚无日常 CI，标签工作流仍是主要发布门禁。

## 下一步计划

1. 确认 `PB-006`，收敛 `test`、`doctor` 和 `submit` 的非 UTF-8 错误边界。
2. 确认 `PB-003`，让非 Accepted 与轮询超时获得稳定的非零退出语义。
3. 确认 Git 工作区标记的版本控制与忽略策略，避免 `lc init` 长期制造不明确的工作树状态。
4. 决定 `PB-002` 的 verbose/Doctor 输出范围，并为普通 push 和 Pull Request 增加日常 CI。
5. 完成上述可靠性门禁后进入 v0.9 核心模型与异常边界迁移。
