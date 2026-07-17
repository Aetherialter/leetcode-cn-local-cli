import pytest

from aether_lc.problem import (
    QuestionIdError,
    normalize_problem_detail,
    parse_question_id,
)


@pytest.mark.parametrize(
    ("raw", "expected_error"),
    [
        ("", QuestionIdError.EMPTY),
        ("abc", QuestionIdError.NOT_DECIMAL),
        ("0", QuestionIdError.NOT_POSITIVE),
        ("01", QuestionIdError.LEADING_ZERO),
    ],
)
def test_parse_question_id_rejects_invalid_values(raw, expected_error) -> None:
    result = parse_question_id(raw)

    assert result.error is expected_error


def test_parse_question_id_normalizes_whitespace() -> None:
    result = parse_question_id(" 2196 ")

    assert result.ok
    assert result.question_id == "2196"


def test_normalize_problem_detail_keeps_frontend_and_submit_question_ids() -> None:
    detail = normalize_problem_detail(
        {
            "questionId": "2265",
            "questionFrontendId": "2161",
            "translatedTitle": "根据给定数字划分数组",
            "title": "Partition Array According to Given Pivot",
            "titleSlug": "partition-array-according-to-given-pivot",
            "difficulty": "Medium",
            "translatedContent": "<p>content</p>",
            "content": "",
            "topicTags": [{"name": "Array"}],
            "codeSnippets": [
                {"langSlug": "python3", "code": "class Solution:\n    pass"}
            ],
        }
    )

    assert detail.question_id == "2161"
    assert detail.submit_question_id == "2265"
    assert detail.title_slug == "partition-array-according-to-given-pivot"


def test_normalize_problem_detail_tolerates_malformed_optional_lists() -> None:
    detail = normalize_problem_detail(
        {
            "questionFrontendId": "1",
            "questionId": "1",
            "title": "Two Sum",
            "topicTags": None,
            "codeSnippets": None,
        }
    )

    assert detail.tags == []
    assert detail.python_code is None
