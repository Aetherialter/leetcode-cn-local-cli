# 安全审计与修复清单

初次审计日期：2026-07-20

最近更新：2026-07-28

审计范围：`src/`、安装脚本、发布工作流、当前运行时依赖，以及 v0.7.2 Windows/Linux 跨平台测试报告

状态：本文只保留当前尚未解决的问题；已经修复并完成回归验证的问题从清单和详细章节中移除，历史记录由 Git 保留。

产品行为是否属于缺陷，先以 [产品边界与待定决策](PRODUCT_BOUNDARIES.md)中的已确认结论为准；未定行为不得仅凭实现现状视为最终设计。

## 总体结论

当前项目没有监听网络端口，也未发现无需用户操作即可通过远程请求直接控制程序的漏洞。当前主要攻击面来自本地工作区、明文登录凭据和通过系统关联打开 Python 文件。

当前源码已修复 `lc solve` 对预先存在的非普通 `solution.py` 目标的跟随写入：目标不存在时创建、普通文件覆盖，符号链接、断链、目录、目录链接和 Windows reparse point 在写入前被拒绝。剩余写入风险主要是检查与直接打开之间的竞争窗口、尚未定义的原子写入保证，以及 Session 固定临时文件路径。

## 风险清单

| ID | 等级 | 问题 | 主要影响 | 状态 |
| --- | --- | --- | --- | --- |
| SR-002 | 高 | Cookie 明文保存在当前目录 | Session 泄漏、误提交或同步 | 待修复 |
| SR-003 | 中 | 系统关联自动打开 `.py` | Windows 上可能直接执行生成文件 | 已接受，后续配置 |
| SR-004 | 高 | Session 写入未防御链接目标；工作区写入尚缺事务级防护 | 覆盖其他文件，或写入失败时损坏旧解法 | 部分修复 |

## 详细发现

### SR-002：Session Cookie 明文绑定当前目录

`auth.py` 在模块导入时使用 `Path.cwd()` 确定 `.leetcode_local_cli/session.json`，并将 `LEETCODE_SESSION` 与 `csrftoken` 写入普通 JSON 文件。

风险包括：

- 在其他 Git 仓库中登录后，凭据可能被意外提交。
- 工作目录位于同步盘或共享目录时，凭据可能被复制到其他设备或账号。
- Windows 上 `os.chmod(..., 0o600)` 不能替代可靠的仅当前用户可读 ACL。

修复要求：

- 凭据迁移到 Windows Credential Manager、macOS Keychain 或 Linux Secret Service。
- 用户配置目录和工作区目录必须分离。
- 秘密存储不可用时明确失败或仅在当前进程中使用，不得静默明文降级。
- 迁移和诊断过程不得输出 Cookie。

### SR-003：自动打开 Python 文件可能变成执行

`workspace.write_solution_file()` 写入远端返回的 Python 模板后立即调用 `open_path()`。Windows 实现使用 `os.startfile()`，行为等同于使用系统默认关联打开文件。如果 `.py` 关联到 Python 解释器，生成文件可能被直接执行。

修复要求：

- 默认只打印生成文件路径。
- 打开编辑器改为显式 `--open` 或经过配置的编辑器命令。
- 不使用 `.py` 的通用系统关联推断编辑器。

### SR-004：工作区与 Session 写入目标劫持

该问题包含两个独立写入路径。

v0.7.2 的 `workspace.write_solution_file()` 使用 `open(SOLUTION_FILE, "w")` 直接写入当前工作区的 `solution.py`。普通写模式会跟随符号链接；恶意工作区可以预先放置同名符号链接、目录链接或 Windows reparse point，使 `lc solve <题号>` 将生成内容写到工作区以外。

当前产品采用单题、单文件工作流。用户执行新的 `lc solve <题号>` 即表示切换当前题目，因此无确认覆盖普通 `solution.py` 是已确认的产品行为，不属于本安全问题。风险只在目标不是预期的普通文件、实际写入位置与界面展示位置不一致时成立。

v0.7.2 Linux/WSL 实测已确认：

- `solution.py` 指向现存普通文件时，`lc solve` 保留符号链接并覆盖链接目标。
- `solution.py` 是断链时，`lc solve` 会在链接指向的位置创建新文件。
- 现存目标覆盖复现 2/2，断链目标创建复现 1/1。
- Windows 尚未执行等价 reparse point 测试，但只读文件和独占文件锁均已确认会使直接写入失败并泄露完整 Traceback。

基于已经确认的数据破坏路径，SR-004 的风险等级由“中”提升为“高”。

当前源码于 2026-07-28 完成第一阶段修复：

- 使用 `Path.lstat()` 检查目录项本身，不跟随符号链接。
- 只允许目标不存在或为普通文件；符号链接、断链、目录、其他非普通文件及带 `FILE_ATTRIBUTE_REPARSE_POINT` 的 Windows 目标均拒绝写入。
- 校验和写入阶段的 `OSError` 转换为 `WorkspaceError`，`lc solve` 输出清晰错误并以状态 1 退出；只有写入成功后才尝试打开文件。
- 单元与 CLI 测试覆盖创建、普通覆盖、拒绝、外部目标保持不变和错误映射。实际 Windows junction 测试通过；当前 Windows 主机没有符号链接创建权限，对应测试显式跳过并由 POSIX 测试覆盖。
- 从本地 wheel 执行隔离的 `uv tool install` 后，已安装包中的相同工作区校验验证通过；安装方式不产生第二套写入逻辑。

这项修复仍不是无竞争的写入事务。`lstat()` 与后续 `open(..., "w")` 之间存在 TOCTOU 时间窗口，直接写入也不能保证中途失败时旧文件字节级不变。这部分必须等待 `PB-005` 的产品语义确定后处理。

Session 路径位于 `auth.save_session()`：

- `file_path.with_suffix(f"{file_path.suffix}.tmp")` 固定生成 `session.json.tmp`，名称可以被提前占用。
- `os.open()` 使用 `O_WRONLY | O_CREAT | O_TRUNC`，会复用并截断已经存在的临时路径，但没有使用排他创建，也没有拒绝跟随符号链接。
- `temporary_file.replace(file_path)` 可以保证正常情况下的最终替换是原子的，但不能消除打开固定临时路径时已经发生的目标劫持。

因此，攻击者可以在可控工作区中预先构造 `session.json.tmp`、父目录链接或 Windows reparse point，使保存登录态时覆盖当前用户有权写入的其他文件。该问题不扩大操作系统权限，但可能造成数据破坏；Session 内容本身还包含敏感 Cookie。

剩余修复要求：

- 在同一目标目录创建不可预测的随机临时文件，使用排他创建和适用平台的拒绝跟随链接机制。
- 完整写入后原子替换，并在替换前重新核对父目录、目标位置和文件类型。
- Session 写入加固与 SR-002 的用户配置目录、系统秘密存储和旧 Session 迁移一并设计，避免先固化即将废弃的工作区凭据路径。

## 跨平台测试补充问题

以下问题由 v0.7.2 Windows/Linux 报告确认。它们不扩大系统权限，因而不新增 `SR-*` 安全编号，但会影响错误边界、自动化可信度或用户数据安全，应纳入后续修复。

| ID | 等级 | 问题 | 主要影响 |
| --- | --- | --- | --- |
| RT-001 | 中 | `lc solve` 仍使用直接截断写入，尚无原子替换和失败后旧文件保证 | 中途写入失败可能损坏旧解法 |
| RT-002 | 中 | 非 UTF-8 `solution.py` 使 `lc test` 泄露 `UnicodeDecodeError` Traceback | 损坏或错误编码文件无法稳定诊断 |
| RT-003 | 中 | 非空脚本缺少 `run_cases()` 时仍显示测试通过 | 本地测试假阳性 |
| RT-004 | 中 | 远端判题为 Runtime Error 时 `lc submit` 返回退出码 0 | Shell/CI 把失败提交误判为成功 |
| RT-005 | 低 | `--help`/`--version` 输出管道提前关闭时返回 1 | `pipefail`、分页和截取输出产生假失败 |
| RT-006 | 低 | 极大合法 `show --skip` 被归因为接口结构变化 | 分页边界错误提示误导排查 |

补充说明：

- RT-001 的 `OSError` 转换和 traceback 泄露已修复；剩余部分应与 SR-004 一起通过同目录随机临时文件、原子替换和失败时保留原文件处理。
- RT-003 需要先明确执行契约。若 CLI 主动调用 `run_cases()`，必须避免与模板中的 `if __name__ == "__main__": run_cases()` 重复执行。
- RT-004 目前只有一次真实 Runtime Error 提交证据。因该远程提交由测试方法错误触发，报告发现后已停止后续真实提交；修复后仍需在明确授权的测试条件下覆盖 Accepted 和各类非 Accepted 状态。
- Windows 报告记录的 `9d2836fb8f3175e3aa9ce34537b253c701a774b9` 是 `v0.7.2` 的 annotated tag 对象，Linux 报告记录的 `17744500f35a54fcc775c9c9797cd2d2f3adf757` 是该标签解引用后的 Commit。两者指向同一发布代码，不能据此判定测试版本不一致。

## 已有安全措施

- LeetCode 客户端基础地址固定为 HTTPS，未发现明显 SSRF 路径。
- 子进程使用参数列表，未使用 `shell=True`。
- GraphQL 使用变量传值，不拼接用户输入。
- 手动 Cookie 输入不回显。
- Doctor 和普通错误输出不包含 Cookie 值。
- `.leetcode_local_cli/` 与旧 `.aether_lc/` 已在当前仓库忽略。
- 当前 Git 历史未发现真实 Session 文件。
- GitHub Actions 的第三方 Action 固定到提交 SHA。
- PyPI 发布使用 OIDC Trusted Publisher，不保存 PyPI Token。

## 自动化检查结果

本次审计执行了以下辅助检查：

- `pip-audit`：当前解析环境未发现已知依赖漏洞。
- Bandit：报告 17 项低危提示，主要涉及子进程、断言和宽泛异常；人工审计发现了上述更高等级的业务逻辑风险。
- Ruff、Pyright 和现有 pytest 通过；当前结果为 144 passed、10 skipped，其中 Windows junction 实际测试通过，3 项符号链接测试因当前主机缺少创建权限而跳过。
- 本地 wheel 经隔离 `uv tool install` 后，安装版版本入口和工作区目标校验通过。

自动化扫描结果只代表其规则和漏洞数据库覆盖范围，不能替代业务逻辑审查。

## 修复优先级

### P1：下一版本阻断项

1. 将工作区写入改为安全的临时文件加原子替换，并收敛权限、占用和编码异常。
2. 修复 `lc test` 缺少 `run_cases()` 的假阳性。
3. 为 Accepted、非 Accepted、轮询超时和请求失败定义稳定退出码。
4. 在 v0.8 的用户配置与秘密存储设计中迁移工作区明文 Cookie，并同步加固 Session 写入。

### P2：持续加固

1. 增加明确的编辑器设置；配置前继续保留系统默认关联行为，并明确其兼容性风险。
2. 修复 Broken Pipe 和极端分页边界的错误归因。
3. 在 CI 加入 `pip-audit`、Bandit 和秘密扫描。

## 与长期设计的关系

`PROJECT_DESIGN.md` 中的 v0.8 已计划引入显式运行上下文、用户配置目录和系统秘密存储，能够覆盖 SR-002 以及 SR-004 的 Session 写入路径。SR-004 的 `solution.py` 静态目标保护已经在不改变普通文件覆盖行为的前提下完成；事务级保护仍等待 `PB-005`。SR-003 已由项目接受为当前默认关联打开方式的兼容性风险，后续编辑器配置应提供明确命令模式。
