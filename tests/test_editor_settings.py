from pathlib import Path
import tomllib

import pytest
from typer.testing import CliRunner

from leetcode_local_cli.cli import app
from leetcode_local_cli.commands import common
from leetcode_local_cli.models.editor import EditorConfig
from leetcode_local_cli.storage.config import (
    USER_CONFIG_VERSION,
    WORKSPACE_CONFIG_VERSION,
    ConfigError,
    ConfigErrorKind,
    load_user_config,
    load_workspace_config,
    resolve_workspace_paths,
)
from leetcode_local_cli.storage.paths import UserPaths
from leetcode_local_cli.use_cases.errors import UseCaseError
from leetcode_local_cli.use_cases.settings import configure_editor, get_editor
from leetcode_local_cli.use_cases.setup import (
    initialize_workspace,
    resolve_existing_workspace,
)


@pytest.fixture
def settings_paths(tmp_path, monkeypatch):
    paths = UserPaths(tmp_path / "config" / "config.toml", tmp_path / "state")
    monkeypatch.setattr(common, "get_user_paths", lambda: paths)
    return paths


def test_configure_editor_before_init_and_preserve_on_workspace_change(
    settings_paths, tmp_path
) -> None:
    editor = EditorConfig("zed", ("--new", "value with spaces"))
    configure_editor(settings_paths, editor)
    assert get_editor(settings_paths) == editor
    assert not settings_paths.user_state_directory.exists()
    assert resolve_existing_workspace(settings_paths.user_config_file) is None
    with pytest.raises(ConfigError, match="尚未配置工作区"):
        resolve_workspace_paths(settings_paths.user_config_file)
    for name in ("first", "second"):
        initialize_workspace(
            tmp_path / name, user_config_file=settings_paths.user_config_file
        )
        assert get_editor(settings_paths) == editor
    configure_editor(settings_paths, None)
    config = load_user_config(settings_paths.user_config_file)
    assert config is not None and config.default_workspace == tmp_path / "second"
    assert config.editor is None


def test_editor_override_does_not_inherit_args_or_write_config(settings_paths) -> None:
    configure_editor(settings_paths, EditorConfig("zed", ("--new",)))
    original = settings_paths.user_config_file.read_bytes()
    assert get_editor(settings_paths, "code") == EditorConfig("code")
    assert settings_paths.user_config_file.read_bytes() == original


def test_config_editor_cli_set_show_clear_without_workspace(settings_paths) -> None:
    runner = CliRunner()
    assert runner.invoke(app, ["config", "editor", "zed", "--arg=--new"]).exit_code == 0
    shown = runner.invoke(app, ["config", "editor"])
    assert shown.exit_code == 0 and '["zed", "--new"]' in shown.output
    assert runner.invoke(app, ["config", "editor", "--clear"]).exit_code == 0
    assert get_editor(settings_paths) is None
    assert not settings_paths.user_state_directory.exists()


@pytest.mark.parametrize("arguments", [["--arg=x"], ["zed", "--clear"], [""]])
def test_config_editor_rejects_invalid_cli(settings_paths, arguments) -> None:
    assert CliRunner().invoke(app, ["config", "editor", *arguments]).exit_code == 2
    assert not settings_paths.user_config_file.exists()


@pytest.mark.parametrize(
    "editor_toml",
    [
        'editor = "zed"',
        '[editor]\ncommand = "zed"\nargs = "--new"',
        '[editor]\ncommand = "zed"\nargs = [1]',
        '[editor]\ncommand = "zed"\nargs = []\nunknown = true',
        '[editor]\ncommand = ""\nargs = []',
    ],
)
def test_editor_config_rejects_corruption_without_overwriting(
    settings_paths, editor_toml
) -> None:
    path = settings_paths.user_config_file
    path.parent.mkdir()
    path.write_text(
        f'version = {USER_CONFIG_VERSION}\ndefault_site = "cn"\n' + editor_toml,
        encoding="utf-8",
    )
    original = path.read_bytes()
    with pytest.raises(UseCaseError):
        configure_editor(settings_paths, EditorConfig("zed"))
    assert path.read_bytes() == original


@pytest.mark.parametrize("version", [1, USER_CONFIG_VERSION])
def test_editor_failed_write_preserves_original(
    settings_paths, monkeypatch, version
) -> None:
    from leetcode_local_cli.storage import safe_files

    configure_editor(settings_paths, EditorConfig("zed"))
    path = settings_paths.user_config_file
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            f"version = {USER_CONFIG_VERSION}", f"version = {version}"
        ),
        encoding="utf-8",
    )
    original = settings_paths.user_config_file.read_bytes()

    def fail_replace(*args):
        raise PermissionError("synthetic failure")

    monkeypatch.setattr(safe_files.os, "replace", fail_replace)
    with pytest.raises(UseCaseError):
        configure_editor(settings_paths, EditorConfig("code"))
    assert settings_paths.user_config_file.read_bytes() == original


def test_editor_rejects_directory_target(settings_paths) -> None:
    settings_paths.user_config_file.mkdir(parents=True)
    with pytest.raises(UseCaseError):
        configure_editor(settings_paths, EditorConfig("zed"))


@pytest.mark.parametrize(
    "command", ["relative/editor", "bad\ncommand", "bad\x00command", "bad\x7fcommand"]
)
def test_editor_command_validation(command) -> None:
    with pytest.raises(ValueError):
        EditorConfig(command)


def test_editor_path_and_args_round_trip(settings_paths, tmp_path: Path) -> None:
    editor = EditorConfig(
        str(tmp_path / 'Editor "quoted".exe'), ('"quoted"', "a\\b", "")
    )
    configure_editor(settings_paths, editor)
    assert get_editor(settings_paths) == editor


def test_editor_args_round_trip_control_characters_and_unicode(settings_paths) -> None:
    args = tuple(chr(code) for code in range(1, 32)) + (
        "\x7f",
        "\u4e2d\u6587",
        "\U0001f600",
        "\\u007f",
    )
    editor = EditorConfig("zed", args)
    configure_editor(settings_paths, editor)
    content = settings_paths.user_config_file.read_text(encoding="utf-8")
    assert "\x7f" not in content
    assert tomllib.loads(content)["editor"]["args"] == list(args)
    assert get_editor(settings_paths) == editor


@pytest.mark.parametrize("broken_escape", [False, True])
def test_editor_invalid_serialization_preserves_config(
    settings_paths, monkeypatch, broken_escape
) -> None:
    from leetcode_local_cli.storage import config

    configure_editor(settings_paths, EditorConfig("zed"))
    original = settings_paths.user_config_file.read_bytes()
    if broken_escape:
        monkeypatch.setattr(config, "_toml_string", lambda value: '"\x7f"')
        editor = EditorConfig("code")
    else:
        editor = EditorConfig("code", ("\ud800",))
    with pytest.raises(UseCaseError, match="有效的 UTF-8 TOML"):
        configure_editor(settings_paths, editor)
    assert settings_paths.user_config_file.read_bytes() == original
    assert list(settings_paths.user_config_file.parent.iterdir()) == [
        settings_paths.user_config_file
    ]


@pytest.mark.parametrize("has_editor", [False, True])
@pytest.mark.parametrize("action", ["init", "set", "clear"])
def test_v1_config_is_read_only_until_explicit_write(
    settings_paths, tmp_path, has_editor, action
) -> None:
    workspace = initialize_workspace(
        tmp_path / "workspace", user_config_file=settings_paths.user_config_file
    ).paths
    if has_editor:
        configure_editor(settings_paths, EditorConfig("zed", ("--new",)))
    path = settings_paths.user_config_file
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            f"version = {USER_CONFIG_VERSION}", "version = 1"
        ),
        encoding="utf-8",
    )
    original = path.read_bytes()
    marker = workspace.workspace_config_file.read_bytes()
    workspace.solution_file.write_bytes(b"user code")
    expected_editor = EditorConfig("zed", ("--new",)) if has_editor else None

    assert get_editor(settings_paths) == expected_editor
    assert resolve_workspace_paths(path) == workspace
    assert path.read_bytes() == original

    if action == "init":
        initialize_workspace(workspace.workspace_root, user_config_file=path)
    else:
        expected_editor = EditorConfig("code") if action == "set" else None
        configure_editor(settings_paths, expected_editor)
    loaded = load_user_config(path)
    assert loaded is not None and loaded.version == USER_CONFIG_VERSION == 2
    assert loaded.default_workspace == workspace.workspace_root
    assert loaded.editor == expected_editor
    assert workspace.workspace_config_file.read_bytes() == marker
    marker_config = load_workspace_config(workspace.workspace_config_file)
    assert marker_config is not None
    assert marker_config.version == WORKSPACE_CONFIG_VERSION == 1
    assert workspace.solution_file.read_bytes() == b"user code"
    assert not settings_paths.user_state_directory.exists()


def test_future_user_config_is_unsupported_before_unknown_fields(
    settings_paths,
) -> None:
    path = settings_paths.user_config_file
    path.parent.mkdir()
    path.write_bytes(b'version = 3\nfuture_editor = "preserve"\n')
    original = path.read_bytes()
    with pytest.raises(ConfigError) as caught:
        load_user_config(path)
    assert caught.value.kind is ConfigErrorKind.UNSUPPORTED
    with pytest.raises(UseCaseError):
        configure_editor(settings_paths, EditorConfig("zed"))
    assert path.read_bytes() == original
