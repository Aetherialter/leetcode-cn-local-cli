from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import subprocess

from leetcode_local_cli.auth import SessionFileStatus, inspect_session_file
from leetcode_local_cli.client import ClientErrorKind, ClientResult
from leetcode_local_cli.workspace import (
    SolutionFileStatus,
    inspect_solution_file,
    run_solution_file,
)


SESSION_CHECK_NAME = "session"
CONNECTIVITY_CHECK_NAME = "connectivity"
AUTHENTICATION_CHECK_NAME = "authentication"
SOLUTION_CHECK_NAME = "solution"
SOLUTION_RUN_TIMEOUT_SECONDS = 10


class DoctorStatus(str, Enum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: DoctorStatus
    message: str
    suggestion: str | None = None


@dataclass(frozen=True)
class DoctorReport:
    checks: tuple[DoctorCheck, ...]

    @property
    def ok(self) -> bool:
        """Return whether the report contains no failed checks."""
        return not any(check.status == DoctorStatus.FAIL for check in self.checks)


def diagnose_session(path: Path | None = None) -> DoctorCheck:
    """Translate the local session inspection into a user-facing check.

    The returned check may contain safe metadata and missing cookie names, but
    it must never include cookie values.
    """
    inspection = inspect_session_file(path)
    match inspection.status:
        case SessionFileStatus.VALID:
            username = inspection.username or "未知"
            source = inspection.source or "未知"
            return DoctorCheck(
                name=SESSION_CHECK_NAME,
                status=DoctorStatus.PASS,
                message=f"有效（用户：{username}，来源：{source}）",
            )

        case SessionFileStatus.MISSING:
            return DoctorCheck(
                name=SESSION_CHECK_NAME,
                status=DoctorStatus.FAIL,
                message="未找到 Session 文件",
                suggestion="请执行 uv run lc login 创建登录态",
            )

        case SessionFileStatus.READ_ERROR:
            return DoctorCheck(
                name=SESSION_CHECK_NAME,
                status=DoctorStatus.FAIL,
                message="无法读取 Session 文件",
                suggestion="请检查文件权限，或重新执行 uv run lc login",
            )

        case SessionFileStatus.INVALID_JSON:
            return DoctorCheck(
                name=SESSION_CHECK_NAME,
                status=DoctorStatus.FAIL,
                message="Session 文件不是有效的 JSON",
                suggestion="请执行 uv run lc login 重新生成登录态",
            )

        case SessionFileStatus.INVALID_STRUCTURE:
            return DoctorCheck(
                name=SESSION_CHECK_NAME,
                status=DoctorStatus.FAIL,
                message="Session 文件结构无效",
                suggestion="请执行 uv run lc login 重新生成登录态",
            )

        case SessionFileStatus.MISSING_COOKIES:
            missing = "、".join(inspection.missing_cookie_names)
            return DoctorCheck(
                name=SESSION_CHECK_NAME,
                status=DoctorStatus.FAIL,
                message=f"缺少或无效的 Cookie：{missing}",
                suggestion="请执行 uv run lc login 刷新 Cookie",
            )


def diagnose_solution(path: Path | None = None) -> DoctorCheck:
    """Inspect solution.py and verify its local entry point in a subprocess."""
    inspection = inspect_solution_file(path)
    if inspection.status in {
        SolutionFileStatus.READY,
        SolutionFileStatus.NOT_SUBMITTABLE,
    }:
        runtime_failure = _diagnose_solution_runtime(path)
        if runtime_failure is not None:
            return runtime_failure

    match inspection.status:
        case SolutionFileStatus.READY:
            metadata = inspection.metadata
            target = (
                f"{metadata.problem_id}. {metadata.title}" if metadata else "未知题目"
            )
            return DoctorCheck(
                name=SOLUTION_CHECK_NAME,
                status=DoctorStatus.PASS,
                message=f"solution.py 语法、提交信息与本地运行正常（{target}）",
            )

        case SolutionFileStatus.MISSING:
            return DoctorCheck(
                name=SOLUTION_CHECK_NAME,
                status=DoctorStatus.WARNING,
                message="未找到 solution.py",
                suggestion="请执行 uv run lc solve <题号> 创建解题文件",
            )

        case SolutionFileStatus.EMPTY:
            return DoctorCheck(
                name=SOLUTION_CHECK_NAME,
                status=DoctorStatus.WARNING,
                message="solution.py 当前为空",
                suggestion="请执行 uv run lc solve <题号> 生成解题模板",
            )

        case SolutionFileStatus.READ_ERROR:
            return DoctorCheck(
                name=SOLUTION_CHECK_NAME,
                status=DoctorStatus.FAIL,
                message="无法读取 solution.py",
                suggestion="请检查文件权限",
            )

        case SolutionFileStatus.INVALID_SYNTAX:
            line = (
                f"第 {inspection.syntax_line} 行"
                if inspection.syntax_line
                else "未知行"
            )
            return DoctorCheck(
                name=SOLUTION_CHECK_NAME,
                status=DoctorStatus.FAIL,
                message=f"solution.py 存在 Python 语法错误（{line}）",
                suggestion="请修复语法错误后重新执行 uv run lc doctor",
            )

        case SolutionFileStatus.NOT_SUBMITTABLE:
            return DoctorCheck(
                name=SOLUTION_CHECK_NAME,
                status=DoctorStatus.WARNING,
                message=f"solution.py 可编译，但暂不可提交：{inspection.detail}",
                suggestion="请执行 uv run lc solve <题号> 重新生成标准模板",
            )


def _diagnose_solution_runtime(path: Path | None) -> DoctorCheck | None:
    try:
        result = run_solution_file(
            path,
            timeout=SOLUTION_RUN_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return DoctorCheck(
            name=SOLUTION_CHECK_NAME,
            status=DoctorStatus.FAIL,
            message=f"solution.py 本地运行超时（{SOLUTION_RUN_TIMEOUT_SECONDS} 秒）",
            suggestion="请检查死循环或耗时过长的本地测试",
        )
    except OSError:
        return DoctorCheck(
            name=SOLUTION_CHECK_NAME,
            status=DoctorStatus.FAIL,
            message="无法启动 Python 运行 solution.py",
            suggestion="请检查当前 Python 环境",
        )
    if result.returncode:
        return DoctorCheck(
            name=SOLUTION_CHECK_NAME,
            status=DoctorStatus.FAIL,
            message=f"solution.py 本地运行失败（退出码：{result.returncode}）",
            suggestion="请执行 uv run lc test 定位本地测试错误",
        )
    return None


def diagnose_remote(result: ClientResult) -> tuple[DoctorCheck, DoctorCheck]:
    """Translate one user-status request into connectivity and auth checks."""
    if not result.ok:
        match result.error:
            case ClientErrorKind.NETWORK:
                message = "无法连接 LeetCode 中文站"
                suggestion = "请检查网络连接后重试"
            case ClientErrorKind.HTTP:
                message = "LeetCode 中文站返回异常 HTTP 状态"
                suggestion = "请稍后重试"
            case ClientErrorKind.INVALID_JSON:
                message = "LeetCode 中文站响应无法解析"
                suggestion = "请稍后重试，接口可能暂时异常"
            case ClientErrorKind.INVALID_RESPONSE:
                message = "LeetCode 中文站接口结构异常"
                suggestion = "接口可能已变更，请检查项目更新"
            case ClientErrorKind.UNAUTHORIZED | ClientErrorKind.MISSING_CSRF:
                return (
                    DoctorCheck(
                        name=CONNECTIVITY_CHECK_NAME,
                        status=DoctorStatus.PASS,
                        message="LeetCode 中文站接口可访问",
                    ),
                    DoctorCheck(
                        name=AUTHENTICATION_CHECK_NAME,
                        status=DoctorStatus.FAIL,
                        message="登录凭证无效或不完整",
                        suggestion="请执行 uv run lc login 刷新登录态",
                    ),
                )
            case _:
                message = "LeetCode 中文站诊断发生未知错误"
                suggestion = "请稍后重试"

        return (
            DoctorCheck(
                name=CONNECTIVITY_CHECK_NAME,
                status=DoctorStatus.FAIL,
                message=message,
                suggestion=suggestion,
            ),
            DoctorCheck(
                name=AUTHENTICATION_CHECK_NAME,
                status=DoctorStatus.WARNING,
                message="网络或接口异常，暂时无法验证 Cookie",
                suggestion="请先解决连接问题后重新执行 uv run lc doctor",
            ),
        )

    status = result.data
    if not isinstance(status, dict):
        return diagnose_remote(ClientResult(error=ClientErrorKind.INVALID_RESPONSE))

    connectivity = DoctorCheck(
        name=CONNECTIVITY_CHECK_NAME,
        status=DoctorStatus.PASS,
        message="LeetCode 中文站接口连接正常",
    )
    if not status.get("isSignedIn"):
        authentication = DoctorCheck(
            name=AUTHENTICATION_CHECK_NAME,
            status=DoctorStatus.FAIL,
            message="Cookie 无效、已过期或当前未登录",
            suggestion="请执行 uv run lc login 刷新登录态",
        )
    else:
        username = status.get("username")
        username = username if isinstance(username, str) and username else "未知用户"
        authentication = DoctorCheck(
            name=AUTHENTICATION_CHECK_NAME,
            status=DoctorStatus.PASS,
            message=f"Cookie 有效（当前用户：{username}）",
        )
    return connectivity, authentication
