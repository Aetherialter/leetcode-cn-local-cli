from typing import NoReturn

from typer import Exit

from leetcode_local_cli.commands.rendering import error, warning
from leetcode_local_cli.storage.config import (
    ConfigError,
    resolve_app_paths,
    resolve_workspace_paths,
)
from leetcode_local_cli.storage.paths import AppPaths, UserPaths, WorkspacePaths
from leetcode_local_cli.use_cases.errors import ErrorCode, UseCaseError


def get_user_paths() -> UserPaths:
    return UserPaths.defaults()


def require_app_paths() -> AppPaths:
    try:
        return resolve_app_paths()
    except ConfigError as exc:
        raise UseCaseError(str(exc), code=ErrorCode.WORKSPACE_CONFIG) from exc


def require_workspace_paths() -> WorkspacePaths:
    try:
        return resolve_workspace_paths()
    except ConfigError as exc:
        raise UseCaseError(str(exc), code=ErrorCode.WORKSPACE_CONFIG) from exc


def exit_for_use_case_error(exc: UseCaseError) -> NoReturn:
    if exc.warning_only:
        warning(exc.message)
    else:
        error(exc.message)
    if exc.suggestion:
        warning(exc.suggestion)
    raise Exit(1) from exc
