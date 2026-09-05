from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class ProblemMetadata:
    problem_id: str
    submit_question_id: str
    title: str
    title_slug: str


class WorkspaceError(ValueError):
    pass


class SolutionFileStatus(str, Enum):
    READY = "ready"
    MISSING = "missing"
    EMPTY = "empty"
    READ_ERROR = "read_error"
    INVALID_ENCODING = "invalid_encoding"
    INVALID_SYNTAX = "invalid_syntax"
    NOT_SUBMITTABLE = "not_submittable"


@dataclass(frozen=True)
class SolutionFileInspection:
    status: SolutionFileStatus
    metadata: ProblemMetadata | None = None
    detail: str = ""
    syntax_line: int | None = None
