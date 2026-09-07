from dataclasses import replace

from leetcode_local_cli.models.editor import EditorConfig
from leetcode_local_cli.storage.config import (
    SUPPORTED_SITE,
    USER_CONFIG_VERSION,
    ConfigError,
    UserConfig,
    load_user_config,
    serialize_user_config,
)
from leetcode_local_cli.storage.paths import UserPaths
from leetcode_local_cli.storage.safe_files import (
    SafeFileError,
    atomic_write_text,
    ensure_regular_directory,
)
from leetcode_local_cli.use_cases.errors import ErrorCode, UseCaseError


def get_editor(paths: UserPaths, override: str | None = None) -> EditorConfig | None:
    try:
        if override is not None:
            return EditorConfig(override)
        config = load_user_config(paths.user_config_file)
        return config.editor if config else None
    except (ConfigError, ValueError) as exc:
        raise UseCaseError(str(exc), code=ErrorCode.WORKSPACE_CONFIG) from exc


def configure_editor(paths: UserPaths, editor: EditorConfig | None) -> None:
    try:
        config = load_user_config(paths.user_config_file)
        if config is None:
            if editor is None:
                return
            config = UserConfig(USER_CONFIG_VERSION, None, SUPPORTED_SITE)
        content = serialize_user_config(
            replace(config, version=USER_CONFIG_VERSION, editor=editor)
        )
        ensure_regular_directory(
            paths.user_config_file.parent, label="用户配置目录", mode=0o700
        )
        atomic_write_text(
            paths.user_config_file,
            content,
            label="用户配置文件",
            mode=0o600,
        )
    except (ConfigError, SafeFileError) as exc:
        raise UseCaseError(str(exc), code=ErrorCode.WORKSPACE_CONFIG) from exc
