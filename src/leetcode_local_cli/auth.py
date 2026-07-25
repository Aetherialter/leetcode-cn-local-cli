import json
import os
import warnings
from dataclasses import dataclass
from enum import Enum
from getpass import getpass
from pathlib import Path


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
PROJECT_ROOT = Path.cwd()
SESSION_DIR = PROJECT_ROOT / ".leetcode_local_cli"
SESSION_FILE = SESSION_DIR / "session.json"
LEGACY_SESSION_DIR = PROJECT_ROOT / ".aether_lc"
LEGACY_SESSION_FILE = LEGACY_SESSION_DIR / "session.json"


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


def _resolve_default_session_file() -> Path:
    """Move the pre-v0.7 session to the canonical directory when possible."""
    if SESSION_FILE.exists() or not LEGACY_SESSION_FILE.exists():
        return SESSION_FILE

    try:
        SESSION_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(SESSION_DIR, 0o700)
        LEGACY_SESSION_FILE.replace(SESSION_FILE)
        if os.name != "nt":
            os.chmod(SESSION_FILE, 0o600)
        try:
            LEGACY_SESSION_DIR.rmdir()
        except OSError:
            # Preserve a non-empty legacy directory instead of deleting unrelated data.
            pass
    except OSError:
        if SESSION_FILE.exists():
            return SESSION_FILE
        return LEGACY_SESSION_FILE

    return SESSION_FILE


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


def save_session(session_data: dict, path: Path | None = None) -> None:
    if path is None:
        _resolve_default_session_file()
    file_path = path or SESSION_FILE
    temporary_file = file_path.with_suffix(f"{file_path.suffix}.tmp")
    try:
        file_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if path is None and os.name != "nt":
            os.chmod(file_path.parent, 0o700)
        descriptor = os.open(
            temporary_file,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            0o600,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(session_data, file, indent=4, ensure_ascii=False)
        os.chmod(temporary_file, 0o600)
        temporary_file.replace(file_path)
        os.chmod(file_path, 0o600)
    except (OSError, TypeError, ValueError) as exc:
        try:
            temporary_file.unlink(missing_ok=True)
        except OSError:
            pass
        raise SessionFileError("无法保存 Session 文件") from exc


def load_session() -> dict | None:
    file_path = _resolve_default_session_file()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None
    except OSError as exc:
        raise SessionFileError("无法读取 Session 文件") from exc


def inspect_session_file(path: Path | None = None) -> SessionFileInspection:
    if path is None:
        path = _resolve_default_session_file()

    try:
        content = path.read_text(encoding="utf-8")

    except FileNotFoundError:
        return SessionFileInspection(
            status=SessionFileStatus.MISSING,
        )

    except OSError:
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
