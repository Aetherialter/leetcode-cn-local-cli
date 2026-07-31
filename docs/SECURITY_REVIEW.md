# 安全审计与修复清单

初次审计日期：2026-07-20

最近更新：2026-07-31

审计范围：`src/`、安装脚本、发布工作流、运行时依赖，以及 v0.8 路径、配置、工作区与 Session 变更。

## 总体结论

v0.8 已消除导入时当前目录路径、`solution.py` 直接截断写入和固定 Session 临时文件三项高风险实现。用户配置、工作区标记、解题文件和 Session 都通过显式 `AppPaths` 定位；写入目标拒绝符号链接、断链、目录、junction 和 Windows reparse point；覆盖使用随机同目录临时文件和原子替换。

当前最高剩余风险是维护者明确选择的明文 Session JSON。它服务于 AI 使用真实账号执行授权端到端测试，但不等同于安全秘密存储，不能进入 Git、同步盘、共享目录、日志或报告。

## 当前风险

| ID | 等级 | 问题 | 主要影响 | 状态 |
| --- | --- | --- | --- | --- |
| SR-002 | 高 | Cookie 明文保存在默认工作区 | Session 泄漏、误提交或同步 | 阶段性接受，长期待替换 |
| SR-003 | 中 | 系统关联自动打开 `.py` | Windows 上可能使用非编辑器关联 | 已接受，后续配置 |

## 已修复风险

### 显式路径与默认工作区

- `auth.py` 和 `workspace.py` 不再定义导入时 `Path.cwd()`、`PROJECT_ROOT`、固定 `SOLUTION_FILE` 或固定 `SESSION_FILE`。
- 普通命令先读取系统用户配置，再验证版本化工作区标记，最后把明确路径传入核心模块。
- `--help` 和 `--version` 不读取配置；未初始化的业务命令清晰提示 `lc init`。
- 损坏、未知版本和结构异常的 TOML 不会被静默覆盖。

### `solution.py` 写入事务

- 只允许不存在或普通文件目标。
- 同目录使用不可预测的排他临时文件，完整写入、flush、fsync 后再次验证目标。
- 使用 `os.replace` 替换目录项，不跟随目标符号链接。
- 写入、权限或占用失败时临时文件被清理，旧 `solution.py` 保持不变。
- `lc init` 与 `lc solve` 的语义分离：初始化保留已有普通解法，切题命令允许原子覆盖。

### Session 写入事务

- 删除固定 `session.json.tmp` 路径。
- Session 目录和文件目标都拒绝链接、目录和 reparse point。
- POSIX 上目录使用 `0700`、文件使用 `0600`。
- JSON 序列化在写入前完成，失败不会产生 Session 文件。
- Doctor、异常和测试结果只包含安全元数据或缺失 Cookie 名称。

### 初始化与安装器

- `lc init` 先验证已有用户配置、工作区配置和文件目标，再执行创建。
- 初始化失败只回滚本次创建的文件，不删除预先存在的用户内容。
- `--yes` 只能与显式完整路径组合，不能绕过安全校验。
- 官方安装器使用 uv 工具 bin 目录中的绝对 `lc`，不依赖终端 PATH 刷新。
- POSIX 管道安装通过 `/dev/tty` 交互；非交互、CI 或显式 `LEETCODE_LOCAL_CLI_NO_INIT=1` 不等待输入。
- 初始化失败不会卸载已经成功安装的工具，但安装脚本返回失败并给出恢复命令。

### `lc test` 假通过与无限等待

- 内部 runner 在入口缺失时先通过 AST 拒绝，不会为了判断入口而执行文件顶层代码。
- 默认模板、旧模板和等价无操作 `run_cases()` 都返回未配置状态，不再显示测试通过。
- 有效入口在独立子进程中以非 `__main__` 名称加载并只调用一次；断言、运行异常和超时映射为稳定非零状态。
- 子进程默认总超时为 10 秒，调用使用参数数组且不启用 Shell。
- 用户 stdout 和简化错误经过控制字符过滤；异常不把 Python traceback 直接展示给普通 CLI 用户。
- 该控制不是沙箱。用户代码仍拥有当前账号权限，也可能创建自己的子进程或持久化副作用，只能在可信工作区中运行。

## 明文 Session 的阶段性控制

目录结构：

```text
<workspace>/.leetcode_local_cli/session.json
```

必须遵守：

- `.leetcode_local_cli/` 必须保持在仓库 `.gitignore` 中。
- 不得把 Session 内容打印、粘贴到报告、提交到 Git 或上传到 Issue。
- AI 真实验收只能在维护者明确授权时读取并使用该文件。
- CI 使用假 Cookie 和 MockTransport，不执行真实远程提交。
- 推荐使用专门测试账号；主账号提交记录和站点风控不属于自动化可恢复资源。
- `lc init`、升级和卸载都不删除或覆盖 Session；用户负责其生命周期。

未来系统秘密存储实施时，需要重新设计 Windows Credential Manager、macOS Keychain、Linux Secret Service、无后端降级和明文 Session 迁移。v0.8 不承诺自动迁移旧文件。

## 其他剩余可靠性风险

| ID | 等级 | 问题 |
| --- | --- | --- |
| RT-002 | 中 | 非 UTF-8 `solution.py` 会让 `test`、`doctor`、`submit` 暴露 `UnicodeDecodeError` traceback |
| RT-004 | 中 | 非 Accepted 判题和轮询超时可能仍返回退出码 0 |
| RT-005 | 低 | Broken Pipe 可能产生假失败 |
| RT-006 | 低 | 极大分页偏移的错误归因不够准确 |
| RT-007 | 低 | Git 仓库作为工作区时，未自动忽略的 `.leetcode-local-cli.toml` 会使工作树变脏 |

## v0.8.0 双平台验收证据

2026-07-30 的脱敏验收补充了以下真实证据：

- Windows 11 完成隐藏手动 Cookie 登录、Session 跨命令复用、在线只读流程、Doctor、本地执行和一次维护者授权的 Accepted 提交。
- Ubuntu 26.04 WSL2 完成隔离构建、安装器、XDG 配置、POSIX Session 权限、符号链接/断链拒绝和在线只读流程；为避免重复远端副作用，没有再次真实提交。
- 两个平台都没有在报告、构建产物或 Git 跟踪内容中发现 Cookie；Windows Session 在在线命令前后保持不变。
- 发布标签的 Ubuntu、macOS、Windows 自动化门禁、wheel/sdist smoke test、PyPI Trusted Publishing 和 GitHub Release 均成功。

这些结果证明已执行范围内的控制有效，但不替代独立物理 Linux、真实 macOS、不同浏览器密钥后端或长期秘密存储验证。

## 已有安全措施

- LeetCode 客户端基础地址固定为 HTTPS。
- 子进程使用参数列表，不使用 `shell=True`。
- GraphQL 使用变量传值，不拼接用户输入。
- 手动 Cookie 输入不回显。
- 外部文本经过控制字符过滤并作为纯文本交给 Rich。
- `.leetcode_local_cli/`、`.aether_lc/`、常见凭据 JSON、环境文件和个人编辑器目录已忽略。
- 仓库测试扫描已跟踪 JSON 的高风险秘密字段，不输出字段值。
- GitHub Actions 的第三方 Action 固定到提交 SHA。
- PyPI 发布使用 OIDC Trusted Publisher，不保存 PyPI Token。

## 发布前验证要求

- Ruff format、Ruff lint、Pyright 和完整 pytest。
- wheel 和源码包构建与入口 smoke test。
- Windows、macOS、Linux 安装器非交互路径自动测试。
- 三平台真实交互初始化需要手动验收。
- 真实 Cookie 和远程提交只在明确授权环境验证，报告必须脱敏。

2026-07-31 的未发布 `lc test` 修复已在 Windows 通过 Ruff、Pyright、231 passed/13 skipped 的完整 pytest、wheel/sdist 构建与 CLI 入口检查；没有执行真实远程提交，也没有读取真实 Session。
