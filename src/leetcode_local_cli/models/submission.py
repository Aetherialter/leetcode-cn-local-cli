from __future__ import annotations

from dataclasses import dataclass

from leetcode_local_cli.models.result import ClientErrorKind

PENDING_SUBMISSION_STATES = frozenset({"PENDING", "STARTED"})


@dataclass(frozen=True)
class SubmissionCheck:
    state: str
    status_message: str | None = None
    runtime: str | None = None
    memory: str | None = None
    total_correct: int | None = None
    total_testcases: int | None = None

    @property
    def pending(self) -> bool:
        return self.state in PENDING_SUBMISSION_STATES


@dataclass(frozen=True)
class SubmissionJudged:
    submission_id: int
    status_message: str
    runtime: str | None = None
    memory: str | None = None
    total_correct: int | None = None
    total_testcases: int | None = None

    @property
    def accepted(self) -> bool:
        return self.status_message == "Accepted"


@dataclass(frozen=True)
class SubmissionTimedOut:
    submission_id: int
    waited_seconds: float


@dataclass(frozen=True)
class SubmissionPending:
    submission_id: int


@dataclass(frozen=True)
class SubmissionPollingFailed:
    submission_id: int
    error_kind: ClientErrorKind
    message: str


type SubmissionOutcome = (
    SubmissionJudged | SubmissionTimedOut | SubmissionPending | SubmissionPollingFailed
)
