# 安全与可靠性边界

最近更新：2026-08-01

范围：凭据、工作区写入、用户代码、浏览器连接、网络和发布。

## 当前风险

| 等级 | 风险 | 当前控制 | 后续方向 |
| --- | --- | --- | --- |
| 高 | Session Cookie 明文保存在工作区 | 目录被 `.gitignore` 排除；原子写入；禁止输出、提交和 CI 使用真实值 | 重新设计系统秘密存储和迁移 |
| 中 | DevTools 授权期间端点可控制日常浏览器 | 用户两步授权；仅回环；浏览器身份、端口和站点范围校验；不关闭用户实例 | 继续缩短权限窗口并完善手动验收 |
| 中 | `lc test`/`doctor --run-solution` 执行用户代码 | 必须显式触发；独立进程、每组超时、无 Shell | 不能宣称沙箱；只在可信工作区运行 |
| 中 | 提交固定轮询次数 | 单次网络请求有超时；未知结果返回非零 | 改为稳定总超时和有限安全重试 |
| 低 | 系统默认程序打开 `.py` | 使用参数化系统调用，不使用 Shell | 引入明确编辑器配置 |
| 低 | 工作区标记使 Git 工作树变脏 | 不静默改 `.gitignore` | 先确认产品语义 |

## 已实施控制

### 文件与路径

- 所有业务路径来自显式 `AppPaths`，不在导入时依赖当前目录。
- 配置、`solution.py` 和 Session 只接受不存在或普通目标；拒绝链接、断链、目录、junction 和 reparse point。
- 覆盖使用同目录随机排他临时文件、完整写入、`fsync` 和 `os.replace`；失败保留旧文件。
- 初始化只回滚本次创建内容，不删除已有用户文件。
- `solution.py` 只按 UTF-8/UTF-8 BOM 读取；非法编码在执行和网络请求前受控失败。

### 凭据与浏览器

- 普通登录优先使用用户明确授权的日常 Chrome/Edge，失败后才隐藏输入手动 Cookie。
- 不读取或解密浏览器 Cookie 数据库；不扫描端口；不创建或关闭浏览器配置。
- DevTools 必须是身份匹配的本机回环端点；只请求 `https://leetcode.cn/`，只保留 `LEETCODE_SESSION` 和 `csrftoken`。
- 获取 Cookie 后仍需在线验证，成功才写入 Session。
- Cookie 值不得进入终端、异常、测试 fixture、报告、Issue、Git 或构建产物。

### 执行、网络与终端

- 子进程使用参数数组，不使用 `shell=True`。
- `lc test` 的参数只用受限 AST 和 `ast.literal_eval` 解析；用户输入不会作为表达式执行。
- `lc doctor` 默认只做静态检查；`lc submit` 不执行本地代码。
- HTTP 使用 HTTPS 和明确超时；GraphQL 使用变量；外部文本去除控制字符并作为纯文本渲染。
- 提交只有明确 `Accepted` 返回 0，避免红色失败信息同时向自动化报告成功。

### 仓库与发布

- `.leetcode_local_cli/`、旧 Session 目录、常见密钥 JSON、环境文件和个人编辑器目录被忽略。
- 测试扫描已跟踪 JSON 的高风险秘密字段；CI 只使用假 Cookie 和 MockTransport。
- GitHub Actions 第三方 Action 固定 SHA；PyPI 使用 OIDC Trusted Publisher，不保存上传 Token。

## 明文 Session 规则

当前文件为 `<workspace>/.leetcode_local_cli/session.json`。这是为维护者授权的真实账号验收保留的阶段性能力，不是安全秘密存储。

- 不放入同步盘或共享工作区，不提交、不粘贴、不记录。
- AI 或脚本只有在维护者明确授权的具体测试中才能使用。
- CI 不执行真实登录或提交；建议真实验收使用专门账号。
- 初始化、升级和卸载不主动删除 Session；用户负责其生命周期。

## 验证边界

发布前运行 Ruff、Pyright、完整 pytest、wheel/sdist 构建和入口 smoke test。三平台安装与包行为由发布工作流验证；真实浏览器、Cookie 和提交只能做明确授权且脱敏的手动验收。

`v0.9.0` 已在 Windows 对 Chrome 与 Edge 各完成一次真实授权登录；自动化覆盖授权文件、回环/身份校验、启动竞态、错误回退、非法编码、worker 超时和提交退出码。它不证明用户代码已被安全沙箱化，也不消除明文 Session 风险。
