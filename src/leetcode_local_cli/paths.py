from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path
import sys


APP_DIRECTORY_NAME = "leetcode-local-cli"
USER_CONFIG_FILENAME = "config.toml"
WORKSPACE_CONFIG_FILENAME = ".leetcode-local-cli.toml"
SOLUTION_FILENAME = "solution.py"
SESSION_DIRECTORY_NAME = ".leetcode_local_cli"
SESSION_FILENAME = "session.json"


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


@dataclass(frozen=True)
class AppPaths:
    """All filesystem locations used during one CLI invocation."""

    user_config_file: Path
    workspace_root: Path

    @classmethod
    def from_workspace(
        cls,
        workspace_root: str | Path,
        *,
        user_config_file: Path | None = None,
    ) -> "AppPaths":
        return cls(
            user_config_file=(
                get_user_config_file()
                if user_config_file is None
                else normalize_workspace_path(user_config_file)
            ),
            workspace_root=normalize_workspace_path(workspace_root),
        )

    @property
    def workspace_config_file(self) -> Path:
        return self.workspace_root / WORKSPACE_CONFIG_FILENAME

    @property
    def solution_file(self) -> Path:
        return self.workspace_root / SOLUTION_FILENAME

    @property
    def session_directory(self) -> Path:
        return self.workspace_root / SESSION_DIRECTORY_NAME

    @property
    def session_file(self) -> Path:
        return self.session_directory / SESSION_FILENAME
