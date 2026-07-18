# 发布流程

`leetcode-local-cli` 使用 GitHub Actions 和 PyPI Trusted Publisher 发布，不在仓库或 GitHub Secrets 中保存 PyPI Token。

## 首次发布配置

在创建首个发布标签前完成以下一次性配置：

1. 在 GitHub 仓库的 `Settings > Environments` 中创建名为 `pypi` 的 environment；建议把维护者本人设置为 required reviewer，避免标签误推后直接发布。
2. 在 PyPI 的 `Publishing` 页面添加 pending publisher：
   - PyPI project name：`leetcode-local-cli`
   - Owner：`Aetherialter`
   - Repository name：`leetcode-local-cli`
   - Workflow name：`release.yml`
   - Environment name：`pypi`

项目首次由该工作流成功发布后，pending publisher 会自动转换为项目的 Trusted Publisher。

## 本地发布门禁

版本号只在正式发布准备阶段修改。`pyproject.toml`、`uv.lock`、发布标签和构建产物中的版本必须一致。

```shell
uv run ruff format --check src tests scripts
uv run ruff check src tests scripts pyproject.toml
uv run pyright src tests scripts
uv run pytest
uv build --no-sources
```

随后分别对 wheel 和源码包执行隔离 smoke test：

```shell
export LEETCODE_LOCAL_CLI_EXPECTED_VERSION="$(uv version --short)"
uv run --isolated --no-project --with dist/*.whl scripts/smoke_test.py
uv run --isolated --no-project --with dist/*.tar.gz scripts/smoke_test.py
```

## 触发发布

发布工作流只接受以 `v` 开头、并与项目版本完全一致的标签。例如项目版本为 `0.7.0` 时：

```shell
git tag -a v0.7.0 -m "v0.7.0"
git push origin main
git push origin v0.7.0
```

标签推送后，`.github/workflows/release.yml` 会依次：

1. 在 Linux、macOS 和 Windows 上运行格式、Lint、Pyright、测试和构建。
2. 在三个平台的隔离 uv 工具目录中运行对应安装器。
3. 分别从 wheel 和源码包启动 `lc --version`、`lc --help`。
4. 使用 OIDC Trusted Publisher 发布到 PyPI。
5. PyPI 发布成功后创建 GitHub Release。

任何阶段失败都会阻止后续发布。PyPI 的同一版本不可覆盖，因此禁止移动已发布标签或重新构建同版本的不同产物。
