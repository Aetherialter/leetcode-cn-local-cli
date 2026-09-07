import json
import tomllib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from leetcode_local_cli.models.editor import EditorConfig
from leetcode_local_cli.storage.paths import (
    AppPaths,
    UserPaths,
    WorkspacePaths,
    get_user_config_file,
    normalize_workspace_path,
)
from leetcode_local_cli.storage.safe_files import (
    SafeFileError,
    validate_directory_target,
    validate_regular_file_target,
)

USER_CONFIG_VERSION = 2
WORKSPACE_CONFIG_VERSION = 1
SUPPORTED_SITE = "cn"
SUPPORTED_LANGUAGE = "python3"


class ConfigErrorKind(str, Enum):
    INVALID = "invalid"
    UNSUPPORTED = "unsupported"
    UNSAFE = "unsafe"
    IO = "io"
    MISSING = "missing"


class ConfigError(ValueError):
    """Configuration is missing, malformed, unsupported, or unsafe."""

    def __init__(
        self, message: str, *, kind: ConfigErrorKind = ConfigErrorKind.INVALID
    ) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class UserConfig:
    version: int
    default_workspace: Path | None
    default_site: str
    editor: EditorConfig | None = None


@dataclass(frozen=True)
class WorkspaceConfig:
    version: int
    site: str
    language: str


def _load_toml(path: Path, *, label: str) -> dict[str, object] | None:
    try:
        validate_directory_target(path.parent, label=f"{label}所在目录")
        target_status = validate_regular_file_target(path, label=label)
    except SafeFileError as exc:
        raise ConfigError(str(exc), kind=ConfigErrorKind.UNSAFE) from exc
    if target_status is None:
        return None

    try:
        with path.open("rb") as file:
            return tomllib.load(file)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{label}不是有效的 TOML") from exc
    except UnicodeError as exc:
        raise ConfigError(f"{label}不是有效的 UTF-8 编码") from exc
    except OSError as exc:
        raise ConfigError(f"无法读取{label}", kind=ConfigErrorKind.IO) from exc


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


def _require_version(
    data: dict[str, object], *, label: str, supported: tuple[int, ...]
) -> int:
    version = data.get("version")
    if type(version) is not int:
        raise ConfigError(f"{label}中的 version 必须是整数")
    if version not in supported:
        raise ConfigError(
            f"{label}版本不受支持：{version}，当前支持版本为 {'、'.join(map(str, supported))}",
            kind=ConfigErrorKind.UNSUPPORTED,
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
    return _parse_user_config(data)


def _parse_user_config(data: dict[str, object]) -> UserConfig:
    # Read v1 without rewriting it; explicit settings/init writes always use v2.
    version = _require_version(
        data, label="用户配置文件", supported=(1, USER_CONFIG_VERSION)
    )
    default_site = _require_string(
        data,
        "default_site",
        label="用户配置文件",
    )
    if default_site != SUPPORTED_SITE:
        raise ConfigError(
            f"当前不支持站点：{default_site}", kind=ConfigErrorKind.UNSUPPORTED
        )
    _require_exact_keys(
        data,
        {"version", "default_site"} | (set(data) & {"default_workspace", "editor"}),
        label="用户配置文件",
    )
    workspace_path = None
    if "default_workspace" in data:
        workspace_value = _require_string(
            data, "default_workspace", label="用户配置文件"
        )
        workspace_path = Path(workspace_value).expanduser()
        if not workspace_path.is_absolute():
            raise ConfigError("default_workspace 必须是绝对路径")
        workspace_path = normalize_workspace_path(workspace_path)
    return UserConfig(
        version=version,
        default_workspace=workspace_path,
        default_site=default_site,
        editor=_load_editor(data["editor"]) if "editor" in data else None,
    )


def _load_editor(value: object) -> EditorConfig:
    if not isinstance(value, dict):
        raise ConfigError("editor 必须是包含 command 和 args 的 TOML 表")
    _require_exact_keys(value, {"command", "args"}, label="编辑器配置")
    command = _require_string(value, "command", label="编辑器配置")
    args = value["args"]
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        raise ConfigError("editor.args 必须是字符串数组")
    try:
        return EditorConfig(command, tuple(args))
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc


def load_workspace_config(path: Path) -> WorkspaceConfig | None:
    data = _load_toml(path, label="工作区配置文件")
    if data is None:
        return None
    version = _require_version(
        data, label="工作区配置文件", supported=(WORKSPACE_CONFIG_VERSION,)
    )
    site = _require_string(data, "site", label="工作区配置文件")
    language = _require_string(data, "language", label="工作区配置文件")
    if site != SUPPORTED_SITE:
        raise ConfigError(f"当前不支持站点：{site}", kind=ConfigErrorKind.UNSUPPORTED)
    if language != SUPPORTED_LANGUAGE:
        raise ConfigError(
            f"当前不支持语言：{language}", kind=ConfigErrorKind.UNSUPPORTED
        )
    _require_exact_keys(
        data,
        {"version", "site", "language"},
        label="工作区配置文件",
    )
    return WorkspaceConfig(version=version, site=site, language=language)


def _resolve_workspace_paths(config_file: Path) -> WorkspacePaths:
    user_config = load_user_config(config_file)
    if user_config is None or user_config.default_workspace is None:
        raise ConfigError(
            "尚未配置工作区，请先执行 lc init", kind=ConfigErrorKind.MISSING
        )
    workspace_paths = WorkspacePaths.from_root(user_config.default_workspace)
    try:
        workspace_status = validate_directory_target(
            workspace_paths.workspace_root,
            label="默认工作区目录",
        )
    except SafeFileError as exc:
        raise ConfigError(str(exc), kind=ConfigErrorKind.UNSAFE) from exc
    if workspace_status is None:
        raise ConfigError(
            "默认工作区目录不存在，请执行 lc init <完整路径> 重新配置",
            kind=ConfigErrorKind.MISSING,
        )
    workspace_config = load_workspace_config(workspace_paths.workspace_config_file)
    if workspace_config is None:
        raise ConfigError(
            "默认目录缺少工作区标记，请执行 lc init <完整路径> 重新配置",
            kind=ConfigErrorKind.MISSING,
        )
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
    # JSON handles C0 escapes, but TOML also forbids a literal DEL character.
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007f")


def _validate_serialized_toml(content: str) -> dict[str, object]:
    try:
        content.encode("utf-8")
        return tomllib.loads(content)
    except (UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError("配置无法序列化为有效的 UTF-8 TOML") from exc


def serialize_user_config(config: UserConfig) -> str:
    _require_version(
        {"version": config.version},
        label="待写入用户配置",
        supported=(USER_CONFIG_VERSION,),
    )
    lines = [f"version = {config.version}"]
    if config.default_workspace is not None:
        lines.append(
            f"default_workspace = {_toml_string(config.default_workspace.as_posix())}"
        )
    lines.append(f"default_site = {_toml_string(config.default_site)}")
    if config.editor is not None:
        lines.extend(
            (
                "",
                "[editor]",
                f"command = {_toml_string(config.editor.command)}",
                f"args = [{', '.join(_toml_string(arg) for arg in config.editor.args)}]",
            )
        )
    content = "\n".join(lines) + "\n"
    _parse_user_config(_validate_serialized_toml(content))
    return content


def serialize_workspace_config(config: WorkspaceConfig) -> str:
    return (
        f"version = {config.version}\n"
        f"site = {_toml_string(config.site)}\n"
        f"language = {_toml_string(config.language)}\n"
    )
