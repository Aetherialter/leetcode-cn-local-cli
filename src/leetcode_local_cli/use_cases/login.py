from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, sleep

from leetcode_local_cli.auth import (
    DevToolsApprovalRejected,
    DevToolsConnectionUnavailable,
    DevToolsError,
    SessionFileError,
    get_cookies_from_browser_endpoint,
    get_cookies_from_devtools,
    save_session,
)
from leetcode_local_cli.browser import (
    BROWSER_LOGIN_TIMEOUT_SECONDS,
    BrowserAuthorizationPending,
    BrowserDevToolsEndpoint,
    BrowserError,
    BrowserKind,
    get_browser_display_name,
    get_browser_identity_prefixes,
    get_browser_remote_debugging_url,
    get_browser_session_source,
    open_browser_authorization_pages,
    read_browser_devtools_endpoint,
    validate_devtools_browser,
)
from leetcode_local_cli.client import ClientErrorKind, LeetCodeClient
from leetcode_local_cli.use_cases.common import UseCaseError, client_error_message


BROWSER_COOKIE_POLL_INTERVAL_SECONDS = 0.5
BROWSER_WINDOW_READY_DELAY_SECONDS = 1.0


@dataclass(frozen=True)
class LoginReporter:
    info: Callable[[str], None]
    warning: Callable[[str], None]
    loading: Callable[[str], AbstractContextManager[None]]


def try_automatic_login(
    browser: BrowserKind,
    session_file: Path,
    *,
    reporter: LoginReporter,
    devtools_port: int | None = None,
) -> bool:
    """Try configured browser paths; False means the CLI should ask manually."""
    if devtools_port is not None:
        return _try_explicit_devtools_login(
            browser,
            devtools_port,
            session_file=session_file,
            reporter=reporter,
        )

    if browser in {BrowserKind.AUTO, BrowserKind.CHROME}:
        if _try_authorized_browser_login(
            BrowserKind.CHROME,
            session_file,
            reporter=reporter,
        ):
            return True
        if browser is BrowserKind.CHROME:
            return False

    if browser in {BrowserKind.AUTO, BrowserKind.EDGE}:
        if _try_authorized_browser_login(
            BrowserKind.EDGE,
            session_file,
            reporter=reporter,
        ):
            return True
    return False


def validate_and_save_login(
    cookies: dict[str, str],
    *,
    source: str,
    session_file: Path,
) -> bool:
    with LeetCodeClient(cookies) as client:
        status_result = client.user_status()
        status = status_result.data
        if not status_result.ok:
            raise UseCaseError(client_error_message(status_result.error))
        if isinstance(status, dict) and status.get("isSignedIn"):
            username = status.get("username")
            if not isinstance(username, str) or not username:
                raise UseCaseError(
                    client_error_message(ClientErrorKind.INVALID_RESPONSE)
                )
            try:
                save_session(
                    {
                        "site": "leetcode.cn",
                        "source": source,
                        "username": username,
                        "cookies": cookies,
                    },
                    session_file,
                )
            except SessionFileError as exc:
                raise UseCaseError(str(exc)) from exc
            return True
        return False


def _try_authorized_browser_login(
    browser: BrowserKind,
    session_file: Path,
    *,
    reporter: LoginReporter,
) -> bool:
    display_name = get_browser_display_name(browser)
    remote_debugging_url = get_browser_remote_debugging_url(browser)
    source = get_browser_session_source(browser)
    reporter.info(
        f"{display_name} 自动登录前，请先打开 {remote_debugging_url}，"
        "勾选 Allow remote debugging for this browser instance"
    )
    try:
        try:
            endpoint = read_browser_devtools_endpoint(browser)
        except BrowserAuthorizationPending:
            open_browser_authorization_pages(browser)
            reporter.info(
                f"已尝试打开 {display_name} 的 Remote debugging 页面和 LeetCode；"
                f"如未显示，请手动打开 {remote_debugging_url}"
            )
            reporter.info(
                "请勾选 Allow remote debugging for this browser instance；"
                f"CLI 最多等待 {BROWSER_LOGIN_TIMEOUT_SECONDS:g} 秒"
            )
            with reporter.loading(f"正在等待 {display_name} 授权和登录状态..."):
                cookies = _wait_for_browser_cookies(browser)
        else:
            reporter.info(
                f"已检测到 {display_name} 调试授权记录；正在检查连接，"
                "如出现确认请选择允许"
            )
            try:
                with reporter.loading(f"正在连接 {display_name} 并读取登录状态..."):
                    cookies = _read_browser_login_cookies(
                        browser,
                        endpoint,
                        timeout_seconds=BROWSER_LOGIN_TIMEOUT_SECONDS,
                    )
            except (DevToolsApprovalRejected, DevToolsConnectionUnavailable) as exc:
                if isinstance(exc, DevToolsApprovalRejected):
                    reporter.warning(
                        f"当前 {display_name} 只有后台进程或拒绝了连接，"
                        "正在打开可见窗口"
                    )
                else:
                    reporter.info(
                        f"{display_name} 当前未运行或授权端点暂不可用，"
                        f"正在自动打开浏览器；请在 {remote_debugging_url} "
                        "确认已勾选 Allow remote debugging for this browser instance"
                    )
                open_browser_authorization_pages(browser)
                reporter.info("如出现 Allow remote debugging? 确认框，请选择 Allow")
                sleep(BROWSER_WINDOW_READY_DELAY_SECONDS)
                with reporter.loading(f"正在等待 {display_name} 确认和登录状态..."):
                    cookies = _wait_for_browser_cookies(browser)
    except (BrowserError, DevToolsError) as exc:
        reporter.warning(f"{display_name} 自动登录失败：{exc}")
        return False

    if validate_and_save_login(
        cookies,
        source=source,
        session_file=session_file,
    ):
        return True
    reporter.warning(f"{display_name} 中的 LeetCode 登录状态无效")
    return False


def _try_explicit_devtools_login(
    browser: BrowserKind,
    port: int,
    *,
    session_file: Path,
    reporter: LoginReporter,
) -> bool:
    display_name = get_browser_display_name(browser)
    source = get_browser_session_source(browser)
    try:
        with reporter.loading(f"正在连接 {display_name} DevTools..."):
            validate_devtools_browser(port, browser)
            cookies = get_cookies_from_devtools(port)
    except (BrowserError, DevToolsError) as exc:
        reporter.warning(f"{display_name} DevTools 登录失败：{exc}")
        return False
    if validate_and_save_login(
        cookies,
        source=source,
        session_file=session_file,
    ):
        return True
    reporter.warning(f"{display_name} 中的 LeetCode 登录状态无效")
    return False


def _wait_for_browser_cookies(browser: BrowserKind) -> dict[str, str]:
    display_name = get_browser_display_name(browser)
    deadline = monotonic() + BROWSER_LOGIN_TIMEOUT_SECONDS
    while monotonic() < deadline:
        try:
            endpoint = read_browser_devtools_endpoint(browser)
        except BrowserAuthorizationPending:
            endpoint = None
        except BrowserError:
            raise
        if endpoint is not None:
            remaining = deadline - monotonic()
            if remaining <= 0:
                break
            try:
                return _read_browser_login_cookies(
                    browser,
                    endpoint,
                    timeout_seconds=remaining,
                )
            except (DevToolsApprovalRejected, DevToolsConnectionUnavailable):
                pass
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        sleep(min(BROWSER_COOKIE_POLL_INTERVAL_SECONDS, remaining))
    raise BrowserError(f"等待 {display_name} 授权或 LeetCode 登录状态超时")


def _read_browser_login_cookies(
    browser: BrowserKind,
    endpoint: BrowserDevToolsEndpoint,
    *,
    timeout_seconds: float,
) -> dict[str, str]:
    return get_cookies_from_browser_endpoint(
        endpoint.debugger_url,
        expected_port=endpoint.port,
        expected_browser_prefixes=get_browser_identity_prefixes(browser),
        timeout_seconds=timeout_seconds,
    )
