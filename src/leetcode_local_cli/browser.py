from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

from leetcode_local_cli.auth import get_devtools_browser_info
from leetcode_local_cli.paths import (
    get_chrome_devtools_active_port_file,
    get_edge_devtools_active_port_file,
)
from leetcode_local_cli.safe_files import (
    SafeFileError,
    validate_directory_target,
    validate_regular_file_target,
)


LEETCODE_URL = "https://leetcode.cn/"
BROWSER_LOGIN_TIMEOUT_SECONDS = 180.0
DEVTOOLS_ACTIVE_PORT_MAX_BYTES = 4096


class BrowserKind(str, Enum):
    AUTO = "auto"
    CHROME = "chrome"
    EDGE = "edge"


class BrowserError(RuntimeError):
    """A browser login source could not be accessed safely."""


class BrowserAuthorizationPending(BrowserError):
    """The browser instance has not exposed a DevTools endpoint yet."""


@dataclass(frozen=True)
class BrowserDevToolsEndpoint:
    """An authorized browser-level endpoint published by a local browser."""

    port: int
    debugger_url: str


@dataclass(frozen=True)
class _BrowserDefinition:
    display_name: str
    session_source: str
    remote_debugging_url: str
    identity_prefixes: tuple[str, ...]


_BROWSER_DEFINITIONS = {
    BrowserKind.CHROME: _BrowserDefinition(
        display_name="Google Chrome",
        session_source="Chrome DevTools",
        remote_debugging_url="chrome://inspect/#remote-debugging",
        identity_prefixes=("Chrome/",),
    ),
    BrowserKind.EDGE: _BrowserDefinition(
        display_name="Microsoft Edge",
        session_source="Edge DevTools",
        remote_debugging_url="edge://inspect/#remote-debugging",
        identity_prefixes=("Edg/",),
    ),
}


def get_browser_display_name(browser: BrowserKind) -> str:
    return _get_browser_definition(browser).display_name


def get_browser_session_source(browser: BrowserKind) -> str:
    return _get_browser_definition(browser).session_source


def get_browser_remote_debugging_url(browser: BrowserKind) -> str:
    return _get_browser_definition(browser).remote_debugging_url


def get_browser_identity_prefixes(browser: BrowserKind) -> tuple[str, ...]:
    return _get_browser_definition(browser).identity_prefixes


def find_chrome_executable(
    *,
    environment: Mapping[str, str] | None = None,
    home: Path | None = None,
    platform: str | None = None,
    os_name: str | None = None,
) -> Path:
    """Find a locally installed Google Chrome Stable executable."""
    active_environment = os.environ if environment is None else environment
    active_home = Path.home() if home is None else home
    active_platform = sys.platform if platform is None else platform
    active_os_name = os.name if os_name is None else os_name

    candidates: list[Path] = []
    if active_os_name == "nt":
        for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base_directory = active_environment.get(variable)
            if base_directory:
                candidates.append(
                    Path(base_directory)
                    / "Google"
                    / "Chrome"
                    / "Application"
                    / "chrome.exe"
                )
    elif active_platform == "darwin":
        candidates.extend(
            [
                Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                active_home
                / "Applications"
                / "Google Chrome.app"
                / "Contents"
                / "MacOS"
                / "Google Chrome",
            ]
        )
    else:
        for command in ("google-chrome", "google-chrome-stable"):
            executable = shutil.which(command)
            if executable:
                candidates.append(Path(executable))

    return _first_existing_executable(candidates, browser_name="Google Chrome")


def find_edge_executable(
    *,
    environment: Mapping[str, str] | None = None,
    home: Path | None = None,
    platform: str | None = None,
    os_name: str | None = None,
) -> Path:
    """Find a locally installed Microsoft Edge Stable executable."""
    active_environment = os.environ if environment is None else environment
    active_home = Path.home() if home is None else home
    active_platform = sys.platform if platform is None else platform
    active_os_name = os.name if os_name is None else os_name

    candidates: list[Path] = []
    if active_os_name == "nt":
        for variable in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
            base_directory = active_environment.get(variable)
            if base_directory:
                candidates.append(
                    Path(base_directory)
                    / "Microsoft"
                    / "Edge"
                    / "Application"
                    / "msedge.exe"
                )
    elif active_platform == "darwin":
        candidates.extend(
            [
                Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
                active_home
                / "Applications"
                / "Microsoft Edge.app"
                / "Contents"
                / "MacOS"
                / "Microsoft Edge",
            ]
        )
    else:
        for command in ("microsoft-edge", "microsoft-edge-stable"):
            executable = shutil.which(command)
            if executable:
                candidates.append(Path(executable))

    return _first_existing_executable(candidates, browser_name="Microsoft Edge")


def open_browser_authorization_pages(
    browser: BrowserKind,
    *,
    executable: Path | None = None,
) -> None:
    """Open a visible daily-browser window without owning its lifecycle."""
    definition = _get_browser_definition(browser)
    active_executable = (
        _find_browser_executable(browser) if executable is None else executable
    )
    try:
        subprocess.Popen(
            [
                str(active_executable),
                "--new-window",
                definition.remote_debugging_url,
                LEETCODE_URL,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise BrowserError(f"无法打开 {definition.display_name}") from exc


def read_browser_devtools_endpoint(
    browser: BrowserKind,
    *,
    port_file: Path | None = None,
) -> BrowserDevToolsEndpoint:
    """Read an explicitly authorized daily-browser endpoint safely."""
    definition = _get_browser_definition(browser)
    active_port_file = (
        _get_browser_devtools_active_port_file(browser)
        if port_file is None
        else Path(os.path.abspath(os.fspath(port_file)))
    )
    try:
        validate_directory_target(
            active_port_file.parent,
            label=f"{definition.display_name} 用户数据目录",
        )
        status = validate_regular_file_target(
            active_port_file,
            label=f"{definition.display_name} DevToolsActivePort",
        )
        if status is None:
            raise BrowserAuthorizationPending(
                f"{definition.display_name} 尚未授权当前实例调试"
            )
        if status.st_size > DEVTOOLS_ACTIVE_PORT_MAX_BYTES:
            raise BrowserError(f"{definition.display_name} DevToolsActivePort 内容过大")
        content = active_port_file.read_text(encoding="utf-8")
    except BrowserAuthorizationPending:
        raise
    except SafeFileError as exc:
        raise BrowserError(str(exc)) from exc
    except FileNotFoundError as exc:
        raise BrowserAuthorizationPending(
            f"{definition.display_name} 尚未授权当前实例调试"
        ) from exc
    except (OSError, UnicodeError) as exc:
        raise BrowserError(f"无法读取 {definition.display_name} 调试授权") from exc

    lines = content.splitlines()
    if len(lines) < 2 or not lines[0].isdigit():
        raise BrowserError(f"{definition.display_name} DevToolsActivePort 内容无效")
    port = int(lines[0])
    _validate_port(port)
    control_path = lines[1]
    parsed_control_path = urlsplit(control_path)
    if (
        not control_path.startswith("/devtools/browser/")
        or parsed_control_path.scheme
        or parsed_control_path.netloc
        or parsed_control_path.query
        or parsed_control_path.fragment
        or parsed_control_path.path != control_path
        or "\\" in control_path
        or any(
            ord(character) <= 0x20 or ord(character) == 0x7F
            for character in control_path
        )
    ):
        raise BrowserError(f"{definition.display_name} DevToolsActivePort 控制端点无效")
    return BrowserDevToolsEndpoint(
        port=port,
        debugger_url=f"ws://127.0.0.1:{port}{control_path}",
    )


def validate_devtools_browser(port: int, browser: BrowserKind) -> None:
    """Ensure a traditional local endpoint belongs to the requested browser."""
    definition = _get_browser_definition(browser)
    browser_name = get_devtools_browser_info(port).browser
    if not browser_name.startswith(definition.identity_prefixes):
        raise BrowserError(f"DevTools 端点不是 {definition.display_name}")


def _get_browser_definition(browser: BrowserKind) -> _BrowserDefinition:
    if browser is BrowserKind.AUTO:
        raise BrowserError("自动模式不能表示单个浏览器")
    return _BROWSER_DEFINITIONS[browser]


def _find_browser_executable(browser: BrowserKind) -> Path:
    if browser is BrowserKind.CHROME:
        return find_chrome_executable()
    if browser is BrowserKind.EDGE:
        return find_edge_executable()
    raise BrowserError("自动模式不能查找单个浏览器")


def _get_browser_devtools_active_port_file(browser: BrowserKind) -> Path:
    if browser is BrowserKind.CHROME:
        return get_chrome_devtools_active_port_file()
    if browser is BrowserKind.EDGE:
        return get_edge_devtools_active_port_file()
    raise BrowserError("自动模式不能读取单个浏览器授权")


def _first_existing_executable(
    candidates: list[Path],
    *,
    browser_name: str,
) -> Path:
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise BrowserError(f"未找到可用的 {browser_name} 浏览器")


def _validate_port(port: int) -> None:
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise BrowserError("DevTools 端口必须介于 1 到 65535 之间")
