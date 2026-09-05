import pytest

from leetcode_local_cli.storage.config import (
    ConfigError,
    ConfigErrorKind,
    load_user_config,
    load_workspace_config,
    resolve_workspace_paths,
)
from leetcode_local_cli.storage.safe_files import SafeFileError
from leetcode_local_cli.use_cases import setup


@pytest.mark.parametrize("target", ["user", "marker", "both"])
@pytest.mark.parametrize("content", [b"invalid = [", b"\xff\xfeoriginal bytes"])
def test_repair_preserves_original_bytes_and_solution(
    tmp_path, target, content
) -> None:
    config_file = tmp_path / "config.toml"
    workspace = setup.initialize_workspace(
        tmp_path / "workspace", user_config_file=config_file
    ).paths
    workspace.solution_file.write_bytes(b"user solution")
    targets = {
        "user": [config_file],
        "marker": [workspace.workspace_config_file],
        "both": [config_file, workspace.workspace_config_file],
    }[target]
    for path in targets:
        path.write_bytes(content)
    with pytest.raises(ConfigError):
        setup.initialize_workspace(
            workspace.workspace_root, user_config_file=config_file
        )
    assert not list(tmp_path.rglob("*.bak"))
    result = setup.initialize_workspace(
        workspace.workspace_root, user_config_file=config_file, repair=True
    )
    assert len(result.backups) == len(targets)
    assert [backup.read_bytes() for backup in result.backups] == [content] * len(
        targets
    )
    assert [backup.parent for backup in result.backups] == [
        path.parent for path in targets
    ]
    assert load_user_config(config_file) is not None
    assert load_workspace_config(workspace.workspace_config_file) is not None
    assert workspace.solution_file.read_bytes() == b"user solution"
    repeated = setup.initialize_workspace(
        workspace.workspace_root, user_config_file=config_file, repair=True
    )
    assert repeated.reused and not repeated.backups


@pytest.mark.parametrize("target", ["user", "marker"])
@pytest.mark.parametrize("extra", ["", '\nfuture_field = "preserve"\n'])
@pytest.mark.parametrize(
    "old, new", [("version = 1", "version = 99"), ('"cn"', '"com"')]
)
def test_repair_rejects_unsupported_settings(tmp_path, target, old, new, extra) -> None:
    config_file = tmp_path / "config.toml"
    workspace = setup.initialize_workspace(
        tmp_path / "workspace", user_config_file=config_file
    ).paths
    path = config_file if target == "user" else workspace.workspace_config_file
    path.write_text(
        path.read_text(encoding="utf-8").replace(old, new) + extra, encoding="utf-8"
    )
    original = path.read_bytes()
    with pytest.raises(ConfigError) as caught:
        setup.initialize_workspace(
            workspace.workspace_root, user_config_file=config_file, repair=True
        )
    assert caught.value.kind is ConfigErrorKind.UNSUPPORTED
    assert path.read_bytes() == original
    assert not list(tmp_path.rglob("*.bak"))


def test_backup_failure_does_not_overwrite_originals(tmp_path, monkeypatch) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_bytes(b"\xff")

    def fail_backup(*args, **kwargs):
        raise SafeFileError("backup failure")

    monkeypatch.setattr(setup, "create_bytes_file", fail_backup)
    with pytest.raises(ConfigError, match="backup failure"):
        setup.initialize_workspace(
            tmp_path / "workspace", user_config_file=config_file, repair=True
        )
    assert config_file.read_bytes() == b"\xff"
    assert not (tmp_path / "workspace").exists()


def test_later_failure_restores_repaired_marker_and_retains_backups(
    tmp_path, monkeypatch
) -> None:
    config_file = tmp_path / "config.toml"
    workspace = setup.initialize_workspace(
        tmp_path / "workspace", user_config_file=config_file
    ).paths
    config_file.write_bytes(b"\xff-user")
    workspace.workspace_config_file.write_bytes(b"\xff-marker")
    workspace.solution_file.write_bytes(b"user solution")
    original_write = setup.atomic_write_text

    def fail_user_write(path, *args, **kwargs):
        if path == config_file:
            raise SafeFileError("user write failure")
        original_write(path, *args, **kwargs)

    monkeypatch.setattr(setup, "atomic_write_text", fail_user_write)
    with pytest.raises(ConfigError, match="user write failure"):
        setup.initialize_workspace(
            workspace.workspace_root, user_config_file=config_file, repair=True
        )
    assert config_file.read_bytes() == b"\xff-user"
    assert workspace.workspace_config_file.read_bytes() == b"\xff-marker"
    assert workspace.solution_file.read_bytes() == b"user solution"
    assert sorted(backup.read_bytes() for backup in tmp_path.rglob("*.bak")) == [
        b"\xff-marker",
        b"\xff-user",
    ]


@pytest.mark.parametrize("target_exists", [True, False])
def test_repair_never_follows_config_links(tmp_path, target_exists) -> None:
    target = tmp_path / "outside.toml"
    if target_exists:
        target.write_bytes(b"\xff")
    config_file = tmp_path / "config.toml"
    try:
        config_file.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ConfigError) as caught:
        setup.initialize_workspace(
            tmp_path / "workspace", user_config_file=config_file, repair=True
        )
    assert caught.value.kind is ConfigErrorKind.UNSAFE
    assert not list(tmp_path.rglob("*.bak"))
    if target_exists:
        assert target.read_bytes() == b"\xff"


@pytest.mark.parametrize("target", ["config", "marker", "workspace"])
def test_missing_configuration_is_not_classified_as_corrupt(tmp_path, target) -> None:
    config_file = tmp_path / "config.toml"
    workspace = setup.initialize_workspace(
        tmp_path / "workspace", user_config_file=config_file
    ).paths
    if target == "config":
        config_file.unlink()
    elif target == "marker":
        workspace.workspace_config_file.unlink()
    else:
        workspace.workspace_root.rename(tmp_path / "moved-workspace")
    with pytest.raises(ConfigError) as caught:
        resolve_workspace_paths(config_file)
    assert caught.value.kind is ConfigErrorKind.MISSING


def test_repair_rejects_reparse_metadata_directory(tmp_path, monkeypatch) -> None:
    from leetcode_local_cli.storage import safe_files

    config_file = tmp_path / "config.toml"
    workspace = setup.initialize_workspace(
        tmp_path / "workspace", user_config_file=config_file
    ).paths
    marker_before = workspace.workspace_config_file.read_bytes()
    metadata_stat = workspace.metadata_directory.stat()
    original_check = safe_files.is_windows_reparse_point
    monkeypatch.setattr(
        safe_files,
        "is_windows_reparse_point",
        lambda status: status == metadata_stat or original_check(status),
    )
    with pytest.raises(ConfigError):
        setup.initialize_workspace(
            workspace.workspace_root, user_config_file=config_file, repair=True
        )
    assert workspace.workspace_config_file.read_bytes() == marker_before
    assert not list(tmp_path.rglob("*.bak"))
