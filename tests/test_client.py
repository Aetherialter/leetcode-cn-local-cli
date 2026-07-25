import httpx
import pytest

from leetcode_local_cli.client import (
    BASE_URL,
    ClientErrorKind,
    ClientResult,
    LeetCodeClient,
)


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
