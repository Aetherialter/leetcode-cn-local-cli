from enum import Enum


class ErrorCode(str, Enum):
    WORKSPACE_CONFIG = "workspace_config"
    SESSION_MISSING = "session_missing"
    SESSION_INVALID = "session_invalid"
    SESSION_IO = "session_io"
    CLIENT = "client_error"
    INVALID_INPUT = "invalid_input"
    SOLUTION = "solution_error"


class UseCaseError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: ErrorCode = ErrorCode.INVALID_INPUT,
        suggestion: str | None = None,
        warning_only: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.suggestion = suggestion
        self.warning_only = warning_only
