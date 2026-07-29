import json
import os
import warnings
from dataclasses import dataclass
from enum import Enum
from getpass import getpass
from pathlib import Path

from leetcode_local_cli.safe_files import (
    SafeFileError,
    atomic_write_text,
    ensure_regular_directory,
    validate_regular_file_target,
)


with warnings.catch_warnings():
    # wmi 1.5.1, imported transitively by browser-cookie3 on Windows, contains
    # invalid escape sequences in docstrings. Keep those third-party warnings
    # out of every CLI invocation without disabling SyntaxWarning globally.
    warnings.filterwarnings(
        "ignore",
        message=r".*invalid escape sequence.*",
        category=SyntaxWarning,
    )
    import browser_cookie3

LC_DOMAIN = "leetcode.cn"
# BROWSER_LOADERS = [("Edge", browser_cookie3.edge), ("Chrome", browser_cookie3.chrome)]
BROWSER_LOADERS = [("Chrome", browser_cookie3.chrome)]

REQUIRED_COOKIE_NAMES = ("LEETCODE_SESSION", "csrftoken")


class SessionFileStatus(str, Enum):
    VALID = "valid"
    MISSING = "missing"
    INVALID_JSON = "invalid_json"
    INVALID_STRUCTURE = "invalid_structure"
    MISSING_COOKIES = "missing_cookies"
    READ_ERROR = "read_error"


@dataclass(frozen=True)
class SessionFileInspection:
    status: SessionFileStatus
    missing_cookie_names: tuple[str, ...] = ()
    username: str | None = None
    source: str | None = None


class SessionFileError(OSError):
    pass


def get_cookies_from_browser() -> tuple[str, dict[str, str]] | None:
    for browser_name, loader in BROWSER_LOADERS:
        try:
            cookie_jar = loader(domain_name=LC_DOMAIN)

        except (browser_cookie3.BrowserCookieError, OSError, RuntimeError):
            continue

        cookies_dict: dict[str, str] = {
            cookie.name: cookie.value
            for cookie in cookie_jar
            if (
                cookie.domain
                and _cookie_domain_matches(cookie.domain, LC_DOMAIN)
                and cookie.value is not None
            )
        }
        if all(name in cookies_dict for name in REQUIRED_COOKIE_NAMES):
            return browser_name, {
                "LEETCODE_SESSION": cookies_dict["LEETCODE_SESSION"],
                "csrftoken": cookies_dict["csrftoken"],
            }

    return None


def _cookie_domain_matches(domain: str, expected_domain: str) -> bool:
    normalized_domain = domain.removeprefix(".").lower()
    normalized_expected_domain = expected_domain.lower()
    return (
        normalized_domain == normalized_expected_domain
        or normalized_domain.endswith(f".{normalized_expected_domain}")
    )


def parse_cookie_header(cookies: str) -> dict[str, str] | None:
    cookies_dict = {}
    for item in cookies.split(";"):
        if "=" in item:
            key, val = item.strip().split("=", 1)
            cookies_dict[key] = val

    if all(name in cookies_dict for name in REQUIRED_COOKIE_NAMES):
        return {
            "LEETCODE_SESSION": cookies_dict["LEETCODE_SESSION"],
            "csrftoken": cookies_dict["csrftoken"],
        }

    return None


def get_cookies_from_input() -> dict[str, str] | None:
    return parse_cookie_header(getpass("请粘贴 Cookie（输入内容不会回显）：\n"))


def save_session(session_data: dict, path: Path) -> None:
    try:
        content = json.dumps(session_data, indent=4, ensure_ascii=False)
        ensure_regular_directory(
            path.parent,
            label="Session 目录",
            mode=0o700,
        )
        if os.name != "nt":
            os.chmod(path.parent, 0o700)
        atomic_write_text(
            path,
            content,
            label="Session 文件",
            mode=0o600,
        )
    except (OSError, TypeError, ValueError) as exc:
        raise SessionFileError("无法保存 Session 文件") from exc


def load_session(path: Path) -> dict | None:
    try:
        if validate_regular_file_target(path, label="Session 文件") is None:
            return None
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None
    except (OSError, SafeFileError) as exc:
        raise SessionFileError("无法读取 Session 文件") from exc


def inspect_session_file(path: Path) -> SessionFileInspection:
    try:
        if validate_regular_file_target(path, label="Session 文件") is None:
            return SessionFileInspection(status=SessionFileStatus.MISSING)
        content = path.read_text(encoding="utf-8")

    except FileNotFoundError:
        return SessionFileInspection(
            status=SessionFileStatus.MISSING,
        )

    except (OSError, SafeFileError):
        return SessionFileInspection(
            status=SessionFileStatus.READ_ERROR,
        )

    try:
        data = json.loads(content)

    except json.JSONDecodeError:
        return SessionFileInspection(
            status=SessionFileStatus.INVALID_JSON,
        )

    if not isinstance(data, dict):
        return SessionFileInspection(
            status=SessionFileStatus.INVALID_STRUCTURE,
        )

    cookies = data.get("cookies")

    if not isinstance(cookies, dict):
        return SessionFileInspection(
            status=SessionFileStatus.INVALID_STRUCTURE,
        )

    missing_cookie_names: list[str] = []

    for cookie_name in REQUIRED_COOKIE_NAMES:
        cookie_value = cookies.get(cookie_name)

        if not isinstance(cookie_value, str) or cookie_value == "":
            missing_cookie_names.append(cookie_name)

    if missing_cookie_names:
        return SessionFileInspection(
            status=SessionFileStatus.MISSING_COOKIES,
            missing_cookie_names=tuple(missing_cookie_names),
        )

    username, source = data.get("username"), data.get("source")

    if not isinstance(username, str):
        username = None

    if not isinstance(source, str):
        source = None

    return SessionFileInspection(
        status=SessionFileStatus.VALID, username=username, source=source
    )
