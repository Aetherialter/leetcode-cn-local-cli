# 项目状态

最近更新：2026-07-30

当前开发版本：`v0.8.0`

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

## 当前开发阶段

v0.8 的运行上下文、配置、工作区初始化和安装器集成已经实现，并已完成本地发布前质量门禁。下一阶段是 v0.9 的领域模型、异常边界和 Python API 预览，不应在 v0.8 中继续扩大功能范围。

当前本地验证结果：Ruff format/check、Pyright、构建、`lc --version` 和 `lc --help` 均通过；`pytest` 为 198 passed、13 skipped。Windows 隔离安装冒烟测试已使用 v0.8.0 wheel 通过官方 PowerShell 安装脚本完成，验证了安装后绝对路径调用、首次初始化和项目外复用默认工作区。

## 未完成任务

### 下一批产品决策

- `lc test` 是否必须验证或主动调用 `run_cases()`，以及超时和输出策略。
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
- `lc test` 仍可能把缺少有效测试入口的可编译脚本判定为通过，且没有超时。
- 非 Accepted 判题和轮询超时尚未统一返回非零退出码。
- Windows 上系统默认 `.py` 关联可能不是编辑器；当前行为仍按既有兼容边界保留。
- 普通 push 和 Pull Request 尚无日常 CI，标签工作流仍是主要发布门禁。

## 下一步计划

1. 完成 v0.8.0 全量质量、构建、入口和隔离安装验证。
2. 对官方安装脚本在真实 Windows、macOS 和 Linux 交互终端执行手动验收。
3. 在明确授权下，使用不会输出 Cookie 的真实账号流程验证一次远程提交。
4. 进入 v0.9 前先确定本地测试和远程提交的剩余产品语义。
