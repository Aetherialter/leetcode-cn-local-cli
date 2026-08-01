# 项目状态

最近更新：2026-08-02

当前已发布版本：`v0.9.0`，已发布到 PyPI 和 GitHub Releases。当前工作树包含尚未发布的 CLI 分层重构。

这是维护者的第一事实入口。用户行为以 [README](../README.md) 和 [PRODUCT_BOUNDARIES](PRODUCT_BOUNDARIES.md) 为准；实现结构以 [ARCHITECTURE](ARCHITECTURE.md) 为准。

## 当前目标

`leetcode-local-cli` 是面向 LeetCode 中文站的轻量、本地刷题 CLI。当前目标是可靠完成：配置工作区、登录、查询题目、生成单文件解法、本地调用、诊断和远程提交。

当前明确不做数据库、完整本地题库、每题目录、Web/桌面 UI、AI 功能和 Python3 以外的提交语言。

## 已实现

- 安装与工作区：uv 安装；跨平台用户配置；`lc init [path]`；单个默认工作区和 `solution.py`。
- 安全写入：普通文件可原子覆盖；符号链接、断链、目录、junction 和 reparse point 被拒绝。
- 登录：日常 Chrome → 日常 Edge → 手动 Cookie；浏览器路径需要用户明确允许 DevTools，只读取 `leetcode.cn` 所需 Cookie 并在线验证。
- 查询与解题：`status`、`profile`、`show`、`get`、`solve` 和 `doctor`。
- 本地调用：`lc test` 自动发现 `Solution` 首个公开方法，支持交互输入和 `--stdin` JSON Lines；每组默认超时 1 秒。
- 编码边界：`solution.py` 只接受 UTF-8/UTF-8 BOM，非法编码受控失败。
- 提交：当前只支持 Python3；只有明确 `Accepted` 返回退出码 0。
- 应用边界：CLI 命令适配器已集中到 `commands/`，可复用流程已迁移到不依赖 Typer/Rich 的 `use_cases/`。
- 发布：标签触发三平台检查、PyPI Trusted Publisher 和 GitHub Release。

## 当前架构阶段

项目是同步 Python CLI。`cli.py` 只创建应用并注册命令；`commands/` 负责参数、交互、渲染和退出码；`use_cases/` 负责编排认证、题目、诊断、本地测试和提交流程，且不依赖 Typer、Rich 或 `ui.py`。路径、配置、安全文件操作、浏览器发现、本地 worker 和 HTTP 客户端继续作为底层能力模块。当前尚未形成稳定 Python API。

## 当前问题

1. **提交总超时**：判题仍固定轮询 10 次，不能给出稳定、可解释的总等待时间。
2. **明文 Session**：Cookie 位于工作区 `.leetcode_local_cli/session.json`，存在误提交、同步或共享风险。
3. **工作区标记**：Git 仓库中的 `.leetcode-local-cli.toml` 是否提交或忽略尚未形成统一语义。
4. **日常 CI**：普通 push/PR 尚无常规工作流，主要门禁仍集中在发布标签。
5. **公开模型**：部分账号与提交结果仍使用裸字典；用例层已建立错误边界，但稳定 Python API 尚未设计。

低优先级问题：系统 `.py` 关联可能不是编辑器；Broken Pipe、极端分页和正式 Python 小版本范围尚未收口。

## 下一步

1. 将提交轮询改为基于单调时钟的总超时，并测试终态、超时和接口异常。
2. 确认工作区标记的 Git 语义；不允许 CLI 未经确认修改用户仓库 `.gitignore`。
3. 为普通 push/PR 增加 Ruff、Pyright 和 pytest。
4. 将剩余裸字典逐步迁移为结构化模型，再以真实消费者需求确定最小 Python API。

更远方向只见 [PROJECT_DESIGN](PROJECT_DESIGN.md)，不视为承诺或排期。

## 最近验证

当前结构重构通过 Ruff format、Ruff lint、Pyright、Windows 完整测试（289 passed、13 skipped）、wheel/sdist 构建、全部子命令帮助检查和隔离 wheel smoke test。未重复执行真实浏览器登录或远程提交；`v0.9.0` 发布前的 Chrome/Edge 真实登录验收仍是最近一次外部集成证据。真实凭据未进入测试、终端报告或仓库。
