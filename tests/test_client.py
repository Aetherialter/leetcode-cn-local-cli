import httpx
import pytest

from leetcode_local_cli.integrations.leetcode import LeetCodeClient
from leetcode_local_cli.models.account import UserStatus
from leetcode_local_cli.models.result import ClientErrorKind, ClientSuccess
from leetcode_local_cli.models.submission import SubmissionCheck


def _client_with_transport(handler, cookies=None) -> LeetCodeClient:
    return LeetCodeClient(cookies, transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    ("response", "expected_error"),
    [
        (httpx.Response(503, json={"error": "unavailable"}), ClientErrorKind.HTTP),
        (httpx.Response(200, text="not-json"), ClientErrorKind.INVALID_JSON),
        (httpx.Response(200, json=[]), ClientErrorKind.INVALID_RESPONSE),
        (httpx.Response(200, json={"data": None}), ClientErrorKind.INVALID_RESPONSE),
        (
            httpx.Response(200, json={"data": {"userStatus": None}}),
            ClientErrorKind.INVALID_RESPONSE,
        ),
    ],
)
def test_user_status_classifies_invalid_responses(response, expected_error) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        response.request = request
        return response

    with _client_with_transport(handler) as client:
        result = client.user_status()

    assert result.error is expected_error


def test_user_status_classifies_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    with _client_with_transport(handler) as client:
        result = client.user_status()

    assert result.error is ClientErrorKind.NETWORK


def test_user_status_classifies_timeout_separately() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow response", request=request)

    with _client_with_transport(handler) as client:
        result = client.user_status()

    assert result.error is ClientErrorKind.TIMEOUT


def test_http_error_preserves_status_and_retry_after() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            request=request,
            headers={"Retry-After": "1.5"},
            json={"error": "rate limited"},
        )

    with _client_with_transport(handler) as client:
        result = client.user_status()

    assert result.error is ClientErrorKind.HTTP
    assert result.status_code == 429
    assert result.retry_after_seconds == 1.5


def test_user_status_returns_valid_status_object() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={"data": {"userStatus": {"isSignedIn": False}}},
        )

    with _client_with_transport(handler) as client:
        result = client.user_status()

    assert result.ok
    assert result.data == UserStatus(False)


@pytest.mark.parametrize(
    "status",
    [
        {},
        {"isSignedIn": "yes"},
        {"isSignedIn": True, "username": None},
    ],
)
def test_user_status_rejects_invalid_authentication_fields(status) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={"data": {"userStatus": status}},
        )

    with _client_with_transport(handler) as client:
        result = client.user_status()

    assert result.error is ClientErrorKind.INVALID_RESPONSE


def test_problem_list_returns_immutable_page_and_forwards_pagination() -> None:
    import json

    def handler(request):
        variables = json.loads(request.content)["variables"]
        assert variables["limit"] == 2 and variables["skip"] == 100
        return httpx.Response(
            200,
            json={
                "data": {
                    "problemsetQuestionList": {
                        "total": 101,
                        "questions": [
                            {
                                "frontendQuestionId": "101",
                                "title": "Example",
                                "titleSlug": "example",
                                "difficulty": "Easy",
                                "paidOnly": False,
                                "topicTags": [{"name": "Array"}],
                            }
                        ],
                    }
                }
            },
        )

    with _client_with_transport(handler) as client:
        result = client.problem_list(limit=2, skip=100)
    assert isinstance(result, ClientSuccess)
    assert result.data.total == 101
    assert isinstance(result.data.questions, tuple)
    assert result.data.questions[0].tags == ("Array",)


@pytest.mark.parametrize(
    "problem_list",
    [
        None,
        {"total": "1", "questions": []},
        {"total": 1, "questions": [None]},
    ],
)
def test_problem_list_rejects_invalid_payload(problem_list) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={"data": {"problemsetQuestionList": problem_list}},
        )

    with _client_with_transport(handler) as client:
        result = client.problem_list()

    assert result.error is ClientErrorKind.INVALID_RESPONSE


def test_problem_detail_rejects_missing_question() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={"data": {"question": None}},
        )

    with _client_with_transport(handler) as client:
        result = client.problem_detail("missing")

    assert result.error is ClientErrorKind.INVALID_RESPONSE


def test_problem_stats_rejects_malformed_items() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={"stat_status_pairs": [None]},
        )

    with _client_with_transport(handler) as client:
        result = client.problem_stats()

    assert result.error is ClientErrorKind.INVALID_RESPONSE


def test_submit_solution_rejects_missing_csrf_without_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("request should not be sent")

    with _client_with_transport(handler) as client:
        result = client.submit_solution("two-sum", "1", "class Solution: pass")

    assert result.error is ClientErrorKind.MISSING_CSRF


def test_submission_result_rejects_missing_state() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json={"status_msg": "Accepted"})

    with _client_with_transport(handler) as client:
        result = client.get_submission_result(123)

    assert result.error is ClientErrorKind.INVALID_RESPONSE


def test_submission_result_returns_typed_check_and_forwards_timeout() -> None:
    received_timeout = []

    def handler(request: httpx.Request) -> httpx.Response:
        received_timeout.append(request.extensions["timeout"]["read"])
        return httpx.Response(
            200,
            request=request,
            json={
                "state": "SUCCESS",
                "status_msg": "Accepted",
                "status_runtime": "4 ms",
                "status_memory": "18.2 MB",
                "memory": 18_200_000,
                "total_correct": 63,
                "total_testcases": 63,
            },
        )

    with _client_with_transport(handler) as client:
        result = client.get_submission_result(123, timeout=2.5)

    assert received_timeout == [2.5]
    assert result.data == SubmissionCheck(
        state="SUCCESS",
        status_message="Accepted",
        runtime="4 ms",
        memory="18.2 MB",
        total_correct=63,
        total_testcases=63,
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"state": "SUCCESS", "status_msg": 1},
        {"state": "SUCCESS", "status_runtime": []},
        {"state": "SUCCESS", "status_memory": []},
        {"state": "SUCCESS", "memory": {}},
        {"state": "SUCCESS", "total_correct": True},
        {"state": "SUCCESS", "total_testcases": "63"},
    ],
)
def test_submission_result_rejects_invalid_optional_fields(payload) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json=payload)

    with _client_with_transport(handler) as client:
        result = client.get_submission_result(123)

    assert result.error is ClientErrorKind.INVALID_RESPONSE


@pytest.mark.parametrize(
    ("method_name", "args"),
    [
        ("user_status", ()),
        ("problem_stats", ()),
        ("problem_list", ()),
        ("problem_detail", ("two-sum",)),
        ("submit_solution", ("two-sum", "1", "class Solution: pass")),
        ("get_submission_result", (123,)),
    ],
)
def test_client_methods_reject_non_dict_success_data(
    method_name,
    args,
    monkeypatch,
) -> None:
    with _client_with_transport(
        lambda request: httpx.Response(200, json=[]),
        cookies={"csrftoken": "csrf-value"},
    ) as client:
        result = getattr(client, method_name)(*args)

    assert result.error is ClientErrorKind.INVALID_RESPONSE
