from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

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


class ClientErrorKind(str, Enum):
    NETWORK = "network"
    HTTP = "http"
    INVALID_JSON = "invalid_json"
    INVALID_RESPONSE = "invalid_response"
    UNAUTHORIZED = "unauthorized"
    MISSING_CSRF = "missing_csrf"


@dataclass(frozen=True)
class ClientResult:
    data: Any = None
    error: ClientErrorKind | None = None
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.error is None


class LeetCodeClient:
    def __init__(self, cookies: dict[str, str] | None = None):
        self.client = httpx.Client(
            base_url=BASE_URL,
            follow_redirects=True,
            timeout=20.0,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json, text/plain, */*",
                "Origin": BASE_URL,
                "Referer": f"{BASE_URL}/",
            },
        )
        if cookies:
            self.client.cookies.update(cookies)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        timeout: float,
        **kwargs: Any,
    ) -> ClientResult:
        try:
            response = self.client.request(
                method,
                path,
                timeout=timeout,
                **kwargs,
            )
            response.raise_for_status()
        except httpx.RequestError:
            return ClientResult(error=ClientErrorKind.NETWORK)
        except httpx.HTTPStatusError:
            return ClientResult(error=ClientErrorKind.HTTP)

        try:
            result = response.json()
        except ValueError:
            return ClientResult(error=ClientErrorKind.INVALID_JSON)
        if not isinstance(result, dict):
            return ClientResult(error=ClientErrorKind.INVALID_RESPONSE)
        return ClientResult(data=result)

    def user_status(self) -> ClientResult:
        result = self._request_json(
            "POST",
            "/graphql/",
            json=USER_STATUS_QUERY,
            timeout=10,
        )
        if not result.ok:
            return result
        payload = result.data
        assert isinstance(payload, dict)
        data = payload.get("data")
        if not isinstance(data, dict):
            return ClientResult(error=ClientErrorKind.INVALID_RESPONSE)
        status = data.get("userStatus")
        if not isinstance(status, dict):
            return ClientResult(error=ClientErrorKind.INVALID_RESPONSE)
        is_signed_in = status.get("isSignedIn")
        username = status.get("username")
        if not isinstance(is_signed_in, bool) or (
            is_signed_in and (not isinstance(username, str) or not username)
        ):
            return ClientResult(error=ClientErrorKind.INVALID_RESPONSE)
        return ClientResult(data=status)

    def problem_stats(self) -> ClientResult:
        result = self._request_json("GET", "/api/problems/all/", timeout=20)
        if not result.ok:
            return result
        payload = result.data
        assert isinstance(payload, dict)

        stats = {
            "solved": {
                "All": 0,
                "Easy": 0,
                "Medium": 0,
                "Hard": 0,
            },
            "total": {
                "All": 0,
                "Easy": 0,
                "Medium": 0,
                "Hard": 0,
            },
        }
        items = payload.get("stat_status_pairs")
        if not isinstance(items, list):
            return ClientResult(
                error=ClientErrorKind.INVALID_RESPONSE,
                message="stat_status_pairs is not a list",
            )
        for item in items:
            if not isinstance(item, dict):
                return ClientResult(error=ClientErrorKind.INVALID_RESPONSE)
            difficulty_data = item.get("difficulty")
            if not isinstance(difficulty_data, dict):
                return ClientResult(error=ClientErrorKind.INVALID_RESPONSE)
            difficulty_level = difficulty_data.get("level")
            difficulty = (
                DIFFICULTY_MAP.get(difficulty_level)
                if isinstance(difficulty_level, int)
                else None
            )

            if not difficulty:
                continue

            stats["total"]["All"] += 1
            stats["total"][difficulty] += 1

            if item.get("status") == "ac":
                stats["solved"]["All"] += 1
                stats["solved"][difficulty] += 1

        return ClientResult(data=stats)

    def account_profile(self) -> ClientResult:
        status_result = self.user_status()
        if not status_result.ok:
            return status_result
        status = status_result.data
        problem_profile_result = self.problem_stats()
        if not problem_profile_result.ok:
            return problem_profile_result
        problem_profile = problem_profile_result.data
        if not isinstance(status, dict):
            return ClientResult(error=ClientErrorKind.INVALID_RESPONSE)
        if not status.get("isSignedIn"):
            return ClientResult(error=ClientErrorKind.UNAUTHORIZED)
        if not isinstance(problem_profile, dict):
            return ClientResult(
                error=ClientErrorKind.INVALID_RESPONSE,
                message="problem stats is not a dict",
            )
        return ClientResult(
            data={
                "username": status.get("username"),
                "real_name": status.get("realName"),
                "avatar": status.get("avatar"),
                "is_premium": status.get("isPremium"),
                "solved": problem_profile.get("solved"),
                "total": problem_profile.get("total"),
            }
        )

    def problem_list(self, limit: int = 50, skip: int = 0) -> ClientResult:
        payload = {
            "operationName": "problemsetQuestionList",
            "query": PROBLEM_LIST_QUERY,
            "variables": {
                "categorySlug": "",
                "limit": limit,
                "skip": skip,
                "filters": {},
            },
        }
        result = self._request_json(
            "POST",
            "/graphql/",
            json=payload,
            timeout=10,
        )
        if not result.ok:
            return result
        response_payload = result.data
        assert isinstance(response_payload, dict)
        data = response_payload.get("data")
        if not isinstance(data, dict):
            return ClientResult(error=ClientErrorKind.INVALID_RESPONSE)
        problem_list = data.get("problemsetQuestionList")
        if not isinstance(problem_list, dict):
            return ClientResult(error=ClientErrorKind.INVALID_RESPONSE)
        questions = problem_list.get("questions")
        total = problem_list.get("total")
        if (
            not isinstance(questions, list)
            or not all(isinstance(item, dict) for item in questions)
            or not isinstance(total, int)
        ):
            return ClientResult(error=ClientErrorKind.INVALID_RESPONSE)
        return ClientResult(data=problem_list)

    def problem_detail(self, title_slug: str) -> ClientResult:
        payload = {
            "operationName": "questionData",
            "query": QUESTION_DETAIL_QUERY,
            "variables": {
                "titleSlug": title_slug,
            },
        }
        result = self._request_json(
            "POST",
            "/graphql/",
            json=payload,
            timeout=10,
        )
        if not result.ok:
            return result
        response_payload = result.data
        assert isinstance(response_payload, dict)
        data = response_payload.get("data")
        if not isinstance(data, dict):
            return ClientResult(error=ClientErrorKind.INVALID_RESPONSE)
        question = data.get("question")
        if not isinstance(question, dict):
            return ClientResult(error=ClientErrorKind.INVALID_RESPONSE)
        return ClientResult(data=question)

    def submit_solution(
        self, title_slug: str, question_id: str, code: str
    ) -> ClientResult:
        payload = {
            "lang": "python3",
            "question_id": question_id,
            "typed_code": code,
        }
        csrftoken = self.client.cookies.get("csrftoken")
        if not csrftoken:
            return ClientResult(error=ClientErrorKind.MISSING_CSRF)
        result = self._request_json(
            "POST",
            f"/problems/{title_slug}/submit/",
            json=payload,
            headers={
                "X-CSRFToken": csrftoken,
                "Referer": f"{BASE_URL}/problems/{title_slug}/",
            },
            timeout=10,
        )
        if not result.ok:
            return result
        response_payload = result.data
        assert isinstance(response_payload, dict)
        submission_id = response_payload.get("submission_id")
        if not isinstance(submission_id, int) or isinstance(submission_id, bool):
            return ClientResult(error=ClientErrorKind.INVALID_RESPONSE)
        return ClientResult(data=submission_id)

    def get_submission_result(self, submission_id: int) -> ClientResult:
        result = self._request_json(
            "GET",
            f"/submissions/detail/{submission_id}/check/",
            timeout=10,
        )
        if not result.ok:
            return result
        payload = result.data
        assert isinstance(payload, dict)
        if not isinstance(payload.get("state"), str):
            return ClientResult(error=ClientErrorKind.INVALID_RESPONSE)
        return result

    def close(self) -> None:
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
