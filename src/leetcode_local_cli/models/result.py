from dataclasses import dataclass
from enum import Enum
from typing import Literal


class ClientErrorKind(str, Enum):
    TIMEOUT = "timeout"
    NETWORK = "network"
    HTTP = "http"
    INVALID_JSON = "invalid_json"
    INVALID_RESPONSE = "invalid_response"
    UNAUTHORIZED = "unauthorized"
    MISSING_CSRF = "missing_csrf"
    UNSAFE_TARGET = "unsafe_target"
    REDIRECT = "redirect"


@dataclass(frozen=True)
class ClientSuccess[T]:
    data: T

    @property
    def ok(self) -> Literal[True]:
        return True

    @property
    def error(self) -> None:
        return None


@dataclass(frozen=True)
class ClientFailure:
    error: ClientErrorKind
    status_code: int | None = None
    retry_after_seconds: float | None = None

    @property
    def ok(self) -> Literal[False]:
        return False

    @property
    def data(self) -> None:
        return None


type ClientResult[T] = ClientSuccess[T] | ClientFailure
