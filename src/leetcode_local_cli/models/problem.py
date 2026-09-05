from dataclasses import dataclass
from enum import Enum


class QuestionIdError(str, Enum):
    EMPTY = "empty"
    NOT_DECIMAL = "not_decimal"
    NOT_POSITIVE = "not_positive"
    LEADING_ZERO = "leading_zero"


QUESTION_ID_ERROR_MESSAGES = {
    QuestionIdError.EMPTY: "题号不能为空",
    QuestionIdError.NOT_DECIMAL: "题号必须是正整数",
    QuestionIdError.NOT_POSITIVE: "题号必须大于 0",
    QuestionIdError.LEADING_ZERO: "题号不能以 0 开头",
}


@dataclass(frozen=True)
class ParseQuestionIdResult:
    question_id: str | None = None
    error: QuestionIdError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def error_message(self) -> str | None:
        if self.error is None:
            return None
        return QUESTION_ID_ERROR_MESSAGES[self.error]


@dataclass(frozen=True)
class ProblemSummary:
    question_id: str
    title: str
    title_slug: str
    difficulty: str
    paid_only: bool
    tags: tuple[str, ...]


@dataclass(frozen=True)
class ProblemDetail:
    question_id: str
    submit_question_id: str
    title: str
    title_slug: str
    difficulty: str
    tags: tuple[str, ...]
    content_html: str
    python_code: str | None


def parse_question_id(raw: str) -> ParseQuestionIdResult:
    text = raw.strip()

    if not text:
        return ParseQuestionIdResult(error=QuestionIdError.EMPTY)

    if not text.isdecimal():
        return ParseQuestionIdResult(error=QuestionIdError.NOT_DECIMAL)

    if text == "0":
        return ParseQuestionIdResult(error=QuestionIdError.NOT_POSITIVE)

    if text.startswith("0"):
        return ParseQuestionIdResult(error=QuestionIdError.LEADING_ZERO)

    return ParseQuestionIdResult(question_id=text)


def find_problem_by_id(
    problems: tuple[ProblemSummary, ...], question_id: str
) -> ProblemSummary | None:
    for problem in problems:
        if question_id == problem.question_id:
            return problem
    return None


@dataclass(frozen=True)
class ProblemPage:
    questions: tuple[ProblemSummary, ...]
    total: int
