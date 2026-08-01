from pathlib import Path

from leetcode_local_cli.config import (
    ConfigError,
    WorkspaceInitResult,
    initialize_workspace,
    load_user_config,
    resolve_app_paths,
)
from leetcode_local_cli.paths import AppPaths
from leetcode_local_cli.use_cases.common import UseCaseError


def resolve_existing_workspace(config_file: Path) -> AppPaths | None:
    try:
        if load_user_config(config_file) is None:
            return None
        return resolve_app_paths(config_file)
    except ConfigError as exc:
        raise UseCaseError(str(exc)) from exc


def configure_workspace(
    workspace_root: Path,
    *,
    config_file: Path,
) -> WorkspaceInitResult:
    try:
        return initialize_workspace(
            workspace_root,
            user_config_file=config_file,
        )
    except ConfigError as exc:
        raise UseCaseError(str(exc)) from exc
