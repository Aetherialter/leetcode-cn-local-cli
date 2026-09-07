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
from leetcode_local_cli.models.editor import EditorConfig
from leetcode_local_cli.models.session import Credentials, Session
from leetcode_local_cli.storage.paths import UserPaths
from leetcode_local_cli.storage.session import save_session
from leetcode_local_cli.use_cases import account, diagnostics, problems
from leetcode_local_cli.use_cases.setup import initialize_workspace
from leetcode_local_cli.use_cases.settings import configure_editor


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

    def fail_open(path, editor):
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


@pytest.mark.parametrize(
    "options, expected",
    [
        ([], EditorConfig("zed", ("--new",))),
        (["--editor", "code"], EditorConfig("code")),
        (["--no-open", "--editor", "invalid/relative"], None),
    ],
)
def test_solve_editor_precedence_never_changes_user_config(
    isolated_user, requests, tmp_path, monkeypatch, options, expected
) -> None:
    initialize_workspace(
        tmp_path / "workspace", user_config_file=isolated_user.user_config_file
    )
    configure_editor(isolated_user, EditorConfig("zed", ("--new",)))
    save_session(
        Session(Credentials("synthetic-session", "synthetic-csrf")),
        isolated_user.session_file,
    )
    original = isolated_user.user_config_file.read_bytes()
    opened = []
    monkeypatch.setattr(
        problems, "open_path", lambda path, editor: opened.append(editor)
    )
    result = CliRunner().invoke(app, ["solve", "1", *options])
    assert result.exit_code == 0, result.output
    assert opened == ([expected] if expected else [])
    assert isolated_user.user_config_file.read_bytes() == original


def test_solve_unconfigured_editor_only_saves(
    isolated_user, requests, tmp_path, monkeypatch
) -> None:
    from leetcode_local_cli.integrations import editor

    workspace = initialize_workspace(
        tmp_path / "workspace", user_config_file=isolated_user.user_config_file
    ).paths
    save_session(
        Session(Credentials("synthetic-session", "synthetic-csrf")),
        isolated_user.session_file,
    )
    monkeypatch.setattr(
        editor.subprocess, "Popen", lambda *a, **k: pytest.fail("no editor configured")
    )
    result = CliRunner().invoke(app, ["solve", "1"])
    assert result.exit_code == 0, result.output
    assert "未配置编辑器" in result.output
    assert "class Solution:" in workspace.solution_file.read_text(encoding="utf-8")


def test_editor_only_config_keeps_account_and_doctor_workspace_independent(
    isolated_user, requests
) -> None:
    configure_editor(isolated_user, EditorConfig("zed"))
    save_session(
        Session(Credentials("synthetic-session", "synthetic-csrf")),
        isolated_user.session_file,
    )
    for command in ("profile", "doctor"):
        result = CliRunner().invoke(app, [command])
        assert result.exit_code == 0, result.output
    result = CliRunner().invoke(app, ["test", "--stdin"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["code"] == "workspace_config"


@pytest.mark.parametrize("verbose", [False, True])
@pytest.mark.parametrize("startup", [False, True])
def test_stdin_error_details_remain_json_and_traceback_is_opt_in(
    isolated_user, tmp_path, verbose, startup
) -> None:
    workspace = initialize_workspace(
        tmp_path / "workspace", user_config_file=isolated_user.user_config_file
    ).paths
    workspace.solution_file.write_text(
        "raise RuntimeError('startup failure')\n"
        if startup
        else "class Solution:\n    def run(self):\n        print('before')\n        return 1 / 0\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        app, ["test", "--stdin", *(["--verbose"] if verbose else [])], input="()\n"
    )
    assert result.exit_code == 1, result.output
    events = [json.loads(line) for line in result.stdout.splitlines()]
    event = events[0]
    assert event["error_line"] == (1 if startup else 4)
    assert ("traceback" in event) is verbose
    if startup:
        assert event["kind"] == "startup_error" and event["code"] == "solution_error"
    else:
        assert event["stdout"] == "before\n"
        assert events[-1]["kind"] == "summary"


@pytest.mark.parametrize("verbose", [False, True])
@pytest.mark.parametrize("stdin", [False, True])
def test_restart_error_after_timeout_keeps_cli_diagnostics(
    isolated_user, tmp_path, monkeypatch, verbose, stdin
) -> None:
    from leetcode_local_cli.execution.worker import LocalExecutionWorker

    workspace = initialize_workspace(
        tmp_path / "workspace", user_config_file=isolated_user.user_config_file
    ).paths
    workspace.solution_file.write_text(
        "from time import sleep\nclass Solution:\n    def run(self):\n        sleep(2)\n",
        encoding="utf-8",
    )
    execute = LocalExecutionWorker.execute
    calls = 0

    def execute_with_edited_source(worker, arguments):
        nonlocal calls
        calls += 1
        if calls == 2:
            workspace.solution_file.write_text(
                "# changed during local testing\nrestart_missing\n", encoding="utf-8"
            )
        return execute(worker, arguments)

    monkeypatch.setattr(LocalExecutionWorker, "execute", execute_with_edited_source)
    result = CliRunner().invoke(
        app,
        ["test", *(["--stdin"] if stdin else []), *(["--verbose"] if verbose else [])],
        input="()\n()\n\n\n",
    )
    assert result.exit_code == 1, result.output
    assert calls == 2
    if stdin:
        events = [json.loads(line) for line in result.stdout.splitlines()]
        assert len(events) == 3
        assert events[0]["ok"] is False and "超过" in events[0]["error"]
        event = events[1]
        assert event["case"] == 2 and event["ok"] is False
        assert "NameError" in event["error"] and event["error_line"] == 2
        assert ("traceback" in event) is verbose
        assert events[-1] == {
            "kind": "summary",
            "total": 2,
            "successful": 0,
            "failed": 2,
        }
    else:
        assert "solution.py:2" in result.output and "NameError" in result.output
        assert ("Traceback" in result.output) is verbose


def test_stdin_tree_conversion_and_in_place_output(isolated_user, tmp_path) -> None:
    from leetcode_local_cli.models.solution import ProblemMetadata
    from leetcode_local_cli.storage.solution import build_solution_content

    workspace = initialize_workspace(
        tmp_path / "workspace", user_config_file=isolated_user.user_config_file
    ).paths
    workspace.solution_file.write_text(
        build_solution_content(
            "class Solution:\n    def run(self, root: Optional[TreeNode]) -> None:\n        if root:\n            root.val = 8\n",
            ProblemMetadata("1", "1", "Example", "example"),
        ),
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        app, ["test", "--stdin"], input="root = [1, null, 2, 3]\nroot = []\n"
    )
    assert result.exit_code == 0, result.output
    events = [json.loads(line) for line in result.stdout.splitlines()]
    assert events[0]["arguments_after"] == {"root": [8, None, 2, 3]}
    assert events[1]["arguments_after"] == {"root": []}


def test_interactive_verbose_error_is_plain_text(isolated_user, tmp_path) -> None:
    workspace = initialize_workspace(
        tmp_path / "workspace", user_config_file=isolated_user.user_config_file
    ).paths
    workspace.solution_file.write_text(
        "class Solution:\n    def run(self):\n        raise ValueError('[bold]literal[/bold]')\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(app, ["test", "--verbose"], input="()\n\n\n")
    assert result.exit_code == 1
    assert "solution.py:3" in result.output
    assert "Traceback" in result.output
    assert "[bold]literal[/bold]" in result.output


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
