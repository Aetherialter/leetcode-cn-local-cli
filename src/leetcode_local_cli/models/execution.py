from dataclasses import dataclass
from enum import Enum

from leetcode_local_cli.models.solution import WorkspaceError


class LocalExecutionStartupError(WorkspaceError):
    def __init__(self, message: str, *, error_line: int | None, traceback: str) -> None:
        super().__init__(message)
        self.error_line = error_line
        self.traceback = traceback


class LocalExecutionStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class LocalExecutionEntry:
    method_name: str
    method_signature: str


@dataclass(frozen=True)
class LocalExecutionResult:
    status: LocalExecutionStatus
    result_text: str = ""
    result_is_json: bool = False
    stdout: str = ""
    stderr: str = ""
    error: str = ""
    error_line: int | None = None
    traceback: str = ""
    arguments_after_text: str | None = None
    arguments_after_is_json: bool = False
