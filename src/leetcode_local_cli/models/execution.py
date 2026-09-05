from dataclasses import dataclass
from enum import Enum


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
    arguments_after_text: str | None = None
    arguments_after_is_json: bool = False
