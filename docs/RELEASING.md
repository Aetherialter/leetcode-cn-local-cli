# 发布流程

项目通过 GitHub Actions、PyPI Trusted Publisher 和版本化 Release Notes 发布，不保存 PyPI Token。

普通分支 push 和 PR 由 `ci.yml` 在 Linux、macOS、Windows 的 Python 3.12 上运行 Ruff、Pyright 和 pytest，只授予仓库读取权限，不发布。`release.yml` 继续单独处理版本标签；新增 CI 配置不等于三平台运行已通过。

## 一次性配置

- GitHub `pypi` environment 建议设置 required reviewer。
- PyPI Trusted Publisher 使用项目 `leetcode-local-cli`、仓库 `Aetherialter/leetcode-local-cli`、工作流 `release.yml` 和环境 `pypi`。

## 发布准备

1. 同步 `pyproject.toml` 与 `uv.lock` 版本。
2. 新建 `docs/release-notes/vX.Y.Z.md`；第一行是标题，空一行后是正文。
3. 运行完整门禁：

```shell
uv run ruff format --check src tests scripts
uv run ruff check src tests scripts pyproject.toml
uv run pyright src tests scripts
uv run pytest
uv build --no-sources
```

4. 分别从 wheel 和 sdist 执行隔离 smoke test：

```shell
export LEETCODE_LOCAL_CLI_EXPECTED_VERSION="$(uv version --short)"
uv run --isolated --no-project --with dist/*.whl scripts/smoke_test.py
uv run --isolated --no-project --with dist/*.tar.gz scripts/smoke_test.py
```

PowerShell 使用 `$env:LEETCODE_LOCAL_CLI_EXPECTED_VERSION = (uv version --short)` 设置变量。

若本机 uv 版本超出 `build-system.requires` 中 `uv_build` 的范围，可用 `uv build --no-sources --force-pep517` 复验。该模式禁用 uv 内置构建快路径，通过隔离的 PEP 517 环境使用项目声明范围内的后端，不需要修改全局 uv 或放宽依赖范围。

两种产物的 smoke test 都会验证版本/帮助入口、初始化前配置编辑器及初始化后设置保留，在临时用户目录中启动本地 worker，检查普通参数和节点数组的 JSON 输入输出，以及生成模板所需的包资源。不读取真实 Session，不启动编辑器，不联网登录或提交。

## 发布

创建并推送与项目版本完全一致的 `vX.Y.Z` 标签。标签工作流会：

1. 在 Linux、macOS 和 Windows 运行质量门禁与构建。
2. 在三平台隔离 uv 工具目录验证安装器。
3. 在三平台分别从 wheel/sdist 隔离安装，验证入口、用户配置、初始化和节点本地调用；全部通过后，发布任务对自己构建的产物再执行同一验收。
4. 使用 OIDC 发布 PyPI，并以同版本 Release Notes 创建 GitHub Release。

任何阶段失败都阻止发布。PyPI 同一版本不可覆盖；不得移动已发布标签或用同一版本重建不同产物。真实 Cookie 和远程提交不进入发布工作流。
