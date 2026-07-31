# 发布流程

项目使用 GitHub Actions、PyPI Trusted Publisher 和版本化 Release Notes 发布。仓库和 GitHub Secrets 不保存 PyPI Token。

## 一次性配置

1. GitHub 创建 `pypi` environment；建议配置 required reviewer。
2. PyPI 创建 Trusted Publisher：
   - project：`leetcode-local-cli`
   - owner：`Aetherialter`
   - repository：`leetcode-local-cli`
   - workflow：`release.yml`
   - environment：`pypi`

## 发布准备

1. 更新 `pyproject.toml` 与 `uv.lock`，确保版本一致。
2. 新建 `docs/release-notes/vX.Y.Z.md`：第一行是 Release 标题，空一行后是正文。
3. 运行本地门禁：

```shell
uv run ruff format --check src tests scripts
uv run ruff check src tests scripts pyproject.toml
uv run pyright src tests scripts
uv run pytest
uv build --no-sources
```

4. 分别从 wheel 和 sdist 运行隔离 smoke test：

```shell
export LEETCODE_LOCAL_CLI_EXPECTED_VERSION="$(uv version --short)"
uv run --isolated --no-project --with dist/*.whl scripts/smoke_test.py
uv run --isolated --no-project --with dist/*.tar.gz scripts/smoke_test.py
```

PowerShell 使用 `$env:LEETCODE_LOCAL_CLI_EXPECTED_VERSION = (uv version --short)` 设置变量。

## 触发与门禁

创建并推送与项目版本完全一致的 `vX.Y.Z` 标签。标签工作流依次：

1. 在 Linux、macOS、Windows 运行格式、Lint、Pyright、测试和构建。
2. 在三平台隔离 uv 工具目录验证安装器。
3. 从 wheel 和 sdist 验证 `lc --version`、`lc --help`。
4. 使用 OIDC 发布 PyPI。
5. 使用同版本 Release Notes 创建或更新 GitHub Release。

任何阶段失败都阻止后续发布。PyPI 同一版本不可覆盖；禁止移动已发布标签或用同一版本重建不同产物。真实 Cookie 和远程提交不进入发布工作流。
