from dataclasses import dataclass
from enum import Enum
from typing import Any


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
    tags: list[str]


@dataclass(frozen=True)
class ProblemDetail:
    question_id: str
    submit_question_id: str
    title: str
    title_slug: str
    difficulty: str
    tags: list[str]
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


def normalize_problem_summary(raw: dict[str, Any]) -> ProblemSummary:
    question_id = raw.get("frontendQuestionId", "")
    question_id = str(question_id) if isinstance(question_id, (str, int)) else ""
    title = raw.get("title", "")
    title = title if isinstance(title, str) else ""
    title_slug = raw.get("titleSlug", "")
    title_slug = title_slug if isinstance(title_slug, str) else ""
    difficulty = raw.get("difficulty", "")
    difficulty = difficulty if isinstance(difficulty, str) else ""
    paid_only = bool(raw.get("paidOnly", False))
    raw_tags = raw.get("topicTags")
    tags = (
        [
            name
            for tag in raw_tags
            if isinstance(tag, dict)
            and isinstance((name := tag.get("name")), str)
            and name
        ]
        if isinstance(raw_tags, list)
        else []
    )

    return ProblemSummary(
        question_id=question_id,
        title=title,
        title_slug=title_slug,
        difficulty=difficulty,
        paid_only=paid_only,
        tags=tags,
    )


def normalize_problem_summaries(
    raw_items: list[dict[str, Any]],
) -> list[ProblemSummary]:
    summaries = [normalize_problem_summary(raw) for raw in raw_items]
    return summaries


def find_problem_by_id(
    problems: list[ProblemSummary], question_id: str
) -> ProblemSummary | None:
    for problem in problems:
        if question_id == problem.question_id:
            return problem
    return None


def extract_python_code(code_snippets: Any) -> str | None:
    if not isinstance(code_snippets, list):
        return None
    for snippet in code_snippets:
        if not isinstance(snippet, dict):
            continue
        if snippet.get("langSlug") == "python3":
            code = snippet.get("code")
            return code if isinstance(code, str) else None

    return None


def normalize_problem_detail(raw: dict[str, Any]) -> ProblemDetail:
    raw_tags = raw.get("topicTags")
    tags = (
        [
            name
            for tag in raw_tags
            if isinstance(tag, dict)
            and isinstance((name := tag.get("name")), str)
            and name
        ]
        if isinstance(raw_tags, list)
        else []
    )

    def text(key: str) -> str:
        value = raw.get(key)
        return value if isinstance(value, str) else ""

    return ProblemDetail(
        question_id=text("questionFrontendId"),
        submit_question_id=text("questionId"),
        title=text("translatedTitle") or text("title"),
        title_slug=text("titleSlug"),
        difficulty=text("difficulty"),
        tags=tags,
        content_html=text("translatedContent") or text("content"),
        python_code=extract_python_code(raw.get("codeSnippets")),
    )
