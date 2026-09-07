from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from leetcode_local_cli.storage.config import (
    SUPPORTED_LANGUAGE,
    SUPPORTED_SITE,
    USER_CONFIG_VERSION,
    WORKSPACE_CONFIG_VERSION,
    ConfigError,
    ConfigErrorKind,
    UserConfig,
    WorkspaceConfig,
    load_user_config,
    load_workspace_config,
    resolve_workspace_paths,
    serialize_user_config,
    serialize_workspace_config,
)
from leetcode_local_cli.storage.paths import (
    WorkspacePaths,
    get_user_config_file,
    normalize_workspace_path,
)
from leetcode_local_cli.storage.safe_files import (
    atomic_write_bytes,
    atomic_write_text,
    create_bytes_file,
    create_empty_regular_file,
    ensure_regular_directory,
    validate_directory_target,
    validate_regular_file_target,
)
from leetcode_local_cli.use_cases.errors import ErrorCode, UseCaseError


@dataclass(frozen=True)
class WorkspaceInitResult:
    paths: WorkspacePaths
    workspace_created: bool
    metadata_directory_created: bool
    workspace_config_created: bool
    solution_created: bool
    backups: tuple[Path, ...] = ()

    @property
    def reused(self) -> bool:
        return not any(
            (
                self.workspace_created,
                self.metadata_directory_created,
                self.workspace_config_created,
                self.solution_created,
                bool(self.backups),
            )
        )


def resolve_existing_workspace(config_file: Path) -> WorkspacePaths | None:
    try:
        config = load_user_config(config_file)
        if config is None or config.default_workspace is None:
            return None
        return resolve_workspace_paths(config_file)
    except ConfigError as exc:
        raise _setup_error(exc) from exc


def configure_workspace(
    workspace_root: Path, *, config_file: Path, repair: bool = False
) -> WorkspaceInitResult:
    try:
        return initialize_workspace(
            workspace_root, user_config_file=config_file, repair=repair
        )
    except ConfigError as exc:
        raise _setup_error(exc) from exc


def _setup_error(exc: ConfigError) -> UseCaseError:
    suggestion = (
        "请执行 lc init <完整路径> --repair 恢复损坏配置"
        if exc.kind is ConfigErrorKind.INVALID
        else None
    )
    return UseCaseError(
        str(exc), code=ErrorCode.WORKSPACE_CONFIG, suggestion=suggestion
    )


def _snapshot(path: Path) -> bytes | None:
    validate_directory_target(path.parent, label="配置目录")
    return (
        None
        if validate_regular_file_target(path, label="配置文件") is None
        else path.read_bytes()
    )


def initialize_workspace(
    workspace_root: str | Path,
    *,
    user_config_file: Path | None = None,
    repair: bool = False,
) -> WorkspaceInitResult:
    config_file = (
        get_user_config_file()
        if user_config_file is None
        else normalize_workspace_path(user_config_file)
    )
    paths = WorkspacePaths.from_root(workspace_root)
    created_directories: list[Path] = []
    changed_files: list[tuple[Path, bytes | None]] = []
    backups: list[Path] = []
    solution_created = False
    previous_user: UserConfig | None = None
    try:
        # Validate every original before mutating any target or creating a backup.
        damaged: list[tuple[Path, bytes]] = []
        for path, loader in (
            (config_file, load_user_config),
            (paths.workspace_config_file, load_workspace_config),
        ):
            try:
                loaded = loader(path)
                if isinstance(loaded, UserConfig):
                    previous_user = loaded
            except ConfigError as exc:
                if not repair or exc.kind is not ConfigErrorKind.INVALID:
                    raise
                original = _snapshot(path)
                if original is None:
                    raise ConfigError("待修复配置不存在")
                damaged.append((path, original))
        validate_regular_file_target(paths.solution_file, label="solution.py")
        original_user = _snapshot(config_file)
        original_marker = _snapshot(paths.workspace_config_file)
        for directory, label, mode in (
            (paths.workspace_root, "工作区目录", 0o755),
            (paths.metadata_directory, "工作区元数据目录", 0o700),
            (config_file.parent, "用户配置目录", 0o700),
        ):
            if ensure_regular_directory(directory, label=label, mode=mode):
                created_directories.append(directory)
        for path, original in damaged:
            backup = path.with_name(f"{path.name}.{uuid4().hex}.bak")
            create_bytes_file(backup, original, label="配置备份")
            backups.append(backup)
        if original_marker is None or any(
            path == paths.workspace_config_file for path, _ in damaged
        ):
            atomic_write_text(
                paths.workspace_config_file,
                serialize_workspace_config(
                    WorkspaceConfig(
                        WORKSPACE_CONFIG_VERSION, SUPPORTED_SITE, SUPPORTED_LANGUAGE
                    )
                ),
                label="工作区配置文件",
            )
            changed_files.append((paths.workspace_config_file, original_marker))
        solution_created = create_empty_regular_file(
            paths.solution_file, label="solution.py"
        )
        if solution_created:
            changed_files.append((paths.solution_file, None))
        atomic_write_text(
            config_file,
            serialize_user_config(
                UserConfig(
                    USER_CONFIG_VERSION,
                    paths.workspace_root,
                    SUPPORTED_SITE,
                    editor=previous_user.editor if previous_user else None,
                )
            ),
            label="用户配置文件",
            mode=0o600,
        )
        changed_files.append((config_file, original_user))
    except (OSError, ConfigError) as exc:
        restore_failed = False
        for path, original in reversed(changed_files):
            try:
                if original is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_write_bytes(path, original, label="原始配置")
            except OSError:
                restore_failed = True
        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except OSError:
                pass
        if restore_failed:
            raise ConfigError(
                "初始化失败且部分配置无法自动恢复，请检查本地 .bak 备份",
                kind=ConfigErrorKind.IO,
            ) from exc
        if isinstance(exc, ConfigError):
            raise
        raise ConfigError(str(exc), kind=ConfigErrorKind.IO) from exc
    return WorkspaceInitResult(
        paths=paths,
        workspace_created=paths.workspace_root in created_directories,
        metadata_directory_created=paths.metadata_directory in created_directories,
        workspace_config_created=original_marker is None,
        solution_created=solution_created,
        backups=tuple(backups),
    )
