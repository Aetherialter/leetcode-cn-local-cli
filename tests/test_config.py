from pathlib import Path

import pytest

from leetcode_local_cli import config
from leetcode_local_cli.config import (
    CONFIG_VERSION,
    ConfigError,
    UserConfig,
    WorkspaceConfig,
    load_user_config,
    load_workspace_config,
    initialize_workspace,
    resolve_app_paths,
)
from leetcode_local_cli.safe_files import SafeFileError


def _write_user_config(path: Path, workspace_root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            (
                f"version = {CONFIG_VERSION}",
                f'default_workspace = "{workspace_root.as_posix()}"',
                'default_site = "cn"',
                "",
            )
        ),
        encoding="utf-8",
    )


def _write_workspace_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            (
                f"version = {CONFIG_VERSION}",
                'site = "cn"',
                'language = "python3"',
                "",
            )
        ),
        encoding="utf-8",
    )


def test_load_user_config_returns_none_when_file_is_missing(tmp_path: Path) -> None:
    assert load_user_config(tmp_path / "missing.toml") is None


def test_load_user_config_returns_typed_model(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    config_file = tmp_path / "config.toml"
    _write_user_config(config_file, workspace_root)

    result = load_user_config(config_file)

    assert result == UserConfig(
        version=CONFIG_VERSION,
        default_workspace=workspace_root,
        default_site="cn",
    )


@pytest.mark.parametrize(
    "content",
    (
        "not valid toml = [",
        'version = true\ndefault_workspace = "C:/workspace"\ndefault_site = "cn"\n',
        'version = 999\ndefault_workspace = "C:/workspace"\ndefault_site = "cn"\n',
        'version = 1\ndefault_workspace = "relative/path"\ndefault_site = "cn"\n',
        'version = 1\ndefault_workspace = "C:/workspace"\ndefault_site = "com"\n',
    ),
)
def test_load_user_config_rejects_invalid_content(
    tmp_path: Path,
    content: str,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(content, encoding="utf-8")

    with pytest.raises(ConfigError):
        load_user_config(config_file)


def test_load_workspace_config_returns_none_when_file_is_missing(
    tmp_path: Path,
) -> None:
    assert load_workspace_config(tmp_path / "missing.toml") is None


def test_load_workspace_config_returns_typed_model(tmp_path: Path) -> None:
    config_file = tmp_path / ".leetcode_local_cli" / "workspace.toml"
    _write_workspace_config(config_file)

    result = load_workspace_config(config_file)

    assert result == WorkspaceConfig(
        version=CONFIG_VERSION,
        site="cn",
        language="python3",
    )


@pytest.mark.parametrize(
    "content",
    (
        "not valid toml = [",
        'version = true\nsite = "cn"\nlanguage = "python3"\n',
        'version = 999\nsite = "cn"\nlanguage = "python3"\n',
        'version = 1\nsite = "com"\nlanguage = "python3"\n',
        'version = 1\nsite = "cn"\nlanguage = "java"\n',
    ),
)
def test_load_workspace_config_rejects_invalid_content(
    tmp_path: Path,
    content: str,
) -> None:
    config_file = tmp_path / ".leetcode_local_cli" / "workspace.toml"
    config_file.parent.mkdir()
    config_file.write_text(content, encoding="utf-8")

    with pytest.raises(ConfigError):
        load_workspace_config(config_file)


def test_resolve_app_paths_uses_configured_workspace(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    user_config_file = tmp_path / "config" / "config.toml"
    user_state_directory = tmp_path / "state"
    _write_user_config(user_config_file, workspace_root)
    _write_workspace_config(workspace_root / ".leetcode_local_cli" / "workspace.toml")

    paths = resolve_app_paths(
        user_config_file,
        user_state_directory=user_state_directory,
    )

    assert paths.user.user_config_file == user_config_file
    assert paths.user.session_file == user_state_directory / "session.json"
    assert paths.workspace.workspace_root == workspace_root
    assert paths.workspace.solution_file == workspace_root / "solution.py"


def test_resolve_app_paths_rejects_missing_user_config(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="尚未配置工作区"):
        resolve_app_paths(tmp_path / "missing.toml")


def test_resolve_app_paths_rejects_missing_workspace_config(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    user_config_file = tmp_path / "config.toml"
    _write_user_config(user_config_file, workspace_root)

    with pytest.raises(ConfigError, match="工作区标记"):
        resolve_app_paths(user_config_file)


def test_resolve_app_paths_does_not_accept_legacy_root_marker(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    user_config_file = tmp_path / "config.toml"
    _write_user_config(user_config_file, workspace_root)
    _write_workspace_config(workspace_root / ".leetcode-local-cli.toml")

    with pytest.raises(ConfigError, match="工作区标记"):
        resolve_app_paths(user_config_file)


def test_resolve_app_paths_rejects_workspace_symlink(tmp_path: Path) -> None:
    actual_workspace = tmp_path / "actual-workspace"
    _write_workspace_config(actual_workspace / ".leetcode_local_cli" / "workspace.toml")
    linked_workspace = tmp_path / "linked-workspace"
    try:
        linked_workspace.symlink_to(actual_workspace, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symbolic links are unavailable: {exc}")
    user_config_file = tmp_path / "config.toml"
    _write_user_config(user_config_file, linked_workspace)

    with pytest.raises(ConfigError, match="符号链接"):
        resolve_app_paths(user_config_file)


def test_initialize_workspace_creates_versioned_files_and_user_config(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    user_config_file = tmp_path / "config" / "config.toml"

    result = initialize_workspace(
        workspace_root,
        user_config_file=user_config_file,
    )

    assert result.workspace_created
    assert result.metadata_directory_created
    assert result.workspace_config_created
    assert result.solution_created
    assert not (result.paths.metadata_directory / "session.json").exists()
    assert load_workspace_config(result.paths.workspace_config_file) == WorkspaceConfig(
        version=CONFIG_VERSION,
        site="cn",
        language="python3",
    )
    assert load_user_config(user_config_file) == UserConfig(
        version=CONFIG_VERSION,
        default_workspace=workspace_root,
        default_site="cn",
    )
    assert result.paths.solution_file.read_text(encoding="utf-8") == ""


def test_initialize_workspace_is_idempotent_and_preserves_existing_files(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    user_config_file = tmp_path / "config.toml"
    first_result = initialize_workspace(
        workspace_root,
        user_config_file=user_config_file,
    )
    first_result.paths.solution_file.write_text("user code", encoding="utf-8")
    workspace_config_bytes = first_result.paths.workspace_config_file.read_bytes()

    second_result = initialize_workspace(
        workspace_root,
        user_config_file=user_config_file,
    )

    assert second_result.reused
    assert second_result.paths.solution_file.read_text(encoding="utf-8") == "user code"
    assert (
        second_result.paths.workspace_config_file.read_bytes() == workspace_config_bytes
    )


def test_initialize_workspace_rejects_corrupt_marker_without_modifying_files(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    marker = workspace_root / ".leetcode_local_cli" / "workspace.toml"
    marker.parent.mkdir()
    marker.write_text("invalid = [", encoding="utf-8")
    solution_file = workspace_root / "solution.py"
    solution_file.write_text("user code", encoding="utf-8")
    user_config_file = tmp_path / "config.toml"

    with pytest.raises(ConfigError, match="不是有效的 TOML"):
        initialize_workspace(
            workspace_root,
            user_config_file=user_config_file,
        )

    assert marker.read_text(encoding="utf-8") == "invalid = ["
    assert solution_file.read_text(encoding="utf-8") == "user code"
    assert not user_config_file.exists()


def test_initialize_workspace_rejects_solution_symlink_without_touching_target(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    external_file = tmp_path / "external.py"
    external_file.write_text("external content", encoding="utf-8")
    solution_file = workspace_root / "solution.py"
    try:
        solution_file.symlink_to(external_file)
    except OSError as exc:
        pytest.skip(f"symbolic links are unavailable: {exc}")

    with pytest.raises(ConfigError, match="符号链接"):
        initialize_workspace(
            workspace_root,
            user_config_file=tmp_path / "config.toml",
        )

    assert solution_file.is_symlink()
    assert external_file.read_text(encoding="utf-8") == "external content"
    assert not (workspace_root / ".leetcode_local_cli").exists()


def test_initialize_workspace_rejects_metadata_directory_symlink(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    external_directory = tmp_path / "external"
    external_directory.mkdir()
    metadata_directory = workspace_root / ".leetcode_local_cli"
    try:
        metadata_directory.symlink_to(external_directory, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symbolic links are unavailable: {exc}")

    with pytest.raises(ConfigError, match="符号链接"):
        initialize_workspace(
            workspace_root,
            user_config_file=tmp_path / "config.toml",
        )

    assert metadata_directory.is_symlink()
    assert not (external_directory / "workspace.toml").exists()
    assert not (workspace_root / "solution.py").exists()


def test_initialize_workspace_rolls_back_created_workspace_files_on_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace_root = tmp_path / "workspace"
    user_config_file = tmp_path / "config" / "config.toml"

    def fail_atomic_write(*args, **kwargs) -> None:
        raise SafeFileError("simulated config failure")

    monkeypatch.setattr(config, "atomic_write_text", fail_atomic_write)

    with pytest.raises(ConfigError, match="simulated config failure"):
        initialize_workspace(
            workspace_root,
            user_config_file=user_config_file,
        )

    assert not workspace_root.exists()
    assert not user_config_file.exists()
