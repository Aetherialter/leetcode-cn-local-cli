from dataclasses import dataclass
import json
from pathlib import Path
import tomllib

from leetcode_local_cli.paths import (
    AppPaths,
    UserPaths,
    WorkspacePaths,
    get_user_config_file,
    normalize_workspace_path,
)
from leetcode_local_cli.safe_files import (
    SafeFileError,
    atomic_write_text,
    create_empty_regular_file,
    create_text_file,
    ensure_regular_directory,
    validate_directory_target,
    validate_regular_file_target,
)


CONFIG_VERSION = 1
SUPPORTED_SITE = "cn"
SUPPORTED_LANGUAGE = "python3"


class ConfigError(ValueError):
    """Configuration is missing, malformed, unsupported, or unsafe."""


@dataclass(frozen=True)
class UserConfig:
    version: int
    default_workspace: Path
    default_site: str


@dataclass(frozen=True)
class WorkspaceConfig:
    version: int
    site: str
    language: str


@dataclass(frozen=True)
class WorkspaceInitResult:
    paths: WorkspacePaths
    workspace_created: bool
    metadata_directory_created: bool
    workspace_config_created: bool
    solution_created: bool

    @property
    def reused(self) -> bool:
        return not any(
            (
                self.workspace_created,
                self.metadata_directory_created,
                self.workspace_config_created,
                self.solution_created,
            )
        )


def _load_toml(path: Path, *, label: str) -> dict[str, object] | None:
    try:
        target_status = validate_regular_file_target(path, label=label)
    except SafeFileError as exc:
        raise ConfigError(str(exc)) from exc
    if target_status is None:
        return None

    try:
        with path.open("rb") as file:
            return tomllib.load(file)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{label}不是有效的 TOML") from exc
    except (OSError, UnicodeError) as exc:
        raise ConfigError(f"无法读取{label}") from exc


def _require_exact_keys(
    data: dict[str, object],
    expected_keys: set[str],
    *,
    label: str,
) -> None:
    actual_keys = set(data)
    if actual_keys == expected_keys:
        return
    missing_keys = sorted(expected_keys - actual_keys)
    unknown_keys = sorted(actual_keys - expected_keys)
    details: list[str] = []
    if missing_keys:
        details.append(f"缺少字段：{'、'.join(missing_keys)}")
    if unknown_keys:
        details.append(f"未知字段：{'、'.join(unknown_keys)}")
    raise ConfigError(f"{label}结构无效（{'；'.join(details)}）")


def _require_version(data: dict[str, object], *, label: str) -> int:
    version = data.get("version")
    if type(version) is not int:
        raise ConfigError(f"{label}中的 version 必须是整数")
    if version != CONFIG_VERSION:
        raise ConfigError(
            f"{label}版本不受支持：{version}，当前支持版本为 {CONFIG_VERSION}"
        )
    return version


def _require_string(
    data: dict[str, object],
    key: str,
    *,
    label: str,
) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{label}中的 {key} 必须是非空字符串")
    return value


def load_user_config(path: Path) -> UserConfig | None:
    data = _load_toml(path, label="用户配置文件")
    if data is None:
        return None
    _require_exact_keys(
        data,
        {"version", "default_workspace", "default_site"},
        label="用户配置文件",
    )
    version = _require_version(data, label="用户配置文件")
    workspace_value = _require_string(
        data,
        "default_workspace",
        label="用户配置文件",
    )
    default_site = _require_string(
        data,
        "default_site",
        label="用户配置文件",
    )
    workspace_path = Path(workspace_value).expanduser()
    if not workspace_path.is_absolute():
        raise ConfigError("default_workspace 必须是绝对路径")
    if default_site != SUPPORTED_SITE:
        raise ConfigError(f"当前不支持站点：{default_site}")
    return UserConfig(
        version=version,
        default_workspace=normalize_workspace_path(workspace_path),
        default_site=default_site,
    )


def load_workspace_config(path: Path) -> WorkspaceConfig | None:
    data = _load_toml(path, label="工作区配置文件")
    if data is None:
        return None
    _require_exact_keys(
        data,
        {"version", "site", "language"},
        label="工作区配置文件",
    )
    version = _require_version(data, label="工作区配置文件")
    site = _require_string(data, "site", label="工作区配置文件")
    language = _require_string(data, "language", label="工作区配置文件")
    if site != SUPPORTED_SITE:
        raise ConfigError(f"当前不支持站点：{site}")
    if language != SUPPORTED_LANGUAGE:
        raise ConfigError(f"当前不支持语言：{language}")
    return WorkspaceConfig(version=version, site=site, language=language)


def _resolve_workspace_paths(config_file: Path) -> WorkspacePaths:
    user_config = load_user_config(config_file)
    if user_config is None:
        raise ConfigError("尚未配置工作区，请先执行 lc init")
    workspace_paths = WorkspacePaths.from_root(user_config.default_workspace)
    try:
        workspace_status = validate_directory_target(
            workspace_paths.workspace_root,
            label="默认工作区目录",
        )
    except SafeFileError as exc:
        raise ConfigError(str(exc)) from exc
    if workspace_status is None:
        raise ConfigError("默认工作区目录不存在，请执行 lc init <完整路径> 重新配置")
    workspace_config = load_workspace_config(workspace_paths.workspace_config_file)
    if workspace_config is None:
        raise ConfigError("默认目录缺少工作区标记，请执行 lc init <完整路径> 重新配置")
    if workspace_config.site != user_config.default_site:
        raise ConfigError("用户配置与工作区配置的站点不一致")
    return workspace_paths


def resolve_workspace_paths(
    user_config_file: Path | None = None,
) -> WorkspacePaths:
    config_file = (
        get_user_config_file()
        if user_config_file is None
        else normalize_workspace_path(user_config_file)
    )
    return _resolve_workspace_paths(config_file)


def resolve_app_paths(
    user_config_file: Path | None = None,
    *,
    user_state_directory: Path | None = None,
) -> AppPaths:
    user_paths = UserPaths.defaults(
        user_config_file=user_config_file,
        user_state_directory=user_state_directory,
    )
    return AppPaths(
        user=user_paths,
        workspace=_resolve_workspace_paths(user_paths.user_config_file),
    )


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _serialize_user_config(config: UserConfig) -> str:
    return (
        f"version = {config.version}\n"
        f"default_workspace = {_toml_string(config.default_workspace.as_posix())}\n"
        f"default_site = {_toml_string(config.default_site)}\n"
    )


def _serialize_workspace_config(config: WorkspaceConfig) -> str:
    return (
        f"version = {config.version}\n"
        f"site = {_toml_string(config.site)}\n"
        f"language = {_toml_string(config.language)}\n"
    )


def initialize_workspace(
    workspace_root: str | Path,
    *,
    user_config_file: Path | None = None,
) -> WorkspaceInitResult:
    config_file = (
        get_user_config_file()
        if user_config_file is None
        else normalize_workspace_path(user_config_file)
    )
    load_user_config(config_file)
    paths = WorkspacePaths.from_root(workspace_root)

    workspace_created = False
    metadata_directory_created = False
    workspace_config_created = False
    solution_created = False
    try:
        workspace_created = ensure_regular_directory(
            paths.workspace_root,
            label="工作区目录",
        )
        metadata_directory_created = ensure_regular_directory(
            paths.metadata_directory,
            label="工作区元数据目录",
            mode=0o700,
        )
        existing_workspace_config = load_workspace_config(paths.workspace_config_file)
        if existing_workspace_config is None:
            workspace_config_created = create_text_file(
                paths.workspace_config_file,
                _serialize_workspace_config(
                    WorkspaceConfig(
                        version=CONFIG_VERSION,
                        site=SUPPORTED_SITE,
                        language=SUPPORTED_LANGUAGE,
                    )
                ),
                label="工作区配置文件",
            )
        elif (
            existing_workspace_config.site != SUPPORTED_SITE
            or existing_workspace_config.language != SUPPORTED_LANGUAGE
        ):
            raise ConfigError("现有工作区配置与当前版本不兼容")

        solution_created = create_empty_regular_file(
            paths.solution_file,
            label="solution.py",
        )
        ensure_regular_directory(
            config_file.parent,
            label="用户配置目录",
            mode=0o700,
        )
        atomic_write_text(
            config_file,
            _serialize_user_config(
                UserConfig(
                    version=CONFIG_VERSION,
                    default_workspace=paths.workspace_root,
                    default_site=SUPPORTED_SITE,
                )
            ),
            label="用户配置文件",
            mode=0o600,
        )
    except (SafeFileError, ConfigError) as exc:
        if solution_created:
            _remove_created_file(paths.solution_file)
        if workspace_config_created:
            _remove_created_file(paths.workspace_config_file)
        if metadata_directory_created:
            _remove_created_directory(paths.metadata_directory)
        if workspace_created:
            _remove_created_directory(paths.workspace_root)
        if isinstance(exc, ConfigError):
            raise
        raise ConfigError(str(exc)) from exc

    return WorkspaceInitResult(
        paths=paths,
        workspace_created=workspace_created,
        metadata_directory_created=metadata_directory_created,
        workspace_config_created=workspace_config_created,
        solution_created=solution_created,
    )


def _remove_created_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _remove_created_directory(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        pass
