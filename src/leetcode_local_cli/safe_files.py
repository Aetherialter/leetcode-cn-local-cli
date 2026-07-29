import os
from pathlib import Path
import stat
import tempfile


class SafeFileError(OSError):
    """A filesystem target is unsafe or cannot be accessed reliably."""


def is_windows_reparse_point(file_status: object) -> bool:
    reparse_point_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    file_attributes = getattr(file_status, "st_file_attributes", 0)
    return bool(reparse_point_flag and file_attributes & reparse_point_flag)


def validate_regular_file_target(path: Path, *, label: str) -> os.stat_result | None:
    """Return target metadata, allowing a missing target but rejecting links."""
    try:
        file_status = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise SafeFileError(f"无法检查{label}") from exc

    if stat.S_ISLNK(file_status.st_mode):
        raise SafeFileError(f"{label}是符号链接或断链，已拒绝操作")
    if is_windows_reparse_point(file_status):
        raise SafeFileError(f"{label}是 Windows reparse point，已拒绝操作")
    if stat.S_ISDIR(file_status.st_mode):
        raise SafeFileError(f"{label}是目录，已拒绝操作")
    if not stat.S_ISREG(file_status.st_mode):
        raise SafeFileError(f"{label}不是普通文件，已拒绝操作")
    return file_status


def validate_directory_target(path: Path, *, label: str) -> os.stat_result | None:
    """Return directory metadata, allowing a missing target but rejecting links."""
    try:
        file_status = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise SafeFileError(f"无法检查{label}") from exc

    if stat.S_ISLNK(file_status.st_mode):
        raise SafeFileError(f"{label}是符号链接或断链，已拒绝操作")
    if is_windows_reparse_point(file_status):
        raise SafeFileError(f"{label}是 Windows reparse point，已拒绝操作")
    if not stat.S_ISDIR(file_status.st_mode):
        raise SafeFileError(f"{label}不是普通目录，已拒绝操作")
    return file_status


def ensure_regular_directory(path: Path, *, label: str, mode: int = 0o755) -> bool:
    """Create a directory when absent and report whether this call created it."""
    existing_status = validate_directory_target(path, label=label)
    if existing_status is not None:
        return False

    try:
        path.mkdir(mode=mode, parents=True, exist_ok=False)
    except FileExistsError:
        validate_directory_target(path, label=label)
        return False
    except OSError as exc:
        raise SafeFileError(f"无法创建{label}") from exc

    validate_directory_target(path, label=label)
    if os.name != "nt":
        try:
            os.chmod(path, mode)
        except OSError as exc:
            try:
                path.rmdir()
            except OSError:
                pass
            raise SafeFileError(f"无法设置{label}权限") from exc
    return True


def create_empty_regular_file(path: Path, *, label: str, mode: int = 0o644) -> bool:
    """Create an empty file without replacing an existing regular file."""
    if validate_regular_file_target(path, label=label) is not None:
        return False

    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    except FileExistsError:
        validate_regular_file_target(path, label=label)
        return False
    except OSError as exc:
        raise SafeFileError(f"无法创建{label}") from exc

    try:
        os.close(descriptor)
        if os.name != "nt":
            os.chmod(path, mode)
    except OSError as exc:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise SafeFileError(f"无法完成{label}创建") from exc
    return True


def create_text_file(
    path: Path,
    content: str,
    *,
    label: str,
    mode: int = 0o644,
) -> bool:
    """Create a UTF-8 text file exclusively, preserving any existing file."""
    if validate_regular_file_target(path, label=label) is not None:
        return False

    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    except FileExistsError:
        validate_regular_file_target(path, label=label)
        return False
    except OSError as exc:
        raise SafeFileError(f"无法创建{label}") from exc

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        if os.name != "nt":
            os.chmod(path, mode)
    except (OSError, UnicodeError) as exc:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise SafeFileError(f"无法写入{label}") from exc
    return True


def atomic_write_text(
    path: Path,
    content: str,
    *,
    label: str,
    mode: int = 0o644,
) -> None:
    """Atomically replace a regular UTF-8 text file using a sibling temp file."""
    validate_regular_file_target(path, label=label)
    validate_directory_target(path.parent, label=f"{label}所在目录")

    descriptor = -1
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
            descriptor = -1
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        if os.name != "nt":
            os.chmod(temporary_path, mode)

        validate_regular_file_target(path, label=label)
        os.replace(temporary_path, path)
        temporary_path = None
        if os.name != "nt":
            os.chmod(path, mode)
    except (OSError, UnicodeError) as exc:
        raise SafeFileError(f"无法写入{label}") from exc
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
