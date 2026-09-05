import json
import os
from pathlib import Path

from leetcode_local_cli.models.session import (
    REQUIRED_COOKIE_NAMES,
    Credentials,
    Session,
    SessionErrorKind,
    SessionFileError,
)
from leetcode_local_cli.storage.safe_files import (
    atomic_write_text,
    ensure_regular_directory,
    validate_directory_target,
    validate_regular_file_target,
)


def credentials_from_mapping(value: object) -> Credentials:
    if not isinstance(value, dict):
        raise SessionFileError(SessionErrorKind.INVALID_STRUCTURE)
    missing = tuple(
        name for name in REQUIRED_COOKIE_NAMES if not _valid_cookie(value.get(name))
    )
    if missing:
        raise SessionFileError(
            SessionErrorKind.MISSING_COOKIES, missing_cookie_names=missing
        )
    return Credentials(value["LEETCODE_SESSION"], value["csrftoken"])


def _valid_cookie(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and all(0x21 <= ord(ch) <= 0x7E and ch != ";" for ch in value)
    )


def load_session(path: Path) -> Session:
    try:
        validate_directory_target(path.parent, label="Session 目录")
        if validate_regular_file_target(path, label="Session 文件") is None:
            raise SessionFileError(SessionErrorKind.MISSING)
        content = path.read_text(encoding="utf-8")
    except SessionFileError:
        raise
    except FileNotFoundError:
        raise SessionFileError(SessionErrorKind.MISSING) from None
    except UnicodeError:
        raise SessionFileError(SessionErrorKind.INVALID_ENCODING) from None
    except OSError:
        raise SessionFileError(SessionErrorKind.READ_ERROR) from None
    try:
        data = json.loads(content)
    except ValueError:
        raise SessionFileError(SessionErrorKind.INVALID_JSON) from None
    if not isinstance(data, dict) or data.get("site", "leetcode.cn") != "leetcode.cn":
        raise SessionFileError(SessionErrorKind.INVALID_STRUCTURE)
    return Session(
        credentials=credentials_from_mapping(data.get("cookies")),
        username=data.get("username")
        if isinstance(data.get("username"), str)
        else None,
        source=data.get("source") if isinstance(data.get("source"), str) else None,
    )


def save_session(session: Session, path: Path) -> None:
    credentials_from_mapping(session.credentials.as_cookies())
    content = json.dumps(
        {
            "site": "leetcode.cn",
            "username": session.username,
            "source": session.source,
            "cookies": session.credentials.as_cookies(),
        },
        indent=4,
        ensure_ascii=False,
    )
    try:
        ensure_regular_directory(path.parent, label="Session 目录", mode=0o700)
        if os.name != "nt":
            os.chmod(path.parent, 0o700)
        atomic_write_text(path, content, label="Session 文件", mode=0o600)
    except (OSError, UnicodeError):
        raise SessionFileError(SessionErrorKind.WRITE_ERROR) from None
