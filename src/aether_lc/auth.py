from enum import Enum
from dataclasses import dataclass
import browser_cookie3
from pathlib import Path
import json

LC_DOMAIN = "leetcode.cn"
# BROWSER_LOADERS = [("Edge", browser_cookie3.edge), ("Chrome", browser_cookie3.chrome)]
BROWSER_LOADERS = [("Chrome", browser_cookie3.chrome)]

REQUIRED_COOKIE_NAMES = ("LEETCODE_SESSION", "csrftoken")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SESSION_DIR = PROJECT_ROOT / ".aether_lc"
SESSION_FILE = SESSION_DIR / "session.json"


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


def get_cookies_from_browser() -> tuple[str, dict[str, str]] | None:
    for browser_name, loader in BROWSER_LOADERS:
        try:
            cookie_jar = loader(domain_name=LC_DOMAIN)

        except Exception:
            continue

        cookies_dict: dict[str, str] = {
            cookie.name: cookie.value
            for cookie in cookie_jar
            if (
                cookie.domain
                and cookie.domain.lstrip(".").endswith(LC_DOMAIN)
                and cookie.value is not None
            )
        }
        if all(name in cookies_dict for name in REQUIRED_COOKIE_NAMES):
            return browser_name, {
                "LEETCODE_SESSION": cookies_dict["LEETCODE_SESSION"],
                "csrftoken": cookies_dict["csrftoken"],
            }

    return None


def get_cookies_from_input() -> dict[str, str] | None:
    cookies = input("请输入你的cookies\n")
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


def save_session(session_data: dict) -> None:
    file_path = SESSION_FILE
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=4, ensure_ascii=False)


def load_session() -> dict | None:
    file_path = SESSION_FILE
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def inspect_session_file(path: Path | None = None) -> SessionFileInspection:
    if path is None:
        path = SESSION_FILE

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
