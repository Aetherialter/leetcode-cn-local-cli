# 安全与可靠性边界

## 当前风险

| 等级 | 风险 | 当前控制 | 后续方向 |
| --- | --- | --- | --- |
| 高 | Session Cookie 明文保存在工作区 | 忽略 Session 目录、原子写入、禁止输出和提交 | 设计系统秘密存储与迁移 |
| 中 | DevTools 授权端点可控制日常浏览器 | 用户授权、仅回环、身份/端口/站点校验 | 缩短权限窗口 |
| 中 | `test`/`doctor --run-solution` 执行用户代码 | 显式触发、独立进程、每组超时、无 Shell | 只在可信工作区运行，不宣称沙箱 |
| 中 | 提交固定轮询次数 | 单次请求超时、未知结果返回非零 | 改为稳定总超时 |
| 低 | 系统关联可能不是代码编辑器 | 参数化系统调用，不使用 Shell | 增加编辑器配置 |
| 低 | 工作区 marker 使 Git 状态变脏 | 不自动修改用户 `.gitignore` | 确认产品语义 |

## 不可违反的规则

- 配置、`solution.py` 和 Session 只写入不存在或普通目标；拒绝链接、断链、目录、junction 和 reparse point。
- 覆盖使用同目录随机临时文件和原子替换；失败必须保留旧文件。
- Cookie 不进入终端、异常、fixture、报告、Issue、Git 或构建产物。AI/脚本只有在维护者明确授权的具体测试中才能使用真实账号。
- DevTools 必须是身份匹配的本机回环端点，只请求 `https://leetcode.cn/`，只保留 `LEETCODE_SESSION` 和 `csrftoken`。
- 子进程使用参数数组，不使用 `shell=True`；测试参数使用受限 AST 和 `ast.literal_eval`，不执行输入表达式。
- 外部网络和本地文本按不可信纯文本处理；HTTP 使用 HTTPS、明确超时、响应结构检查和 GraphQL 变量。
- 安装器缺少 uv 时只提供官方安装说明，不下载或执行远端安装脚本。
- CI 不保存真实 Cookie，不执行真实登录或远程提交。发布使用固定 SHA 的 Actions 与 PyPI Trusted Publisher。

## 验证边界

自动化覆盖文件目标、终端文本、授权端点、启动竞态、非法编码、worker 超时和提交退出码。真实浏览器、Cookie 和提交只能进行维护者明确授权且脱敏的手动验收；`v0.9.0` 已在 Windows 对 Chrome 与 Edge 各完成一次真实授权登录，但这不消除明文 Session 和用户代码执行风险。
