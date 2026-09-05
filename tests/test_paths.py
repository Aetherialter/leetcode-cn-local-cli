from pathlib import Path

from leetcode_local_cli.storage.paths import (
    AppPaths,
    UserPaths,
    WorkspacePaths,
    get_chrome_user_data_directory,
    get_edge_user_data_directory,
    get_user_config_directory,
    get_user_state_directory,
)


def test_app_paths_derive_workspace_files(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    user_config_file = tmp_path / "config" / "config.toml"
    user_state_directory = tmp_path / "state"

    paths = AppPaths.from_workspace(
        workspace_root,
        user_config_file=user_config_file,
        user_state_directory=user_state_directory,
    )

    assert paths.user == UserPaths(
        user_config_file=user_config_file,
        user_state_directory=user_state_directory,
    )
    assert paths.workspace == WorkspacePaths(workspace_root=workspace_root)
    assert paths.workspace.workspace_config_file == (
        workspace_root / ".leetcode_local_cli" / "workspace.toml"
    )
    assert paths.workspace.solution_file == workspace_root / "solution.py"
    assert paths.user.session_file == user_state_directory / "session.json"


def test_windows_state_directory_uses_local_appdata(tmp_path: Path) -> None:
    local_app_data = tmp_path / "AppData" / "Local"

    result = get_user_state_directory(
        environment={"LOCALAPPDATA": str(local_app_data)},
        home=tmp_path,
        platform="win32",
        os_name="nt",
    )

    assert result == local_app_data / "leetcode-local-cli"


def test_windows_state_directory_falls_back_for_relative_localappdata(
    tmp_path: Path,
) -> None:
    result = get_user_state_directory(
        environment={"LOCALAPPDATA": "relative/path"},
        home=tmp_path,
        platform="win32",
        os_name="nt",
    )

    assert result == tmp_path / "AppData" / "Local" / "leetcode-local-cli"


def test_macos_state_directory_uses_application_support(tmp_path: Path) -> None:
    result = get_user_state_directory(
        environment={},
        home=tmp_path,
        platform="darwin",
        os_name="posix",
    )

    assert result == (
        tmp_path / "Library" / "Application Support" / "leetcode-local-cli"
    )


def test_linux_state_directory_uses_xdg_state_home(tmp_path: Path) -> None:
    xdg_state_home = tmp_path / "state"

    result = get_user_state_directory(
        environment={"XDG_STATE_HOME": str(xdg_state_home)},
        home=tmp_path,
        platform="linux",
        os_name="posix",
    )

    assert result == xdg_state_home / "leetcode-local-cli"


def test_linux_state_directory_falls_back_for_relative_xdg_path(
    tmp_path: Path,
) -> None:
    result = get_user_state_directory(
        environment={"XDG_STATE_HOME": "relative/path"},
        home=tmp_path,
        platform="linux",
        os_name="posix",
    )

    assert result == tmp_path / ".local" / "state" / "leetcode-local-cli"


def test_windows_config_directory_uses_appdata(tmp_path: Path) -> None:
    app_data = tmp_path / "AppData" / "Roaming"

    result = get_user_config_directory(
        environment={"APPDATA": str(app_data)},
        home=tmp_path,
        platform="win32",
        os_name="nt",
    )

    assert result == app_data / "leetcode-local-cli"


def test_windows_config_directory_falls_back_when_appdata_is_relative(
    tmp_path: Path,
) -> None:
    result = get_user_config_directory(
        environment={"APPDATA": "relative/path"},
        home=tmp_path,
        platform="win32",
        os_name="nt",
    )

    assert result == tmp_path / "AppData" / "Roaming" / "leetcode-local-cli"


def test_macos_config_directory_uses_application_support(tmp_path: Path) -> None:
    result = get_user_config_directory(
        environment={},
        home=tmp_path,
        platform="darwin",
        os_name="posix",
    )

    assert result == (
        tmp_path / "Library" / "Application Support" / "leetcode-local-cli"
    )


def test_linux_config_directory_uses_xdg_config_home(tmp_path: Path) -> None:
    xdg_config_home = tmp_path / "xdg"

    result = get_user_config_directory(
        environment={"XDG_CONFIG_HOME": str(xdg_config_home)},
        home=tmp_path,
        platform="linux",
        os_name="posix",
    )

    assert result == xdg_config_home / "leetcode-local-cli"


def test_linux_config_directory_falls_back_for_relative_xdg_path(
    tmp_path: Path,
) -> None:
    result = get_user_config_directory(
        environment={"XDG_CONFIG_HOME": "relative/path"},
        home=tmp_path,
        platform="linux",
        os_name="posix",
    )

    assert result == tmp_path / ".config" / "leetcode-local-cli"


def test_windows_chrome_user_data_directory_uses_local_appdata(tmp_path: Path) -> None:
    local_app_data = tmp_path / "AppData" / "Local"

    result = get_chrome_user_data_directory(
        environment={"LOCALAPPDATA": str(local_app_data)},
        home=tmp_path,
        platform="win32",
        os_name="nt",
    )

    assert result == local_app_data / "Google" / "Chrome" / "User Data"


def test_linux_chrome_user_data_directory_uses_xdg_config_home(
    tmp_path: Path,
) -> None:
    xdg_config_home = tmp_path / "config"

    result = get_chrome_user_data_directory(
        environment={"XDG_CONFIG_HOME": str(xdg_config_home)},
        home=tmp_path,
        platform="linux",
        os_name="posix",
    )

    assert result == xdg_config_home / "google-chrome"


def test_windows_edge_user_data_directory_uses_local_appdata(tmp_path: Path) -> None:
    local_app_data = tmp_path / "AppData" / "Local"

    result = get_edge_user_data_directory(
        environment={"LOCALAPPDATA": str(local_app_data)},
        home=tmp_path,
        platform="win32",
        os_name="nt",
    )

    assert result == local_app_data / "Microsoft" / "Edge" / "User Data"


def test_linux_edge_user_data_directory_uses_xdg_config_home(tmp_path: Path) -> None:
    xdg_config_home = tmp_path / "config"

    result = get_edge_user_data_directory(
        environment={"XDG_CONFIG_HOME": str(xdg_config_home)},
        home=tmp_path,
        platform="linux",
        os_name="posix",
    )

    assert result == xdg_config_home / "microsoft-edge"


def test_runtime_modules_do_not_capture_current_directory_at_import() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src" / "leetcode_local_cli"

    for module_name in (
        "integrations/devtools.py",
        "integrations/browser.py",
        "storage/solution.py",
        "storage/config.py",
        "storage/paths.py",
    ):
        source = (source_root / module_name).read_text(encoding="utf-8")
        assert "Path.cwd()" not in source
