import httpx
import pytest

from leetcode_local_cli.integrations.leetcode import LeetCodeClient
from leetcode_local_cli.models.result import ClientErrorKind


@pytest.mark.parametrize(
    "location",
    ["https://other.invalid/", "http://leetcode.cn/", "https://leetcode.cn/graphql/"],
)
@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
@pytest.mark.parametrize("submit", [False, True])
def test_redirects_never_forward_credentials_or_repeat_submission(
    location, status, submit
) -> None:
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, headers={"Location": location})

    with LeetCodeClient(
        {"LEETCODE_SESSION": "synthetic-session", "csrftoken": "synthetic-csrf"},
        transport=httpx.MockTransport(handler),
    ) as client:
        result = (
            client.submit_solution("two-sum", "1", "pass")
            if submit
            else client.user_status()
        )
    assert result.error is ClientErrorKind.REDIRECT
    assert len(requests) == 1
    assert requests[0].url.host == "leetcode.cn"
    assert requests[0].url.scheme == "https"


@pytest.mark.parametrize(
    "url",
    [
        "https://other.invalid/",
        "http://leetcode.cn/",
        "https://leetcode.cn:444/",
        "https://user:pass@leetcode.cn/",
        "https://sub.leetcode.cn/",
        "//other.invalid/",
    ],
)
def test_unsafe_target_is_rejected_before_transport(url) -> None:
    def unexpected(request):
        pytest.fail("unsafe target reached transport")

    with LeetCodeClient(transport=httpx.MockTransport(unexpected)) as client:
        result = client._request_json("GET", url, timeout=1)
    assert result.error is ClientErrorKind.UNSAFE_TARGET


def test_cookies_are_secure_host_bound_and_limited_to_required_names() -> None:
    with LeetCodeClient(
        {
            "LEETCODE_SESSION": "synthetic-session",
            "csrftoken": "synthetic-csrf",
            "unrelated": "ignored",
        },
        transport=httpx.MockTransport(lambda request: httpx.Response(200)),
    ) as client:
        cookies = list(client.client.cookies.jar)
        assert {c.name for c in cookies} == {"LEETCODE_SESSION", "csrftoken"}
        assert all(
            c.domain == "leetcode.cn"
            and c.secure
            and not c.domain_specified
            and c.path == "/"
            for c in cookies
        )
        assert (
            "cookie"
            not in client.client.build_request("GET", "http://leetcode.cn/").headers
        )
        assert (
            "cookie"
            not in client.client.build_request("GET", "https://other.invalid/").headers
        )
