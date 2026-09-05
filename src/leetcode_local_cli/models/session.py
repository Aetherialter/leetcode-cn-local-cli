from dataclasses import dataclass, field
from enum import Enum

REQUIRED_COOKIE_NAMES = ("LEETCODE_SESSION", "csrftoken")


class SessionErrorKind(str, Enum):
    MISSING = "missing"
    READ_ERROR = "read_error"
    INVALID_ENCODING = "invalid_encoding"
    INVALID_JSON = "invalid_json"
    INVALID_STRUCTURE = "invalid_structure"
    MISSING_COOKIES = "missing_cookies"
    WRITE_ERROR = "write_error"


class SessionFileError(OSError):
    def __init__(
        self, kind: SessionErrorKind, *, missing_cookie_names: tuple[str, ...] = ()
    ) -> None:
        super().__init__(kind.value)
        self.kind = kind
        self.missing_cookie_names = missing_cookie_names


@dataclass(frozen=True)
class Credentials:
    session: str = field(repr=False)
    csrf: str = field(repr=False)

    def as_cookies(self) -> dict[str, str]:
        return dict(zip(REQUIRED_COOKIE_NAMES, (self.session, self.csrf), strict=True))


@dataclass(frozen=True)
class Session:
    credentials: Credentials = field(repr=False)
    username: str | None = None
    source: str | None = None
