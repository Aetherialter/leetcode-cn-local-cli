# 安全与可靠性边界

## 当前风险

| 等级 | 风险 | 当前控制 | 后续方向 |
| --- | --- | --- | --- |
| 高 | Session Cookie 仍以明文文件保存 | 移出工作区并保存到用户本地状态目录；原子写入、禁止输出和提交 | 评估系统秘密存储 |
| 中 | DevTools 授权端点可控制日常浏览器 | 用户授权、仅回环、身份/端口/站点校验 | 缩短权限窗口 |
| 中 | `test`/`doctor --run-solution` 执行用户代码 | 显式触发、独立进程、每组超时、无 Shell | 只在可信工作区运行，不宣称沙箱 |
| 低 | 系统关联可能不是代码编辑器 | 保存与打开解耦，支持 `--no-open`，不使用 Shell | 增加编辑器配置 |
| 低 | 本机工作区 marker 可能使 Git 状态变脏 | 使用 `.leetcode_local_cli/workspace.toml` 并建议忽略；不自动修改用户 `.gitignore` | 接受当前权衡 |

## 不可违反的规则

- 配置、工作区 marker、`solution.py` 和 Session 只写入不存在或普通目标；其父目录拒绝链接、断链、文件、junction 和 reparse point。
- 覆盖使用同目录随机临时文件和原子替换；失败必须保留旧文件。
- 权限设置在替换前完成，避免“替换已生效却报告权限失败”。配置修复先以独占创建方式保存原始字节备份；备份失败不得覆盖原件，回滚失败必须明确报告。备份不包含 Session，仍可能含本机路径，禁止提交。
- Cookie 不进入终端、异常、fixture、报告、Issue、Git 或构建产物。AI/脚本只有在维护者明确授权的具体测试中才能使用真实账号。
- DevTools 必须是身份匹配的本机回环端点，只请求 `https://leetcode.cn/`，只保留 `LEETCODE_SESSION` 和 `csrftoken`。
- 子进程使用参数数组，不使用 `shell=True`；测试参数使用受限 AST 和 `ast.literal_eval`，不执行输入表达式。
- 外部网络和本地文本按不可信纯文本处理；HTTP 使用 HTTPS、明确超时、响应结构检查和 GraphQL 变量。
- HTTP 发送前检查最终 URL 的 scheme、精确 host、端口及用户信息。Cookie 仅保留必需字段、限定站点并标记 Secure，关闭重定向且将 3xx 分类为失败；不得把登录 Cookie 或提交正文发往跳转目标。
- Session 的读取、UTF-8 解码、JSON/结构及 Cookie 值校验集中在一个存储入口。只检查本地格式不代表远端登录有效；凭据模型的默认 repr 不含 Cookie 值，失败信息不包含文件原文。
- 初始提交 POST 不自动重试；判题 GET 只在单调时钟总预算内有限重试，并遵守合法的 `Retry-After`。
- 安装器缺少 uv 时只提供官方安装说明，不下载或执行远端安装脚本。
- CI 不保存真实 Cookie，不执行真实登录或远程提交。发布使用固定 SHA 的 Actions 与 PyPI Trusted Publisher。

## 验证边界

自动化覆盖用户状态路径、工作区 marker、文件目标、终端文本、授权端点、启动竞态、非法编码、worker 超时、提交总预算、安全重试和退出码。真实浏览器、Cookie 和提交只能进行维护者明确授权且脱敏的手动验收；`v0.9.0` 已在 Windows 对 Chrome 与 Edge 各完成一次真实授权登录，2026-08-09 又在明确授权下完成 10 次真实提交和对应的 `lc check` 重查。验收没有输出 Cookie，但不消除明文 Session 和用户代码执行风险。
