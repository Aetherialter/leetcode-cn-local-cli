from typing import NoReturn

from typer import Exit

from leetcode_local_cli.config import ConfigError, resolve_app_paths
from leetcode_local_cli.paths import AppPaths
from leetcode_local_cli.ui import error, warning
from leetcode_local_cli.use_cases.common import UseCaseError


def require_app_paths() -> AppPaths:
    try:
        return resolve_app_paths()
    except ConfigError as exc:
        error(str(exc))
        raise Exit(1) from exc


def exit_for_use_case_error(exc: UseCaseError) -> NoReturn:
    if exc.warning_only:
        warning(exc.message)
    else:
        error(exc.message)
    if exc.suggestion:
        warning(exc.suggestion)
    raise Exit(1) from exc
