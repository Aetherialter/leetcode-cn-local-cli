from dataclasses import dataclass


@dataclass(frozen=True)
class UserStatus:
    signed_in: bool
    username: str | None = None
    real_name: str | None = None
    avatar: str | None = None
    premium: bool = False


@dataclass(frozen=True)
class DifficultyCounts:
    easy: int = 0
    medium: int = 0
    hard: int = 0

    @property
    def total(self) -> int:
        return self.easy + self.medium + self.hard


@dataclass(frozen=True)
class ProblemStats:
    solved: DifficultyCounts
    total: DifficultyCounts


@dataclass(frozen=True)
class AccountProfile:
    user: UserStatus
    stats: ProblemStats
