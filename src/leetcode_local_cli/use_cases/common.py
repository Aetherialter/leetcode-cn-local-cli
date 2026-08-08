from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext

from leetcode_local_cli.auth import (
    REQUIRED_COOKIE_NAMES,
    SessionFileError,
    load_session,
)
from leetcode_local_cli.client import ClientErrorKind
from leetcode_local_cli.doctor import DoctorStatus, diagnose_session
from leetcode_local_cli.paths import AppPaths


Progress = Callable[[str], AbstractContextManager[None]]


class UseCaseError(RuntimeError):
    """A user-actionable application error independent of CLI rendering."""

    def __init__(
        self,
        message: str,
        *,
        suggestion: str | None = None,
        warning_only: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.suggestion = suggestion
        self.warning_only = warning_only


def no_progress(message: str) -> AbstractContextManager[None]:
    del message
    return nullcontext()


def client_error_message(kind: ClientErrorKind | None) -> str:
    match kind:
        case ClientErrorKind.TIMEOUT:
            return "LeetCode 请求超时，请稍后重试"
        case ClientErrorKind.NETWORK:
            return "网络请求失败，请检查网络连接"
        case ClientErrorKind.HTTP:
            return "LeetCode 接口返回异常，请稍后重试"
        case ClientErrorKind.INVALID_JSON:
            return "LeetCode 返回内容无法解析，请稍后重试"
        case ClientErrorKind.INVALID_RESPONSE:
            return "LeetCode 接口数据结构异常，可能是接口变更"
        case ClientErrorKind.UNAUTHORIZED:
            return "登录态无效或已过期，请重新执行 lc login"
        case ClientErrorKind.MISSING_CSRF:
            return "缺少提交凭证 csrftoken，请重新执行 lc login"
        case _:
            return "未知客户端错误"


def load_cookies_from_session(paths: AppPaths) -> dict[str, str]:
    session_check = diagnose_session(paths.session_file)
    if session_check.status is DoctorStatus.FAIL:
        raise UseCaseError(
            session_check.message,
            suggestion=session_check.suggestion,
        )
    try:
        session = load_session(paths.session_file)
    except SessionFileError as exc:
        raise UseCaseError(str(exc)) from exc
    if not isinstance(session, dict):
        raise UseCaseError(
            "未找到有效登录态，请先执行 lc login",
            warning_only=True,
        )
    cookies = session.get("cookies")
    if not isinstance(cookies, dict):
        raise UseCaseError("Session 文件结构无效，请重新执行 lc login")
    valid_cookies: dict[str, str] = {}
    for name in REQUIRED_COOKIE_NAMES:
        value = cookies.get(name)
        if not isinstance(value, str) or not value:
            raise UseCaseError(
                f"缺少或无效的 Cookie：{name}",
                suggestion="请重新执行 lc login",
            )
        valid_cookies[name] = value
    return valid_cookies
