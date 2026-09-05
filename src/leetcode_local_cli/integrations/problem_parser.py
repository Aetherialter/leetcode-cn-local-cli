from leetcode_local_cli.models.problem import ProblemDetail, ProblemSummary


def normalize_problem_summary(raw: dict[str, object]) -> ProblemSummary:
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
        tags=tuple(tags),
    )


def normalize_problem_summaries(
    raw_items: list[dict[str, object]],
) -> list[ProblemSummary]:
    summaries = [normalize_problem_summary(raw) for raw in raw_items]
    return summaries


def extract_python_code(code_snippets: object) -> str | None:
    if not isinstance(code_snippets, list):
        return None
    for snippet in code_snippets:
        if not isinstance(snippet, dict):
            continue
        if snippet.get("langSlug") == "python3":
            code = snippet.get("code")
            return code if isinstance(code, str) else None

    return None


def normalize_problem_detail(raw: dict[str, object]) -> ProblemDetail:
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
        tags=tuple(tags),
        content_html=text("translatedContent") or text("content"),
        python_code=extract_python_code(raw.get("codeSnippets")),
    )
