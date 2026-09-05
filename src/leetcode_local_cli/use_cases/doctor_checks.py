import subprocess
from pathlib import Path

from leetcode_local_cli.execution.worker import run_solution_file
from leetcode_local_cli.models.account import UserStatus
from leetcode_local_cli.models.diagnostics import DoctorCheck, DoctorStatus
from leetcode_local_cli.models.result import (
    ClientErrorKind,
    ClientFailure,
    ClientResult,
)
from leetcode_local_cli.models.session import (
    Session,
    SessionErrorKind,
    SessionFileError,
)
from leetcode_local_cli.models.solution import SolutionFileStatus
from leetcode_local_cli.storage.solution import inspect_solution_file
from leetcode_local_cli.use_cases.common import session_error

SESSION_CHECK_NAME = "session"
CONNECTIVITY_CHECK_NAME = "connectivity"
AUTHENTICATION_CHECK_NAME = "authentication"
WORKSPACE_CHECK_NAME = "workspace"
SOLUTION_CHECK_NAME = "solution"
SOLUTION_RUN_TIMEOUT_SECONDS = 10


def diagnose_session(result: Session | SessionFileError) -> DoctorCheck:
    if isinstance(result, Session):
        return DoctorCheck(
            name=SESSION_CHECK_NAME,
            status=DoctorStatus.PASS,
            message=f"有效（用户：{result.username or '未知'}，来源：{result.source or '未知'}）",
        )
    error = session_error(result)
    suggestions = {
        SessionErrorKind.MISSING: "请执行 lc login 创建登录态",
        SessionErrorKind.READ_ERROR: "请检查文件权限，或重新执行 lc login",
        SessionErrorKind.MISSING_COOKIES: "请执行 lc login 刷新 Cookie",
    }
    return DoctorCheck(
        name=SESSION_CHECK_NAME,
        status=DoctorStatus.FAIL,
        message=error.message,
        suggestion=suggestions.get(result.kind, error.suggestion),
    )


def diagnose_solution(path: Path, *, run_solution: bool = False) -> DoctorCheck:
    """Inspect solution.py and optionally verify it in a subprocess."""
    inspection = inspect_solution_file(path)
    if run_solution and inspection.status in {
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
            message = (
                "solution.py 语法、提交信息与本地运行正常"
                if run_solution
                else "solution.py 语法和提交信息正常"
            )

            return DoctorCheck(
                name=SOLUTION_CHECK_NAME,
                status=DoctorStatus.PASS,
                message=f"{message}（{target}）",
            )

        case SolutionFileStatus.MISSING:
            return DoctorCheck(
                name=SOLUTION_CHECK_NAME,
                status=DoctorStatus.WARNING,
                message="未找到 solution.py",
                suggestion="请执行 lc solve <题号> 创建解题文件",
            )

        case SolutionFileStatus.EMPTY:
            return DoctorCheck(
                name=SOLUTION_CHECK_NAME,
                status=DoctorStatus.WARNING,
                message="solution.py 当前为空",
                suggestion="请执行 lc solve <题号> 生成解题模板",
            )

        case SolutionFileStatus.READ_ERROR:
            return DoctorCheck(
                name=SOLUTION_CHECK_NAME,
                status=DoctorStatus.FAIL,
                message="无法读取 solution.py",
                suggestion="请检查文件权限",
            )

        case SolutionFileStatus.INVALID_ENCODING:
            return DoctorCheck(
                name=SOLUTION_CHECK_NAME,
                status=DoctorStatus.FAIL,
                message=inspection.detail,
                suggestion="请使用编辑器将 solution.py 转换为 UTF-8 编码",
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
                suggestion="请修复语法错误后重新执行 lc doctor",
            )

        case SolutionFileStatus.NOT_SUBMITTABLE:
            return DoctorCheck(
                name=SOLUTION_CHECK_NAME,
                status=DoctorStatus.WARNING,
                message=f"solution.py 可编译，但暂不可提交：{inspection.detail}",
                suggestion="请执行 lc solve <题号> 重新生成标准模板",
            )


def _diagnose_solution_runtime(path: Path) -> DoctorCheck | None:
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
            suggestion="请执行 lc test 定位本地测试错误",
        )
    return None


def diagnose_remote(
    result: ClientResult[UserStatus],
) -> tuple[DoctorCheck, DoctorCheck]:
    """Translate one user-status request into connectivity and auth checks."""
    if isinstance(result, ClientFailure):
        match result.error:
            case ClientErrorKind.TIMEOUT:
                message = "LeetCode 请求超时"
                suggestion = "请稍后重试"
            case ClientErrorKind.REDIRECT | ClientErrorKind.UNSAFE_TARGET:
                message = "已拒绝不安全的请求目标或重定向"
                suggestion = "请检查接口地址或项目更新"
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
                        suggestion="请执行 lc login 刷新登录态",
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
                suggestion="请先解决连接问题后重新执行 lc doctor",
            ),
        )

    status = result.data
    connectivity = DoctorCheck(
        name=CONNECTIVITY_CHECK_NAME,
        status=DoctorStatus.PASS,
        message="LeetCode 中文站接口连接正常",
    )
    if not status.signed_in:
        authentication = DoctorCheck(
            name=AUTHENTICATION_CHECK_NAME,
            status=DoctorStatus.FAIL,
            message="Cookie 无效、已过期或当前未登录",
            suggestion="请执行 lc login 刷新登录态",
        )
    else:
        username = status.username
        username = username if isinstance(username, str) and username else "未知用户"
        authentication = DoctorCheck(
            name=AUTHENTICATION_CHECK_NAME,
            status=DoctorStatus.PASS,
            message=f"Cookie 有效（当前用户：{username}）",
        )
    return connectivity, authentication
