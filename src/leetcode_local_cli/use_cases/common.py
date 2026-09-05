from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext

from leetcode_local_cli.models.result import ClientErrorKind
from leetcode_local_cli.models.session import SessionErrorKind, SessionFileError
from leetcode_local_cli.storage.paths import UserPaths
from leetcode_local_cli.storage.session import load_session
from leetcode_local_cli.use_cases.errors import ErrorCode, UseCaseError

Progress = Callable[[str], AbstractContextManager[None]]


def no_progress(message: str) -> AbstractContextManager[None]:
    del message
    return nullcontext()


def client_error_message(kind: ClientErrorKind | None) -> str:
    match kind:
        case ClientErrorKind.REDIRECT:
            return "LeetCode 接口返回重定向，已停止请求，请检查项目更新"
        case ClientErrorKind.UNSAFE_TARGET:
            return "请求目标不属于允许的 LeetCode HTTPS 地址，已拒绝发送"
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


def session_error(exc: SessionFileError) -> UseCaseError:
    messages = {
        SessionErrorKind.MISSING: "未找到 Session 文件",
        SessionErrorKind.READ_ERROR: "无法读取 Session 文件",
        SessionErrorKind.INVALID_ENCODING: "Session 文件不是有效的 UTF-8 编码",
        SessionErrorKind.INVALID_JSON: "Session 文件不是有效的 JSON",
        SessionErrorKind.INVALID_STRUCTURE: "Session 文件结构无效",
        SessionErrorKind.WRITE_ERROR: "无法保存 Session 文件",
    }
    message = messages.get(exc.kind)
    if message is None:
        message = "缺少或无效的 Cookie：" + "、".join(exc.missing_cookie_names)
    code = ErrorCode.SESSION_INVALID
    if exc.kind is SessionErrorKind.MISSING:
        code = ErrorCode.SESSION_MISSING
    elif exc.kind in {SessionErrorKind.READ_ERROR, SessionErrorKind.WRITE_ERROR}:
        code = ErrorCode.SESSION_IO
    return UseCaseError(message, code=code, suggestion="请执行 lc login 重新生成登录态")


def load_cookies_from_session(paths: UserPaths) -> dict[str, str]:
    try:
        return load_session(paths.session_file).credentials.as_cookies()
    except SessionFileError as exc:
        raise session_error(exc) from None
