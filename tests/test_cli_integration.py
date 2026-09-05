"""Exercise real path resolution, storage, use cases and CLI with isolated HTTP."""

import json
from functools import partial
from pathlib import Path

import httpx
import pytest
from click import unstyle
from typer.testing import CliRunner

from leetcode_local_cli.cli import app
from leetcode_local_cli.integrations.editor import EditorError
from leetcode_local_cli.integrations.leetcode import LeetCodeClient
from leetcode_local_cli.models.session import Credentials, Session
from leetcode_local_cli.storage.paths import UserPaths
from leetcode_local_cli.storage.session import save_session
from leetcode_local_cli.use_cases import account, diagnostics, problems
from leetcode_local_cli.use_cases.setup import initialize_workspace


@pytest.fixture
def isolated_user(tmp_path, monkeypatch) -> UserPaths:
    for variable in (
        "APPDATA",
        "LOCALAPPDATA",
        "XDG_CONFIG_HOME",
        "XDG_STATE_HOME",
        "HOME",
        "USERPROFILE",
    ):
        directory = tmp_path / variable.lower()
        directory.mkdir()
        monkeypatch.setenv(variable, str(directory))
    monkeypatch.chdir(tmp_path)
    return UserPaths.defaults()


@pytest.fixture
def requests(monkeypatch) -> list[httpx.Request]:
    received: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(request)
        if request.url.path == "/api/problems/all/":
            return httpx.Response(
                200,
                json={
                    "stat_status_pairs": [{"difficulty": {"level": 1}, "status": "ac"}]
                },
            )
        payload = json.loads(request.content)
        if payload.get("operationName") == "problemsetQuestionList":
            data = {
                "problemsetQuestionList": {
                    "total": 1,
                    "questions": [
                        {
                            "frontendQuestionId": "1",
                            "title": "Two Sum",
                            "titleSlug": "two-sum",
                            "difficulty": "Easy",
                            "paidOnly": False,
                            "topicTags": [],
                        }
                    ],
                }
            }
        elif payload.get("operationName") == "questionData":
            data = {
                "question": {
                    "questionId": "1",
                    "questionFrontendId": "1",
                    "title": "Two Sum",
                    "titleSlug": "two-sum",
                    "difficulty": "Easy",
                    "content": "<p>Test problem</p>",
                    "topicTags": [],
                    "codeSnippets": [
                        {
                            "langSlug": "python3",
                            "code": "class Solution:\n    def answer(self):\n        pass",
                        }
                    ],
                }
            }
        else:
            data = {
                "userStatus": {
                    "isSignedIn": bool(request.headers.get("Cookie")),
                    "username": "learner",
                }
            }
        return httpx.Response(200, json={"data": data})

    factory = partial(LeetCodeClient, transport=httpx.MockTransport(handler))
    for module in (account, diagnostics, problems):
        monkeypatch.setattr(module, "LeetCodeClient", factory)
    return received


def test_stdin_without_workspace_uses_json_and_operational_exit(
    isolated_user, requests
) -> None:
    result = CliRunner().invoke(app, ["test", "--stdin"])
    assert result.exit_code == 1
    event = json.loads(result.stdout)
    assert event["kind"] == "startup_error"
    assert event["code"] == "workspace_config"
    assert not requests


def test_stdin_invalid_option_has_usage_exit(isolated_user, requests) -> None:
    result = CliRunner().invoke(app, ["test", "--stdin", "--timeout", "nan"])
    assert result.exit_code == 2
    assert not requests


@pytest.mark.parametrize("command", ["status", "profile", "doctor"])
@pytest.mark.parametrize(
    "content, message",
    [
        (None, "未找到 Session 文件"),
        (b"\xff", "UTF-8"),
        (b"{", "JSON"),
        (b"[]", "结构无效"),
    ],
)
def test_account_commands_share_session_validation(
    isolated_user, requests, command, content, message
) -> None:
    path = isolated_user.session_file
    if content is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    result = CliRunner().invoke(app, [command])
    assert result.exit_code == 1
    assert message in unstyle(result.output)
    assert "Traceback" not in result.output
    assert len(requests) == (1 if command == "doctor" else 0)
    assert all("Cookie" not in request.headers for request in requests)


def test_profile_without_workspace_uses_typed_http_results(
    isolated_user, requests
) -> None:
    save_session(
        Session(Credentials("synthetic-session", "synthetic-csrf")),
        isolated_user.session_file,
    )
    result = CliRunner().invoke(app, ["profile"])
    assert result.exit_code == 0, result.output
    assert "learner" in result.output
    assert len(requests) == 2
    assert not isolated_user.user_config_file.exists()


@pytest.mark.parametrize("no_open", [False, True])
def test_solve_saves_even_when_editor_unavailable(
    isolated_user, requests, tmp_path, monkeypatch, no_open
) -> None:
    workspace = initialize_workspace(
        tmp_path / "workspace", user_config_file=isolated_user.user_config_file
    ).paths
    save_session(
        Session(Credentials("synthetic-session", "synthetic-csrf")),
        isolated_user.session_file,
    )
    opened = []

    def fail_open(path):
        opened.append(path)
        assert path.is_file()
        raise EditorError("editor unavailable")

    monkeypatch.setattr(problems, "open_path", fail_open)
    result = CliRunner().invoke(
        app, ["solve", "1", *(["--no-open"] if no_open else [])]
    )
    assert result.exit_code == 0, result.output
    assert "解法已保存" in unstyle(result.output)
    assert ("editor unavailable" in result.output) is (not no_open)
    assert opened == ([] if no_open else [workspace.solution_file])
    assert "class Solution:" in workspace.solution_file.read_text(encoding="utf-8")
    assert len(requests) == 2


def test_solve_failed_write_preserves_solution_and_never_opens(
    isolated_user, requests, tmp_path, monkeypatch
) -> None:
    from leetcode_local_cli.storage import safe_files

    workspace = initialize_workspace(
        tmp_path / "workspace", user_config_file=isolated_user.user_config_file
    ).paths
    workspace.solution_file.write_bytes(b"original solution")
    save_session(
        Session(Credentials("synthetic-session", "synthetic-csrf")),
        isolated_user.session_file,
    )

    def fail_replace(*args):
        raise PermissionError("synthetic failure")

    monkeypatch.setattr(safe_files.os, "replace", fail_replace)
    monkeypatch.setattr(
        problems,
        "open_path",
        lambda path: pytest.fail("must not open after write failure"),
    )
    result = CliRunner().invoke(app, ["solve", "1"])
    assert result.exit_code == 1
    assert workspace.solution_file.read_bytes() == b"original solution"


def test_init_repair_suggestion_is_actionable(isolated_user, tmp_path) -> None:
    path = isolated_user.user_config_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff")
    failed = CliRunner().invoke(app, ["init"])
    assert failed.exit_code == 1
    assert "--repair" in failed.output
    repaired = CliRunner().invoke(
        app, ["init", str(tmp_path / "workspace"), "--repair", "--yes"]
    )
    assert repaired.exit_code == 0, repaired.output
    assert [backup.read_bytes() for backup in path.parent.glob("*.bak")] == [b"\xff"]


def test_init_repair_requires_explicit_path(isolated_user) -> None:
    result = CliRunner().invoke(app, ["init", "--repair"])
    assert result.exit_code == 2
    assert not isolated_user.user_config_file.exists()


def test_doctor_reads_session_once(isolated_user, requests, monkeypatch) -> None:
    save_session(
        Session(Credentials("synthetic-session", "synthetic-csrf")),
        isolated_user.session_file,
    )
    reads = []
    original_read = Path.read_text

    def counted(path, *args, **kwargs):
        reads.append(path)
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counted)
    report = diagnostics.get_doctor_report(isolated_user)
    assert report.ok
    assert reads == [isolated_user.session_file]
    assert len(requests) == 1
