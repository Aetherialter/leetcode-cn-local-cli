# 产品边界

以下行为不得由某次实现偶然改变；未确认的语义必须先由维护者决定。

## 已确认

- 当前采用单默认工作区、单个 `solution.py`、在线优先和 Python3 工作流，不保存完整题库或每题目录。
- `lc solve` 表示切题，可以覆盖普通 `solution.py`；链接、目录、junction 和 reparse point 必须拒绝。
- `solve --no-open` 只保存文件；保存成功但编辑器打开失败只警告且返回 0，写入失败返回 1 且不打开文件。
- `lc config editor` 管理用户级程序和参数数组，可在初始化前配置；`init` 保留有效编辑器设置。`solve` 的优先级是 `--no-open` > `--editor` > 用户配置；临时编辑器不继承旧参数，不增加环境变量或工作区覆盖。未配置只保存并提示，启动失败不回退到系统文件关联，不自动安装编辑器。
- `lc init` 无路径时接收父目录并追加 `leetcode-local-cli`；显式路径是完整工作区；重复初始化保留已有普通解法。
- 普通 `init` 不覆盖损坏配置。`init <完整路径> --repair` 可备份修复损坏的用户配置及目标 marker，备份保留原始字节；不支持的版本、站点、语言以及不安全目标一律拒绝。失败尝试回滚本次文件变化，保留已创建的备份；不是跨文件崩溃恢复事务。
- 普通命令只使用配置中的默认工作区，当前没有全局 `--workspace`。
- 用户配置写入版本独立为 v2，工作区 marker 保持 v1，Session 不变。支持只读现有 v1 用户配置（含内测编辑器设置）；显式设置/清除编辑器或初始化时保留适用字段并写入 v2，不进行读取时迁移。不支持的未来版本仍先拒绝，`--repair` 不降级配置。
- `solution.py` 只接受 UTF-8 或 UTF-8 BOM；其他编码不猜测、不改写、不执行也不提交。
- `lc test` 自动调用 `Solution` 首个公开方法，只接收安全字面量参数并显示实际结果；每组默认 1 秒，无输入或任一错误返回 1，`--stdin` 使用 JSON Lines。成功只代表调用完成，不代表算法正确。
- 节点输入按 `ListNode` / `TreeNode` 及可空、字符串类型注解转换，不按参数名猜类型。链表为整数数组，树为力扣式层序数组，`null` 与 `None` 兼容；节点返回值和原地修改参数转回数组，空节点返回注解对应 `[]`。模板辅助定义不进入提交区域。
- 普通与延迟注解遵循相同节点规则，包含引号的嵌套节点类型仍拒绝；`Literal` 取值和 `Annotated` 元数据不作为类型引用，`Annotated` 包装节点本身暂不支持。
- 第一版节点范围为整数值、无环单链表及普通二叉树；不支持环、共享节点身份、随机指针、N 叉树、嵌套节点集合或设计题多方法调用。每个输入数组最多 100,000 项、每次单个节点输出最多 100,000 个节点，超限报错而非截断。
- 本地异常默认显示类型、原因、可定位的用户源码行号和 stdout/stderr；`test --verbose` 增加完整调用栈，不采集局部变量。JSON 模式用 `error_line` 和可选 `traceback` 字段，仍保持 JSON Lines。
- worker 超时后的重启加载错误属于对应输入组的失败结果，保留行号与可选调用栈；不终止后续输入处理，不改为初次启动的 `startup_error` 事件。
- `test --stdin` 的运行时启动错误统一为 `startup_error` 事件，带稳定 `code`，退出 1；非法 CLI 参数使用标准用法错误，退出 2。
- `lc doctor` 默认不执行用户代码，`lc submit` 也不执行本地代码；只有明确 `--run-solution` 才授权 Doctor 执行。
- `lc submit` 取得 submission ID 后默认等待 30 秒，可用 `--wait-timeout` 调整。只有明确 `Accepted` 返回 0；其他判题、等待超时和轮询失败返回 1，用法错误返回 2。超时不代表代码未提交，必须保留 submission ID。
- `lc check <Submission ID>` 只查询一次已有提交，不发送代码、不持续轮询；仍在判题、非 Accepted 或查询失败返回 1，Accepted 返回 0，用法错误返回 2。
- `lc login` 默认 Chrome → Edge → 手动 Cookie；显式浏览器不跨浏览器回退。CLI 不读取 Cookie 数据库、不创建专用 profile、不关闭日常浏览器。
- `config editor`、`login`、`status`、`profile`、`show`、`get`、`check` 和默认 `doctor` 不要求工作区；`solve`、`test`、`submit` 和 `doctor --run-solution` 必须使用已配置工作区。
- Session 属于当前系统用户，保存在平台本地状态目录的 `leetcode-local-cli/session.json`；切换或删除工作区不得改变登录态。Session 不得输出、提交、同步或上传。
- 凭据 HTTP 请求只允许 HTTPS、精确 `leetcode.cn`、443/默认端口和无 URL 用户信息；拒绝全部重定向，包括同站跳转。接口迁移需显式更新适配代码。
- 工作区 marker 是本机元数据，固定为 `.leetcode_local_cli/workspace.toml`，建议忽略且不提交；CLI 不自动修改用户仓库的 `.gitignore`。
- 内测阶段不兼容、不读取也不迁移旧工作区 Session 和根目录 `.leetcode-local-cli.toml`。
- 工具源码仓库不跟踪根目录 `solution.py`，本地文件保留供开发者使用；普通用户工作区仍可自定义，不强制与源码合并。

## 待定

- `doctor --run-solution` 应展示多少 traceback/stdout。
- 提交前校验整个文件、只校验 marker，还是完全交给远端。
- 合法空分页与 Broken Pipe 的退出语义。
- 实际支持并由 CI 覆盖的 Python 小版本范围。

确认边界变化时更新本文件、README 和对应测试；只有同时改变架构、风险或重大技术选择时，才更新相应专题文档。
