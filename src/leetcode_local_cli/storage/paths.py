import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

APP_DIRECTORY_NAME = "leetcode-local-cli"
USER_CONFIG_FILENAME = "config.toml"
WORKSPACE_METADATA_DIRECTORY_NAME = ".leetcode_local_cli"
WORKSPACE_CONFIG_FILENAME = "workspace.toml"
SOLUTION_FILENAME = "solution.py"
SESSION_FILENAME = "session.json"
DEVTOOLS_ACTIVE_PORT_FILENAME = "DevToolsActivePort"


def normalize_workspace_path(path: str | Path) -> Path:
    """Return an absolute workspace path without resolving symbolic links."""
    expanded_path = Path(path).expanduser()
    return Path(os.path.abspath(os.fspath(expanded_path)))


def get_user_config_directory(
    *,
    environment: Mapping[str, str] | None = None,
    home: Path | None = None,
    platform: str | None = None,
    os_name: str | None = None,
) -> Path:
    """Return the platform-appropriate per-user configuration directory."""
    active_environment = os.environ if environment is None else environment
    active_home = Path.home() if home is None else home
    active_platform = sys.platform if platform is None else platform
    active_os_name = os.name if os_name is None else os_name

    if active_os_name == "nt":
        app_data = active_environment.get("APPDATA")
        if app_data:
            app_data_path = Path(app_data)
            if app_data_path.is_absolute():
                return app_data_path / APP_DIRECTORY_NAME
        return active_home / "AppData" / "Roaming" / APP_DIRECTORY_NAME

    if active_platform == "darwin":
        return active_home / "Library" / "Application Support" / APP_DIRECTORY_NAME
    xdg_config_home = active_environment.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        xdg_config_home = Path(xdg_config_home)
        if xdg_config_home.is_absolute():
            return xdg_config_home / APP_DIRECTORY_NAME

    return active_home / ".config" / APP_DIRECTORY_NAME


def get_user_config_file() -> Path:
    return get_user_config_directory() / USER_CONFIG_FILENAME


def get_user_state_directory(
    *,
    environment: Mapping[str, str] | None = None,
    home: Path | None = None,
    platform: str | None = None,
    os_name: str | None = None,
) -> Path:
    """Return the platform-appropriate per-user state directory."""
    active_environment = os.environ if environment is None else environment
    active_home = Path.home() if home is None else home
    active_platform = sys.platform if platform is None else platform
    active_os_name = os.name if os_name is None else os_name

    if active_os_name == "nt":
        local_app_data = active_environment.get("LOCALAPPDATA")
        if local_app_data:
            local_app_data_path = Path(local_app_data)
            if local_app_data_path.is_absolute():
                return local_app_data_path / APP_DIRECTORY_NAME
        return active_home / "AppData" / "Local" / APP_DIRECTORY_NAME

    if active_platform == "darwin":
        return active_home / "Library" / "Application Support" / APP_DIRECTORY_NAME

    xdg_state_home = active_environment.get("XDG_STATE_HOME")
    if xdg_state_home:
        xdg_state_home_path = Path(xdg_state_home)
        if xdg_state_home_path.is_absolute():
            return xdg_state_home_path / APP_DIRECTORY_NAME
    return active_home / ".local" / "state" / APP_DIRECTORY_NAME


def get_chrome_user_data_directory(
    *,
    environment: Mapping[str, str] | None = None,
    home: Path | None = None,
    platform: str | None = None,
    os_name: str | None = None,
) -> Path:
    """Return the default Google Chrome Stable user data directory."""
    active_environment = os.environ if environment is None else environment
    active_home = Path.home() if home is None else home
    active_platform = sys.platform if platform is None else platform
    active_os_name = os.name if os_name is None else os_name

    if active_os_name == "nt":
        local_app_data = active_environment.get("LOCALAPPDATA")
        if local_app_data:
            local_app_data_path = Path(local_app_data)
            if local_app_data_path.is_absolute():
                return local_app_data_path / "Google" / "Chrome" / "User Data"
        return active_home / "AppData" / "Local" / "Google" / "Chrome" / "User Data"

    if active_platform == "darwin":
        return active_home / "Library" / "Application Support" / "Google" / "Chrome"

    xdg_config_home = active_environment.get("XDG_CONFIG_HOME")
    base_directory = (
        Path(xdg_config_home)
        if xdg_config_home and Path(xdg_config_home).is_absolute()
        else active_home / ".config"
    )
    return base_directory / "google-chrome"


def get_chrome_devtools_active_port_file() -> Path:
    return get_chrome_user_data_directory() / DEVTOOLS_ACTIVE_PORT_FILENAME


def get_edge_user_data_directory(
    *,
    environment: Mapping[str, str] | None = None,
    home: Path | None = None,
    platform: str | None = None,
    os_name: str | None = None,
) -> Path:
    """Return the default Microsoft Edge user data directory."""
    active_environment = os.environ if environment is None else environment
    active_home = Path.home() if home is None else home
    active_platform = sys.platform if platform is None else platform
    active_os_name = os.name if os_name is None else os_name

    if active_os_name == "nt":
        local_app_data = active_environment.get("LOCALAPPDATA")
        base_directory = (
            Path(local_app_data)
            if local_app_data and Path(local_app_data).is_absolute()
            else active_home / "AppData" / "Local"
        )
        return base_directory / "Microsoft" / "Edge" / "User Data"

    if active_platform == "darwin":
        return active_home / "Library" / "Application Support" / "Microsoft Edge"

    xdg_config_home = active_environment.get("XDG_CONFIG_HOME")
    base_directory = (
        Path(xdg_config_home)
        if xdg_config_home and Path(xdg_config_home).is_absolute()
        else active_home / ".config"
    )
    return base_directory / "microsoft-edge"


def get_edge_devtools_active_port_file() -> Path:
    return get_edge_user_data_directory() / DEVTOOLS_ACTIVE_PORT_FILENAME


@dataclass(frozen=True)
class UserPaths:
    """Per-user configuration and login-state locations."""

    user_config_file: Path
    user_state_directory: Path

    @classmethod
    def defaults(
        cls,
        *,
        user_config_file: Path | None = None,
        user_state_directory: Path | None = None,
    ) -> "UserPaths":
        return cls(
            user_config_file=(
                get_user_config_file()
                if user_config_file is None
                else normalize_workspace_path(user_config_file)
            ),
            user_state_directory=(
                get_user_state_directory()
                if user_state_directory is None
                else normalize_workspace_path(user_state_directory)
            ),
        )

    @property
    def session_file(self) -> Path:
        return self.user_state_directory / SESSION_FILENAME


@dataclass(frozen=True)
class WorkspacePaths:
    """Locations owned by one configured problem-solving workspace."""

    workspace_root: Path

    @classmethod
    def from_root(
        cls,
        workspace_root: str | Path,
    ) -> "WorkspacePaths":
        return cls(workspace_root=normalize_workspace_path(workspace_root))

    @property
    def metadata_directory(self) -> Path:
        return self.workspace_root / WORKSPACE_METADATA_DIRECTORY_NAME

    @property
    def workspace_config_file(self) -> Path:
        return self.metadata_directory / WORKSPACE_CONFIG_FILENAME

    @property
    def solution_file(self) -> Path:
        return self.workspace_root / SOLUTION_FILENAME


@dataclass(frozen=True)
class AppPaths:
    """Combined paths for operations that require both user and workspace state."""

    user: UserPaths
    workspace: WorkspacePaths

    @classmethod
    def from_workspace(
        cls,
        workspace_root: str | Path,
        *,
        user_config_file: Path | None = None,
        user_state_directory: Path | None = None,
    ) -> "AppPaths":
        return cls(
            user=UserPaths.defaults(
                user_config_file=user_config_file,
                user_state_directory=user_state_directory,
            ),
            workspace=WorkspacePaths.from_root(workspace_root),
        )
