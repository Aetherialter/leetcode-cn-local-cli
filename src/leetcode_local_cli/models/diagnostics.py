from dataclasses import dataclass
from enum import Enum


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
