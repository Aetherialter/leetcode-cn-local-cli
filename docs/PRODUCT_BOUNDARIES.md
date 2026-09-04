# 产品边界

以下行为不得由某次实现偶然改变；未确认的语义必须先由维护者决定。

## 已确认

- 当前采用单默认工作区、单个 `solution.py`、在线优先和 Python3 工作流，不保存完整题库或每题目录。
- `lc solve` 表示切题，可以覆盖普通 `solution.py`；链接、目录、junction 和 reparse point 必须拒绝。
- `lc init` 无路径时接收父目录并追加 `leetcode-local-cli`；显式路径是完整工作区；重复初始化保留已有普通解法。
- 普通命令只使用配置中的默认工作区，当前没有全局 `--workspace`。
- `solution.py` 只接受 UTF-8 或 UTF-8 BOM；其他编码不猜测、不改写、不执行也不提交。
- `lc test` 自动调用 `Solution` 首个公开方法，只接收安全字面量参数并显示实际结果；每组默认 1 秒，无输入或任一错误返回 1，`--stdin` 使用 JSON Lines。成功只代表调用完成，不代表算法正确。
- `lc doctor` 默认不执行用户代码，`lc submit` 也不执行本地代码；只有明确 `--run-solution` 才授权 Doctor 执行。
- `lc submit` 取得 submission ID 后默认等待 30 秒，可用 `--wait-timeout` 调整。只有明确 `Accepted` 返回 0；其他判题、等待超时和轮询失败返回 1，用法错误返回 2。超时不代表代码未提交，必须保留 submission ID。
- `lc check <Submission ID>` 只查询一次已有提交，不发送代码、不持续轮询；仍在判题、非 Accepted 或查询失败返回 1，Accepted 返回 0，用法错误返回 2。
- `lc login` 默认 Chrome → Edge → 手动 Cookie；显式浏览器不跨浏览器回退。CLI 不读取 Cookie 数据库、不创建专用 profile、不关闭日常浏览器。
- `login`、`status`、`profile`、`show`、`get`、`check` 和默认 `doctor` 不要求工作区；`solve`、`test`、`submit` 和 `doctor --run-solution` 必须使用已配置工作区。
- Session 属于当前系统用户，保存在平台本地状态目录的 `leetcode-local-cli/session.json`；切换或删除工作区不得改变登录态。Session 不得输出、提交、同步或上传。
- 工作区 marker 是本机元数据，固定为 `.leetcode_local_cli/workspace.toml`，建议忽略且不提交；CLI 不自动修改用户仓库的 `.gitignore`。
- 内测阶段不兼容、不读取也不迁移旧工作区 Session 和根目录 `.leetcode-local-cli.toml`。

## 待定

- `test --verbose` 和 `doctor --run-solution` 应展示多少 traceback/stdout。
- 提交前校验整个文件、只校验 marker，还是完全交给远端。
- 编辑器命令、配置层级和优先级。
- 合法空分页与 Broken Pipe 的退出语义。
- 实际支持并由 CI 覆盖的 Python 小版本范围。

确认边界变化时更新本文件、README 和对应测试；只有同时改变架构、风险或重大技术选择时，才更新相应专题文档。
