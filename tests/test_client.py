import httpx
import pytest

from leetcode_local_cli.client import (
    BASE_URL,
    ClientErrorKind,
    ClientResult,
    LeetCodeClient,
)
from leetcode_local_cli.submission import SubmissionCheck


def _client_with_transport(handler, cookies=None) -> LeetCodeClient:
    client = LeetCodeClient(cookies)
    client.client.close()
    client.client = httpx.Client(
        base_url=BASE_URL,
        transport=httpx.MockTransport(handler),
        cookies=cookies,
    )
    return client


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
    assert result.data == {"isSignedIn": False}


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
    with LeetCodeClient({"csrftoken": "csrf-value"}) as client:
        monkeypatch.setattr(
            client,
            "_request_json",
            lambda *args, **kwargs: ClientResult(data=None),
        )

        result = getattr(client, method_name)(*args)

    assert result.error is ClientErrorKind.INVALID_RESPONSE
