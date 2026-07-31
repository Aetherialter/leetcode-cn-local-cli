import json
import os
import stat

import pytest
from websockets.datastructures import Headers
from websockets.exceptions import InvalidStatus
from websockets.http11 import Response

from leetcode_local_cli import auth
from leetcode_local_cli.auth import SessionFileStatus


def _write_json(path, data) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_inspect_session_file_returns_missing_when_file_does_not_exist(
    tmp_path,
) -> None:
    result = auth.inspect_session_file(tmp_path / "missing-session.json")

    assert result.status is SessionFileStatus.MISSING


def test_inspect_session_file_returns_invalid_json(tmp_path) -> None:
    session_file = tmp_path / "session.json"
    session_file.write_text("{invalid", encoding="utf-8")

    result = auth.inspect_session_file(session_file)

    assert result.status is SessionFileStatus.INVALID_JSON


def test_inspect_session_file_rejects_non_object_root(tmp_path) -> None:
    session_file = tmp_path / "session.json"
    _write_json(session_file, [])

    result = auth.inspect_session_file(session_file)

    assert result.status is SessionFileStatus.INVALID_STRUCTURE


def test_inspect_session_file_rejects_non_object_cookies(tmp_path) -> None:
    session_file = tmp_path / "session.json"
    _write_json(session_file, {"cookies": []})

    result = auth.inspect_session_file(session_file)

    assert result.status is SessionFileStatus.INVALID_STRUCTURE


@pytest.mark.parametrize(
    ("cookies", "expected_missing_names"),
    [
        ({"csrftoken": "csrf-value"}, ("LEETCODE_SESSION",)),
        (
            {"LEETCODE_SESSION": "session-value", "csrftoken": 123},
            ("csrftoken",),
        ),
        (
            {"LEETCODE_SESSION": "", "csrftoken": ""},
            ("LEETCODE_SESSION", "csrftoken"),
        ),
    ],
)
def test_inspect_session_file_reports_missing_or_invalid_cookies(
    tmp_path,
    cookies,
    expected_missing_names,
) -> None:
    session_file = tmp_path / "session.json"
    _write_json(session_file, {"cookies": cookies})

    result = auth.inspect_session_file(session_file)

    assert result.status is SessionFileStatus.MISSING_COOKIES
    assert result.missing_cookie_names == expected_missing_names


def test_inspect_session_file_returns_sanitized_metadata_for_valid_session(
    tmp_path,
) -> None:
    session_file = tmp_path / "session.json"
    _write_json(
        session_file,
        {
            "username": "learner",
            "source": "Chrome",
            "cookies": {
                "LEETCODE_SESSION": "session-value",
                "csrftoken": "csrf-value",
            },
        },
    )

    result = auth.inspect_session_file(session_file)

    assert result.status is SessionFileStatus.VALID
    assert result.username == "learner"
    assert result.source == "Chrome"


def test_inspect_session_file_discards_non_string_metadata(tmp_path) -> None:
    session_file = tmp_path / "session.json"
    _write_json(
        session_file,
        {
            "username": 123,
            "source": ["Chrome"],
            "cookies": {
                "LEETCODE_SESSION": "session-value",
                "csrftoken": "csrf-value",
            },
        },
    )

    result = auth.inspect_session_file(session_file)

    assert result.status is SessionFileStatus.VALID
    assert result.username is None
    assert result.source is None


def test_inspect_session_file_returns_read_error_for_unreadable_path(tmp_path) -> None:
    result = auth.inspect_session_file(tmp_path)

    assert result.status is SessionFileStatus.READ_ERROR


def test_inspection_result_does_not_expose_cookie_values(tmp_path) -> None:
    session_file = tmp_path / "session.json"
    session_value = "private-session-value"
    csrf_value = "private-csrf-value"
    _write_json(
        session_file,
        {
            "cookies": {
                "LEETCODE_SESSION": session_value,
                "csrftoken": csrf_value,
            }
        },
    )

    result = auth.inspect_session_file(session_file)
    result_text = repr(result)

    assert session_value not in result_text
    assert csrf_value not in result_text


def test_load_session_preserves_existing_success_and_failure_contract(
    tmp_path,
) -> None:
    session_dir = tmp_path / ".leetcode_local_cli"
    session_dir.mkdir()
    session_file = session_dir / "session.json"
    session_data = {"cookies": {"LEETCODE_SESSION": "session-value"}}

    _write_json(session_file, session_data)
    assert auth.load_session(session_file) == session_data

    session_file.write_text("{invalid", encoding="utf-8")
    assert auth.load_session(session_file) is None

    session_file.unlink()
    assert auth.load_session(session_file) is None


def test_save_session_writes_atomically_with_private_permissions(tmp_path) -> None:
    session_file = tmp_path / "session.json"
    session_data = {
        "cookies": {
            "LEETCODE_SESSION": "session-value",
            "csrftoken": "csrf-value",
        }
    }

    auth.save_session(session_data, session_file)

    assert json.loads(session_file.read_text(encoding="utf-8")) == session_data
    assert not session_file.with_suffix(".json.tmp").exists()
    if os.name != "nt":
        assert stat.S_IMODE(session_file.stat().st_mode) == 0o600


def test_save_session_creates_private_canonical_directory(tmp_path) -> None:
    session_dir = tmp_path / ".leetcode_local_cli"
    session_file = session_dir / "session.json"
    session_data = {"cookies": {"LEETCODE_SESSION": "session-value"}}

    auth.save_session(session_data, session_file)

    assert (
        json.loads((session_dir / "session.json").read_text(encoding="utf-8"))
        == session_data
    )
    if os.name != "nt":
        assert stat.S_IMODE(session_dir.stat().st_mode) == 0o700


def test_save_session_cleans_temporary_file_after_serialization_error(
    tmp_path,
) -> None:
    session_file = tmp_path / "session.json"

    with pytest.raises(auth.SessionFileError, match="无法保存 Session 文件"):
        auth.save_session({"invalid": object()}, session_file)

    assert not session_file.exists()
    assert not session_file.with_suffix(".json.tmp").exists()


def test_load_session_raises_clear_error_for_unreadable_path(
    tmp_path,
) -> None:
    with pytest.raises(auth.SessionFileError, match="无法读取 Session 文件"):
        auth.load_session(tmp_path)


def test_parse_cookie_header_extracts_required_cookies() -> None:
    result = auth.parse_cookie_header(
        "other=value; LEETCODE_SESSION=session=with=equals; csrftoken=csrf"
    )

    assert result == {
        "LEETCODE_SESSION": "session=with=equals",
        "csrftoken": "csrf",
    }


def test_parse_cookie_header_rejects_missing_required_cookie() -> None:
    assert auth.parse_cookie_header("LEETCODE_SESSION=session") is None


@pytest.mark.parametrize(
    ("domain", "expected"),
    [
        ("leetcode.cn", True),
        (".leetcode.cn", True),
        ("www.leetcode.cn", True),
        ("WWW.LEETCODE.CN", True),
        ("evil-leetcode.cn", False),
        ("notleetcode.cn", False),
        ("leetcode.cn.evil.example", False),
    ],
)
def test_cookie_domain_match_requires_exact_domain_boundary(
    domain,
    expected,
) -> None:
    assert auth._cookie_domain_matches(domain, auth.LC_DOMAIN) is expected


def test_chrome_devtools_loader_reads_only_required_leetcode_cookies(
    monkeypatch,
) -> None:
    messages = iter(
        [
            json.dumps({"method": "Network.loadingFinished"}),
            json.dumps(
                {
                    "id": auth.DEVTOOLS_REQUEST_ID,
                    "result": {
                        "cookies": [
                            {
                                "name": "LEETCODE_SESSION",
                                "value": "session-value",
                                "domain": ".leetcode.cn",
                            },
                            {
                                "name": "csrftoken",
                                "value": "csrf-value",
                                "domain": "leetcode.cn",
                            },
                            {
                                "name": "unrelated",
                                "value": "ignored",
                                "domain": ".leetcode.cn",
                            },
                            {
                                "name": "LEETCODE_SESSION",
                                "value": "wrong-domain",
                                "domain": "evil-leetcode.cn",
                            },
                        ]
                    },
                }
            ),
        ]
    )
    sent_messages = []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def send(self, message):
            sent_messages.append(json.loads(message))

        def recv(self, *, timeout):
            return next(messages)

    received_urls = []
    monkeypatch.setattr(
        auth,
        "_get_page_debugger_url",
        lambda port: "ws://127.0.0.1:9222/devtools/page/example",
    )
    monkeypatch.setattr(
        auth,
        "connect",
        lambda url, **kwargs: received_urls.append((url, kwargs)) or FakeConnection(),
    )

    result = auth.get_cookies_from_devtools(9222)

    assert result == {
        "LEETCODE_SESSION": "session-value",
        "csrftoken": "csrf-value",
    }
    assert sent_messages == [
        {
            "id": auth.DEVTOOLS_REQUEST_ID,
            "method": "Network.getCookies",
            "params": {"urls": ["https://leetcode.cn/"]},
        }
    ]
    assert received_urls[0][0] == "ws://127.0.0.1:9222/devtools/page/example"
    assert received_urls[0][1]["proxy"] is None


def test_browser_endpoint_attaches_to_leetcode_target_and_reads_cookies(
    monkeypatch,
) -> None:
    responses = iter(
        [
            {"id": 101, "result": {"product": "Edg/150.0"}},
            {
                "id": 102,
                "result": {
                    "targetInfos": [
                        {
                            "targetId": "ignored",
                            "type": "page",
                            "url": "https://example.com/",
                        },
                        {
                            "targetId": "leetcode-page",
                            "type": "page",
                            "url": "https://leetcode.cn/problemset/",
                        },
                    ]
                },
            },
            {"id": 103, "result": {"sessionId": "edge-session"}},
            {
                "id": 104,
                "result": {
                    "cookies": [
                        {
                            "name": "LEETCODE_SESSION",
                            "value": "session-value",
                            "domain": ".leetcode.cn",
                        },
                        {
                            "name": "csrftoken",
                            "value": "csrf-value",
                            "domain": "leetcode.cn",
                        },
                    ]
                },
            },
        ]
    )
    sent_messages = []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def send(self, message):
            sent_messages.append(json.loads(message))

        def recv(self, *, timeout):
            return json.dumps(next(responses))

    connections = []
    monkeypatch.setattr(
        auth,
        "connect",
        lambda url, **kwargs: connections.append((url, kwargs)) or FakeConnection(),
    )

    result = auth.get_cookies_from_browser_endpoint(
        "ws://127.0.0.1:9222/devtools/browser/example",
        expected_port=9222,
        expected_browser_prefixes=("Edg/",),
        timeout_seconds=30.0,
    )

    assert result == {
        "LEETCODE_SESSION": "session-value",
        "csrftoken": "csrf-value",
    }
    assert [message["method"] for message in sent_messages] == [
        "Browser.getVersion",
        "Target.getTargets",
        "Target.attachToTarget",
        "Network.getCookies",
    ]
    assert sent_messages[2]["params"] == {
        "targetId": "leetcode-page",
        "flatten": True,
    }
    assert sent_messages[3]["sessionId"] == "edge-session"
    assert sent_messages[3]["params"] == {"urls": ["https://leetcode.cn/"]}
    assert connections[0][0] == "ws://127.0.0.1:9222/devtools/browser/example"
    assert connections[0][1]["open_timeout"] == 30.0
    assert connections[0][1]["proxy"] is None


def test_browser_endpoint_rejects_wrong_browser_before_reading_targets(
    monkeypatch,
) -> None:
    sent_messages = []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def send(self, message):
            sent_messages.append(json.loads(message))

        def recv(self, *, timeout):
            return json.dumps({"id": 101, "result": {"product": "Chrome/150.0"}})

    monkeypatch.setattr(auth, "connect", lambda *args, **kwargs: FakeConnection())

    with pytest.raises(auth.DevToolsError, match="不是请求的浏览器"):
        auth.get_cookies_from_browser_endpoint(
            "ws://127.0.0.1:9222/devtools/browser/example",
            expected_port=9222,
            expected_browser_prefixes=("Edg/",),
            timeout_seconds=30.0,
        )

    assert [message["method"] for message in sent_messages] == ["Browser.getVersion"]


def test_browser_endpoint_rejects_nonlocal_url_before_connecting(monkeypatch) -> None:
    monkeypatch.setattr(
        auth,
        "connect",
        lambda *args, **kwargs: pytest.fail("must not connect to a nonlocal URL"),
    )

    with pytest.raises(auth.DevToolsError, match="不属于已授权的本机端口"):
        auth.get_cookies_from_browser_endpoint(
            "ws://example.com:9222/devtools/browser/example",
            expected_port=9222,
            expected_browser_prefixes=("Edg/",),
            timeout_seconds=30.0,
        )


def test_browser_endpoint_reports_permission_gated_connection_rejection(
    monkeypatch,
) -> None:
    rejection = InvalidStatus(
        Response(
            status_code=403,
            reason_phrase="Forbidden",
            headers=Headers(),
            body=b"Connection rejected",
        )
    )
    monkeypatch.setattr(
        auth,
        "connect",
        lambda *args, **kwargs: (_ for _ in ()).throw(rejection),
    )

    with pytest.raises(auth.DevToolsApprovalRejected, match="可见浏览器窗口"):
        auth.get_cookies_from_browser_endpoint(
            "ws://127.0.0.1:9222/devtools/browser/example",
            expected_port=9222,
            expected_browser_prefixes=("Edg/",),
            timeout_seconds=30.0,
        )


def test_browser_endpoint_classifies_unreachable_endpoint_as_temporary(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        auth,
        "connect",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ConnectionRefusedError("browser is not running")
        ),
    )

    with pytest.raises(
        auth.DevToolsConnectionUnavailable,
        match="无法连接已授权",
    ):
        auth.get_cookies_from_browser_endpoint(
            "ws://127.0.0.1:9222/devtools/browser/example",
            expected_port=9222,
            expected_browser_prefixes=("Chrome/",),
            timeout_seconds=30.0,
        )


def test_browser_endpoint_retries_missing_cookies_on_same_connection(
    monkeypatch,
) -> None:
    responses = iter(
        [
            {"id": 101, "result": {"product": "Edg/150.0"}},
            {
                "id": 102,
                "result": {
                    "targetInfos": [
                        {
                            "targetId": "leetcode-page",
                            "type": "page",
                            "url": "https://leetcode.cn/",
                        }
                    ]
                },
            },
            {"id": 103, "result": {"sessionId": "edge-session"}},
            {"id": 104, "result": {"cookies": []}},
            {
                "id": 105,
                "result": {
                    "cookies": [
                        {
                            "name": "LEETCODE_SESSION",
                            "value": "session-value",
                            "domain": ".leetcode.cn",
                        },
                        {
                            "name": "csrftoken",
                            "value": "csrf-value",
                            "domain": "leetcode.cn",
                        },
                    ]
                },
            },
        ]
    )
    sent_messages = []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def send(self, message):
            sent_messages.append(json.loads(message))

        def recv(self, *, timeout):
            return json.dumps(next(responses))

    monkeypatch.setattr(auth, "connect", lambda *args, **kwargs: FakeConnection())
    monkeypatch.setattr(auth, "sleep", lambda seconds: None)

    result = auth.get_cookies_from_browser_endpoint(
        "ws://127.0.0.1:9222/devtools/browser/example",
        expected_port=9222,
        expected_browser_prefixes=("Edg/",),
        timeout_seconds=30.0,
    )

    assert result["LEETCODE_SESSION"] == "session-value"
    assert [
        message["id"]
        for message in sent_messages
        if message["method"] == "Network.getCookies"
    ] == [104, 105]


def test_chrome_devtools_loader_rejects_nonlocal_websocket_endpoint(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        auth,
        "_get_page_debugger_url",
        lambda port: "ws://example.com:9222/devtools/page/example",
    )
    monkeypatch.setattr(
        auth,
        "connect",
        lambda *args, **kwargs: pytest.fail("must not connect to a nonlocal URL"),
    )

    with pytest.raises(auth.DevToolsError, match="不属于已授权的本机端口"):
        auth.get_cookies_from_devtools(9222)


@pytest.mark.parametrize(
    "debugger_url",
    (
        "ws://127.0.0.1:9333/devtools/page/example",
        "wss://127.0.0.1:9222/devtools/page/example",
        "ws://user@127.0.0.1:9222/devtools/page/example",
    ),
)
def test_chrome_devtools_loader_rejects_endpoint_outside_explicit_authority(
    debugger_url,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        auth,
        "_get_page_debugger_url",
        lambda port: debugger_url,
    )
    monkeypatch.setattr(
        auth,
        "connect",
        lambda *args, **kwargs: pytest.fail("must not connect to rejected endpoint"),
    )

    with pytest.raises(auth.DevToolsError, match="不属于已授权的本机端口"):
        auth.get_cookies_from_devtools(9222)


def test_chrome_devtools_loader_rejects_missing_required_cookies(monkeypatch) -> None:
    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def send(self, message):
            pass

        def recv(self, *, timeout):
            return json.dumps(
                {
                    "id": auth.DEVTOOLS_REQUEST_ID,
                    "result": {"cookies": []},
                }
            )

    monkeypatch.setattr(
        auth,
        "_get_page_debugger_url",
        lambda port: "ws://127.0.0.1:9222/devtools/page/example",
    )
    monkeypatch.setattr(auth, "connect", lambda *args, **kwargs: FakeConnection())

    with pytest.raises(auth.DevToolsError, match="未找到有效的 LeetCode"):
        auth.get_cookies_from_devtools(9222)


def test_chrome_devtools_loader_reports_protocol_error(monkeypatch) -> None:
    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def send(self, message):
            pass

        def recv(self, *, timeout):
            return json.dumps(
                {
                    "id": auth.DEVTOOLS_REQUEST_ID,
                    "error": {"code": -32601, "message": "method unavailable"},
                }
            )

    monkeypatch.setattr(
        auth,
        "_get_page_debugger_url",
        lambda port: "ws://127.0.0.1:9222/devtools/page/example",
    )
    monkeypatch.setattr(auth, "connect", lambda *args, **kwargs: FakeConnection())

    with pytest.raises(auth.DevToolsError, match="拒绝读取 Cookie"):
        auth.get_cookies_from_devtools(9222)


def test_chrome_devtools_http_discovery_is_limited_to_requested_loopback_port(
    monkeypatch,
) -> None:
    received_options = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "type": "service_worker",
                    "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/service/x",
                },
                {
                    "type": "page",
                    "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/x",
                },
            ]

    class FakeClient:
        def __init__(self, **kwargs):
            received_options.append(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def get(self, path):
            assert path == "/json/list"
            return FakeResponse()

    monkeypatch.setattr(auth.httpx, "Client", FakeClient)

    assert auth._get_page_debugger_url(9222).startswith(
        "ws://127.0.0.1:9222/devtools/page/"
    )
    assert received_options == [
        {
            "base_url": "http://127.0.0.1:9222",
            "timeout": auth.DEVTOOLS_TIMEOUT_SECONDS,
            "follow_redirects": False,
            "trust_env": False,
        }
    ]


def test_chrome_devtools_discovery_rejects_missing_page_target(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"type": "service_worker"}]

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def get(self, path):
            return FakeResponse()

    monkeypatch.setattr(auth.httpx, "Client", FakeClient)

    with pytest.raises(auth.DevToolsError, match="没有可用页面"):
        auth._get_page_debugger_url(9222)
