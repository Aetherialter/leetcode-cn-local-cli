import json
import math
from dataclasses import dataclass
from time import monotonic, sleep
from urllib.parse import urlsplit

import httpx
from websockets.exceptions import InvalidStatus, WebSocketException
from websockets.sync.client import ClientConnection, connect

from leetcode_local_cli.models.session import REQUIRED_COOKIE_NAMES

LC_DOMAIN = "leetcode.cn"

LEETCODE_COOKIE_URL = "https://leetcode.cn/"
DEVTOOLS_TIMEOUT_SECONDS = 2.0
DEVTOOLS_MAX_MESSAGES = 16
DEVTOOLS_REQUEST_ID = 1
DEVTOOLS_BROWSER_VERSION_REQUEST_ID = 101
DEVTOOLS_TARGETS_REQUEST_ID = 102
DEVTOOLS_ATTACH_REQUEST_ID = 103
DEVTOOLS_COOKIE_REQUEST_ID = 104
DEVTOOLS_COOKIE_POLL_INTERVAL_SECONDS = 0.5


class DevToolsError(ConnectionError):
    """An explicitly authorized local browser DevTools connection failed."""


class DevToolsApprovalRejected(DevToolsError):
    """The browser rejected a permission-gated DevTools connection."""


class DevToolsConnectionUnavailable(DevToolsError):
    """The authorized browser endpoint is temporarily unreachable."""


def get_cookies_from_devtools(port: int) -> dict[str, str]:
    """Read only LeetCode's required cookies from an authorized local CDP port.

    The caller must explicitly provide the debugging port.  This function never
    scans ports, reads browser profile files, or sends the DevTools request to a
    non-loopback address.
    """
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise DevToolsError("DevTools 端口必须介于 1 到 65535 之间")

    debugger_url = _get_page_debugger_url(port)
    _validate_local_debugger_url(debugger_url, port)
    return _read_devtools_cookies(debugger_url)


def get_cookies_from_browser_endpoint(
    debugger_url: str,
    *,
    expected_port: int,
    expected_browser_prefixes: tuple[str, ...],
    timeout_seconds: float,
) -> dict[str, str]:
    """Read LeetCode cookies through an authorized browser-level CDP endpoint.

    Modern browsers expose this endpoint through ``DevToolsActivePort`` after
    explicit user consent.  Unlike a traditional remote-debugging port, its
    HTTP discovery endpoints may return 404, so all discovery happens over the
    supplied browser WebSocket and a flattened target session.
    """
    if (
        not expected_browser_prefixes
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
    ):
        raise DevToolsError("浏览器 DevTools 连接参数无效")
    _validate_local_debugger_url(debugger_url, expected_port)
    deadline = monotonic() + timeout_seconds
    try:
        with connect(
            debugger_url,
            open_timeout=timeout_seconds,
            close_timeout=DEVTOOLS_TIMEOUT_SECONDS,
            compression=None,
            max_size=1_000_000,
            proxy=None,
        ) as connection:
            version_response = _send_devtools_request(
                connection,
                {
                    "id": DEVTOOLS_BROWSER_VERSION_REQUEST_ID,
                    "method": "Browser.getVersion",
                },
                deadline=deadline,
            )
            version_result = _extract_devtools_result(
                version_response,
                invalid_message="浏览器 DevTools 未提供有效身份",
            )
            product = version_result.get("product")
            if not isinstance(product, str) or not product.startswith(
                expected_browser_prefixes
            ):
                raise DevToolsError("DevTools 端点不是请求的浏览器")

            targets_response = _send_devtools_request(
                connection,
                {
                    "id": DEVTOOLS_TARGETS_REQUEST_ID,
                    "method": "Target.getTargets",
                },
                deadline=deadline,
            )
            target_id = _find_leetcode_page_target(targets_response)

            attach_response = _send_devtools_request(
                connection,
                {
                    "id": DEVTOOLS_ATTACH_REQUEST_ID,
                    "method": "Target.attachToTarget",
                    "params": {"targetId": target_id, "flatten": True},
                },
                deadline=deadline,
            )
            attach_result = _extract_devtools_result(
                attach_response,
                invalid_message="浏览器 DevTools 无法连接 LeetCode 页面",
            )
            received_session_id = attach_result.get("sessionId")
            if not isinstance(received_session_id, str) or not received_session_id:
                raise DevToolsError("浏览器 DevTools 未提供有效页面会话")
            session_id = received_session_id

            request_id = DEVTOOLS_COOKIE_REQUEST_ID
            while monotonic() < deadline:
                cookie_response = _send_devtools_request(
                    connection,
                    {
                        "id": request_id,
                        "sessionId": session_id,
                        "method": "Network.getCookies",
                        "params": {"urls": [LEETCODE_COOKIE_URL]},
                    },
                    deadline=deadline,
                )
                cookies = _extract_optional_leetcode_cookies(cookie_response)
                if cookies is not None:
                    return cookies
                remaining = deadline - monotonic()
                if remaining <= 0:
                    break
                sleep(min(DEVTOOLS_COOKIE_POLL_INTERVAL_SECONDS, remaining))
                request_id += 1

            raise DevToolsError("浏览器中未找到有效的 LeetCode 登录 Cookie")
    except DevToolsError:
        raise
    except InvalidStatus as exc:
        if exc.response.status_code == 403:
            raise DevToolsApprovalRejected(
                "浏览器拒绝调试连接；请保持一个可见浏览器窗口并在确认框中选择允许"
            ) from exc
        raise DevToolsConnectionUnavailable("无法连接已授权的浏览器 DevTools") from exc
    except (OSError, TimeoutError, WebSocketException, ValueError) as exc:
        raise DevToolsConnectionUnavailable("无法连接已授权的浏览器 DevTools") from exc


def _get_page_debugger_url(port: int) -> str:
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}",
            timeout=DEVTOOLS_TIMEOUT_SECONDS,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response = client.get("/json/list")
            response.raise_for_status()
            payload = response.json()
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
        raise DevToolsError(
            "无法连接浏览器 DevTools；请确认已显式开启本机调试权限"
        ) from exc

    if not isinstance(payload, list):
        raise DevToolsError("浏览器 DevTools 返回了无效响应")
    for target in payload:
        if not isinstance(target, dict) or target.get("type") != "page":
            continue
        debugger_url = target.get("webSocketDebuggerUrl")
        if isinstance(debugger_url, str) and debugger_url:
            return debugger_url
    raise DevToolsError("浏览器 DevTools 中没有可用页面；请先打开一个浏览器标签页")


@dataclass(frozen=True)
class DevToolsBrowserInfo:
    browser: str
    debugger_url: str


def get_devtools_browser_info(port: int) -> DevToolsBrowserInfo:
    """Return validated identity and endpoint data for a local browser."""
    info = _get_browser_debugger_info(port)
    _validate_local_debugger_url(info.debugger_url, port)
    return info


def _get_browser_debugger_info(port: int) -> DevToolsBrowserInfo:
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}",
            timeout=DEVTOOLS_TIMEOUT_SECONDS,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response = client.get("/json/version")
            response.raise_for_status()
            payload = response.json()
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
        raise DevToolsError("无法连接浏览器 DevTools") from exc

    if not isinstance(payload, dict):
        raise DevToolsError("浏览器 DevTools 返回了无效响应")
    browser = payload.get("Browser")
    debugger_url = payload.get("webSocketDebuggerUrl")
    if (
        not isinstance(browser, str)
        or not browser
        or not isinstance(debugger_url, str)
        or not debugger_url
    ):
        raise DevToolsError("浏览器 DevTools 未提供有效身份或控制端点")
    return DevToolsBrowserInfo(browser=browser, debugger_url=debugger_url)


def _validate_local_debugger_url(debugger_url: str, expected_port: int) -> None:
    try:
        parsed = urlsplit(debugger_url)
        port = parsed.port
    except ValueError as exc:
        raise DevToolsError("浏览器 DevTools 返回了无效 WebSocket 地址") from exc

    if (
        parsed.scheme != "ws"
        or parsed.hostname not in {"127.0.0.1", "::1"}
        or port != expected_port
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise DevToolsError("浏览器 DevTools 地址不属于已授权的本机端口")


def _read_devtools_cookies(debugger_url: str) -> dict[str, str]:
    request = {
        "id": DEVTOOLS_REQUEST_ID,
        "method": "Network.getCookies",
        "params": {"urls": [LEETCODE_COOKIE_URL]},
    }
    deadline = monotonic() + DEVTOOLS_TIMEOUT_SECONDS
    try:
        with connect(
            debugger_url,
            open_timeout=DEVTOOLS_TIMEOUT_SECONDS,
            close_timeout=DEVTOOLS_TIMEOUT_SECONDS,
            compression=None,
            max_size=1_000_000,
            proxy=None,
        ) as connection:
            connection.send(json.dumps(request))
            for _ in range(DEVTOOLS_MAX_MESSAGES):
                remaining = deadline - monotonic()
                if remaining <= 0:
                    break
                message = connection.recv(timeout=remaining)
                response = _parse_chrome_devtools_message(message)
                if response.get("id") == DEVTOOLS_REQUEST_ID:
                    return _extract_leetcode_cookies(response)
    except DevToolsError:
        raise
    except (OSError, TimeoutError, WebSocketException, ValueError) as exc:
        raise DevToolsError("无法从浏览器 DevTools 读取 Cookie") from exc

    raise DevToolsError("浏览器 DevTools 未在限定时间内返回 Cookie")


def _send_devtools_request(
    connection: ClientConnection,
    request: dict[str, object],
    *,
    deadline: float,
) -> dict[str, object]:
    request_id = request.get("id")
    if not isinstance(request_id, int):
        raise DevToolsError("浏览器 DevTools 请求缺少有效标识")
    connection.send(json.dumps(request))
    for _ in range(DEVTOOLS_MAX_MESSAGES):
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        message = connection.recv(timeout=remaining)
        response = _parse_chrome_devtools_message(message)
        if response.get("id") == request_id:
            return response
    raise DevToolsError("浏览器 DevTools 未在限定时间内返回结果")


def _extract_devtools_result(
    response: dict[str, object],
    *,
    invalid_message: str,
) -> dict[str, object]:
    if "error" in response:
        raise DevToolsError(invalid_message)
    result = response.get("result")
    if not isinstance(result, dict):
        raise DevToolsError(invalid_message)
    return result


def _find_leetcode_page_target(response: dict[str, object]) -> str:
    result = _extract_devtools_result(
        response,
        invalid_message="浏览器 DevTools 未提供有效页面列表",
    )
    targets = result.get("targetInfos")
    if not isinstance(targets, list):
        raise DevToolsError("浏览器 DevTools 未提供有效页面列表")
    for target in targets:
        if not isinstance(target, dict) or target.get("type") != "page":
            continue
        target_id = target.get("targetId")
        target_url = target.get("url")
        if not isinstance(target_id, str) or not isinstance(target_url, str):
            continue
        try:
            hostname = urlsplit(target_url).hostname
        except ValueError:
            continue
        if hostname and _cookie_domain_matches(hostname, LC_DOMAIN):
            return target_id
    raise DevToolsError("浏览器 DevTools 中没有 LeetCode 页面")


def _parse_chrome_devtools_message(message: str | bytes) -> dict[str, object]:
    if isinstance(message, bytes):
        message = message.decode("utf-8")
    try:
        payload = json.loads(message)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DevToolsError("浏览器 DevTools 返回了无效消息") from exc
    if not isinstance(payload, dict):
        raise DevToolsError("浏览器 DevTools 返回了无效消息")
    return payload


def _extract_leetcode_cookies(response: dict[str, object]) -> dict[str, str]:
    cookies = _extract_optional_leetcode_cookies(response)
    if cookies is None:
        raise DevToolsError("浏览器中未找到有效的 LeetCode 登录 Cookie")
    return cookies


def _extract_optional_leetcode_cookies(
    response: dict[str, object],
) -> dict[str, str] | None:
    if "error" in response:
        raise DevToolsError("浏览器 DevTools 拒绝读取 Cookie")
    result = response.get("result")
    if not isinstance(result, dict):
        raise DevToolsError("浏览器 DevTools 返回了无效 Cookie 数据")
    cookies = result.get("cookies")
    if not isinstance(cookies, list):
        raise DevToolsError("浏览器 DevTools 返回了无效 Cookie 数据")

    cookies_by_name: dict[str, str] = {}
    for cookie in cookies:
        if not isinstance(cookie, dict):
            continue
        name = cookie.get("name")
        value = cookie.get("value")
        domain = cookie.get("domain")
        if (
            name in REQUIRED_COOKIE_NAMES
            and isinstance(value, str)
            and value
            and isinstance(domain, str)
            and _cookie_domain_matches(domain, LC_DOMAIN)
        ):
            cookies_by_name[name] = value

    if not all(name in cookies_by_name for name in REQUIRED_COOKIE_NAMES):
        return None
    return {name: cookies_by_name[name] for name in REQUIRED_COOKIE_NAMES}


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
