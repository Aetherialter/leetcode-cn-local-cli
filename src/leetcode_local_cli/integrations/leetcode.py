import math
from collections.abc import Mapping
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http.cookiejar import Cookie

import httpx

from leetcode_local_cli.integrations.problem_parser import (
    normalize_problem_detail,
    normalize_problem_summaries,
)
from leetcode_local_cli.models.account import DifficultyCounts, ProblemStats, UserStatus
from leetcode_local_cli.models.problem import ProblemDetail, ProblemPage
from leetcode_local_cli.models.result import (
    ClientErrorKind,
    ClientFailure,
    ClientResult,
    ClientSuccess,
)
from leetcode_local_cli.models.session import REQUIRED_COOKIE_NAMES
from leetcode_local_cli.models.submission import SubmissionCheck

BASE_URL = "https://leetcode.cn"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/135.0.0.0 Safari/537.36"
)

USER_STATUS_QUERY = {
    "query": """
        query userStatus {
            userStatus {
                isSignedIn
                username
                realName
                avatar
                isPremium
            }
        }
    """
}

DIFFICULTY_MAP = {
    1: "Easy",
    2: "Medium",
    3: "Hard",
}

PROBLEM_LIST_QUERY = """
query problemsetQuestionList(
    $categorySlug: String,
    $limit: Int,
    $skip: Int,
    $filters: QuestionListFilterInput
) {
    problemsetQuestionList(
        categorySlug: $categorySlug,
        limit: $limit,
        skip: $skip,
        filters: $filters
    ) {
        total
        questions {
            frontendQuestionId
            title
            titleSlug
            difficulty
            paidOnly
            topicTags {
                name
                slug
            }
        }
    }
}
"""

QUESTION_DETAIL_QUERY = """
query questionData($titleSlug: String!) {
    question(titleSlug: $titleSlug) {
        questionId
        questionFrontendId
        title
        translatedTitle
        titleSlug
        difficulty
        content
        translatedContent
        topicTags {
            name
            slug
        }
        codeSnippets {
            lang
            langSlug
            code
        }
    }
}
"""


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
    if not math.isfinite(seconds) or seconds < 0:
        return None
    return seconds


class LeetCodeClient:
    def __init__(
        self,
        cookies: Mapping[str, str] | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ):
        self.client = httpx.Client(
            base_url=BASE_URL,
            follow_redirects=False,
            timeout=20.0,
            transport=transport,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json, text/plain, */*",
                "Origin": BASE_URL,
                "Referer": f"{BASE_URL}/",
            },
        )
        for name in REQUIRED_COOKIE_NAMES:
            if cookies and (value := cookies.get(name)):
                self.client.cookies.jar.set_cookie(
                    Cookie(
                        version=0,
                        name=name,
                        value=value,
                        port=None,
                        port_specified=False,
                        domain="leetcode.cn",
                        domain_specified=False,
                        domain_initial_dot=False,
                        path="/",
                        path_specified=True,
                        secure=True,
                        expires=None,
                        discard=True,
                        comment=None,
                        comment_url=None,
                        rest={},
                        rfc2109=False,
                    )
                )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        timeout: float,
        json: object = None,
        headers: Mapping[str, str] | None = None,
    ) -> ClientResult[dict[str, object]]:
        try:
            url = self.client.base_url.join(path)
        except (httpx.InvalidURL, ValueError):
            return ClientFailure(ClientErrorKind.UNSAFE_TARGET)
        if (
            url.scheme != "https"
            or url.host != "leetcode.cn"
            or url.port not in {None, 443}
            or url.username
            or url.password
        ):
            return ClientFailure(ClientErrorKind.UNSAFE_TARGET)
        try:
            response = self.client.request(
                method, url, timeout=timeout, json=json, headers=headers
            )
            if response.is_redirect:
                return ClientFailure(
                    ClientErrorKind.REDIRECT, status_code=response.status_code
                )
            response.raise_for_status()
        except httpx.TimeoutException:
            return ClientFailure(ClientErrorKind.TIMEOUT)
        except (httpx.RequestError, httpx.InvalidURL):
            return ClientFailure(ClientErrorKind.NETWORK)
        except httpx.HTTPStatusError as exc:
            return ClientFailure(
                ClientErrorKind.HTTP,
                status_code=exc.response.status_code,
                retry_after_seconds=_parse_retry_after(
                    exc.response.headers.get("Retry-After")
                ),
            )
        try:
            payload = response.json()
        except ValueError:
            return ClientFailure(ClientErrorKind.INVALID_JSON)
        if not isinstance(payload, dict):
            return ClientFailure(ClientErrorKind.INVALID_RESPONSE)
        return ClientSuccess(payload)

    def _graphql(self, query: object, field: str) -> ClientResult[dict[str, object]]:
        result = self._request_json("POST", "/graphql/", json=query, timeout=10)
        if isinstance(result, ClientFailure):
            return result
        data = result.data.get("data")
        value = data.get(field) if isinstance(data, dict) else None
        if not isinstance(value, dict):
            return ClientFailure(ClientErrorKind.INVALID_RESPONSE)
        return ClientSuccess(value)

    def user_status(self) -> ClientResult[UserStatus]:
        result = self._graphql(USER_STATUS_QUERY, "userStatus")
        if isinstance(result, ClientFailure):
            return result
        status = result.data
        signed_in, username = status.get("isSignedIn"), status.get("username")
        if not isinstance(signed_in, bool) or (
            signed_in and (not isinstance(username, str) or not username)
        ):
            return ClientFailure(ClientErrorKind.INVALID_RESPONSE)
        return ClientSuccess(
            UserStatus(
                signed_in=signed_in,
                username=username if isinstance(username, str) else None,
                real_name=_optional_text(status.get("realName")),
                avatar=_optional_text(status.get("avatar")),
                premium=status.get("isPremium") is True,
            )
        )

    def problem_stats(self) -> ClientResult[ProblemStats]:
        result = self._request_json("GET", "/api/problems/all/", timeout=20)
        if isinstance(result, ClientFailure):
            return result
        items = result.data.get("stat_status_pairs")
        if not isinstance(items, list):
            return ClientFailure(ClientErrorKind.INVALID_RESPONSE)
        solved, total = [0, 0, 0], [0, 0, 0]
        for item in items:
            if not isinstance(item, dict) or not isinstance(
                item.get("difficulty"), dict
            ):
                return ClientFailure(ClientErrorKind.INVALID_RESPONSE)
            level = item["difficulty"].get("level")
            if type(level) is not int or level not in {1, 2, 3}:
                continue
            total[level - 1] += 1
            if item.get("status") == "ac":
                solved[level - 1] += 1
        return ClientSuccess(
            ProblemStats(DifficultyCounts(*solved), DifficultyCounts(*total))
        )

    def problem_list(self, limit: int = 50, skip: int = 0) -> ClientResult[ProblemPage]:
        result = self._graphql(
            {
                "operationName": "problemsetQuestionList",
                "query": PROBLEM_LIST_QUERY,
                "variables": {
                    "categorySlug": "",
                    "limit": limit,
                    "skip": skip,
                    "filters": {},
                },
            },
            "problemsetQuestionList",
        )
        if isinstance(result, ClientFailure):
            return result
        questions, total = result.data.get("questions"), result.data.get("total")
        if (
            not isinstance(questions, list)
            or not all(isinstance(item, dict) for item in questions)
            or type(total) is not int
            or total < 0
        ):
            return ClientFailure(ClientErrorKind.INVALID_RESPONSE)
        return ClientSuccess(
            ProblemPage(tuple(normalize_problem_summaries(questions)), total)
        )

    def problem_detail(self, title_slug: str) -> ClientResult[ProblemDetail]:
        result = self._graphql(
            {
                "operationName": "questionData",
                "query": QUESTION_DETAIL_QUERY,
                "variables": {"titleSlug": title_slug},
            },
            "question",
        )
        if isinstance(result, ClientFailure):
            return result
        return ClientSuccess(normalize_problem_detail(result.data))

    def submit_solution(
        self, title_slug: str, question_id: str, code: str
    ) -> ClientResult[int]:
        csrf = self.client.cookies.get("csrftoken", domain="leetcode.cn", path="/")
        if not csrf:
            return ClientFailure(ClientErrorKind.MISSING_CSRF)
        result = self._request_json(
            "POST",
            f"/problems/{title_slug}/submit/",
            json={"lang": "python3", "question_id": question_id, "typed_code": code},
            headers={
                "X-CSRFToken": csrf,
                "Referer": f"{BASE_URL}/problems/{title_slug}/",
            },
            timeout=10,
        )
        if isinstance(result, ClientFailure):
            return result
        submission_id = result.data.get("submission_id")
        if type(submission_id) is not int or submission_id <= 0:
            return ClientFailure(ClientErrorKind.INVALID_RESPONSE)
        return ClientSuccess(submission_id)

    def get_submission_result(
        self,
        submission_id: int,
        *,
        timeout: float = 10,
    ) -> ClientResult[SubmissionCheck]:
        result = self._request_json(
            "GET",
            f"/submissions/detail/{submission_id}/check/",
            timeout=timeout,
        )
        if isinstance(result, ClientFailure):
            return result
        payload = result.data
        if not isinstance(payload, dict):
            return ClientFailure(error=ClientErrorKind.INVALID_RESPONSE)
        state = payload.get("state")
        if not isinstance(state, str) or not state:
            return ClientFailure(error=ClientErrorKind.INVALID_RESPONSE)
        status_message = payload.get("status_msg")
        if status_message is not None and (
            not isinstance(status_message, str) or not status_message
        ):
            return ClientFailure(error=ClientErrorKind.INVALID_RESPONSE)
        runtime = payload.get("status_runtime")
        if runtime is None:
            runtime = payload.get("runtime")
        if runtime is not None and not isinstance(runtime, str):
            return ClientFailure(error=ClientErrorKind.INVALID_RESPONSE)
        memory = payload.get("status_memory")
        if memory is None:
            memory = payload.get("memory")
        if memory is not None and not isinstance(memory, str):
            return ClientFailure(error=ClientErrorKind.INVALID_RESPONSE)
        total_correct = payload.get("total_correct")
        if total_correct is not None and (
            not isinstance(total_correct, int) or isinstance(total_correct, bool)
        ):
            return ClientFailure(error=ClientErrorKind.INVALID_RESPONSE)
        total_testcases = payload.get("total_testcases")
        if total_testcases is not None and (
            not isinstance(total_testcases, int) or isinstance(total_testcases, bool)
        ):
            return ClientFailure(error=ClientErrorKind.INVALID_RESPONSE)
        return ClientSuccess(
            data=SubmissionCheck(
                state=state,
                status_message=status_message,
                runtime=runtime,
                memory=memory,
                total_correct=total_correct,
                total_testcases=total_testcases,
            )
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "LeetCodeClient":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) else None
