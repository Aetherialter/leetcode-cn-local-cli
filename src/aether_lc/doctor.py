from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from aether_lc.auth import SessionFileStatus, inspect_session_file


SESSION_CHECK_NAME = "session"


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
                message=f"Session 文件有效（用户：{username}，来源：{source}）",
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
