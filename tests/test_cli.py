import json
import os
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path

import pytest
from click import unstyle
from typer.testing import CliRunner

from leetcode_local_cli import cli
from leetcode_local_cli.commands import account as account_commands
from leetcode_local_cli.commands import common as command_common
from leetcode_local_cli.commands import problems as problem_commands
from leetcode_local_cli.commands import setup as setup_commands
from leetcode_local_cli.commands import submission as submission_commands
from leetcode_local_cli.commands import testing as testing_commands
from leetcode_local_cli.integrations.browser import BrowserDevToolsEndpoint, BrowserKind
from leetcode_local_cli.models.account import UserStatus
from leetcode_local_cli.models.diagnostics import (
    DoctorCheck,
    DoctorReport,
    DoctorStatus,
)
from leetcode_local_cli.models.problem import ProblemDetail
from leetcode_local_cli.models.result import ClientErrorKind, ClientSuccess
from leetcode_local_cli.models.session import Credentials, Session
from leetcode_local_cli.models.solution import (
    SolutionFileInspection,
    SolutionFileStatus,
)
from leetcode_local_cli.models.submission import (
    SubmissionJudged,
    SubmissionPending,
    SubmissionPollingFailed,
    SubmissionTimedOut,
)
from leetcode_local_cli.storage.paths import AppPaths
from leetcode_local_cli.use_cases import local_test as local_test_use_case
from leetcode_local_cli.use_cases import login as login_use_case
from leetcode_local_cli.use_cases.common import UseCaseError

runner = CliRunner()
login_reporter = login_use_case.LoginReporter(
    info=lambda message: None,
    warning=lambda message: None,
    loading=lambda message: nullcontext(),
)


@pytest.fixture(autouse=True)
def configured_app_paths(tmp_path, monkeypatch) -> AppPaths:
    paths = AppPaths.from_workspace(
        tmp_path / "workspace",
        user_config_file=tmp_path / "config.toml",
        user_state_directory=tmp_path / "state",
    )
    monkeypatch.setattr(command_common, "require_app_paths", lambda: paths)
    monkeypatch.setattr(command_common, "get_user_paths", lambda: paths.user)
    monkeypatch.setattr(
        command_common,
        "require_workspace_paths",
        lambda: paths.workspace,
    )
    return paths


def test_module_entrypoint_emits_utf8_when_initial_encoding_is_cp1252() -> None:
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "cp1252"

    result = subprocess.run(
        [sys.executable, "-m", "leetcode_local_cli", "--help"],
        capture_output=True,
        check=False,
        env=environment,
    )

    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert "力扣中文站" in result.stdout.decode("utf-8")


def test_version_option_displays_installed_distribution_version(monkeypatch) -> None:
    monkeypatch.setattr(cli, "get_version", lambda: "1.2.3")

    result = runner.invoke(cli.app, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == "leetcode-local-cli 1.2.3"


def test_help_registers_doctor_command() -> None:
    result = runner.invoke(cli.app, ["--help"])

    assert result.exit_code == 0
    assert "doctor" in result.output


def test_help_registers_init_command() -> None:
    result = runner.invoke(cli.app, ["--help"])

    assert result.exit_code == 0
    assert "init" in result.output


def test_init_explicit_path_yes_creates_and_configures_workspace(
    tmp_path,
    monkeypatch,
) -> None:
    workspace_root = tmp_path / "workspace"
    user_config_file = tmp_path / "config" / "config.toml"
    monkeypatch.setattr(
        setup_commands, "get_user_config_file", lambda: user_config_file
    )

    result = runner.invoke(cli.app, ["init", str(workspace_root), "--yes"])

    assert result.exit_code == 0, result.output
    assert (workspace_root / ".leetcode_local_cli" / "workspace.toml").is_file()
    assert (workspace_root / "solution.py").read_text(encoding="utf-8") == ""
    assert workspace_root.as_posix() in user_config_file.read_text(encoding="utf-8")


def test_init_without_path_appends_fixed_workspace_directory(
    tmp_path,
    monkeypatch,
) -> None:
    user_config_file = tmp_path / "config" / "config.toml"
    monkeypatch.setattr(
        setup_commands, "get_user_config_file", lambda: user_config_file
    )

    result = runner.invoke(cli.app, ["init"], input=f"{tmp_path}\ny\n")

    workspace_root = tmp_path / "leetcode-local-cli"
    assert result.exit_code == 0, result.output
    assert (workspace_root / ".leetcode_local_cli" / "workspace.toml").is_file()
    assert (workspace_root / "solution.py").is_file()


def test_init_preserves_existing_regular_solution(tmp_path, monkeypatch) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    solution_file = workspace_root / "solution.py"
    solution_file.write_text("existing solution", encoding="utf-8")
    user_config_file = tmp_path / "config" / "config.toml"
    monkeypatch.setattr(
        setup_commands, "get_user_config_file", lambda: user_config_file
    )

    result = runner.invoke(cli.app, ["init", str(workspace_root), "--yes"])

    assert result.exit_code == 0, result.output
    assert solution_file.read_text(encoding="utf-8") == "existing solution"


def test_init_without_path_reuses_valid_default_workspace(
    tmp_path,
    monkeypatch,
) -> None:
    workspace_root = tmp_path / "workspace"
    user_config_file = tmp_path / "config" / "config.toml"
    monkeypatch.setattr(
        setup_commands, "get_user_config_file", lambda: user_config_file
    )
    first_result = runner.invoke(
        cli.app,
        ["init", str(workspace_root), "--yes"],
    )
    assert first_result.exit_code == 0, first_result.output

    result = runner.invoke(cli.app, ["init"])

    assert result.exit_code == 0, result.output
    assert "继续使用现有工作区" in result.output
    assert "请输入工作区父目录" not in result.output


def test_init_yes_requires_explicit_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        setup_commands,
        "get_user_config_file",
        lambda: tmp_path / "missing" / "config.toml",
    )

    result = runner.invoke(cli.app, ["init", "--yes"])

    assert result.exit_code == 1
    assert "--yes 必须与工作区完整路径一起使用" in result.output


def test_doctor_command_renders_successful_report(monkeypatch) -> None:
    report = DoctorReport(checks=(DoctorCheck("session", DoctorStatus.PASS, "ok"),))
    rendered = []
    received = []
    monkeypatch.setattr(
        testing_commands,
        "get_doctor_report",
        lambda paths, *, run_solution=False: received.append(run_solution) or report,
    )
    monkeypatch.setattr(testing_commands, "render_doctor_report", rendered.append)

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 0
    assert received == [False]
    assert rendered == [report]


def test_doctor_command_forwards_run_solution_option(monkeypatch) -> None:
    report = DoctorReport(checks=(DoctorCheck("solution", DoctorStatus.PASS, "ok"),))
    received = []
    monkeypatch.setattr(
        testing_commands,
        "get_doctor_report",
        lambda paths, *, run_solution=False: received.append(run_solution) or report,
    )
    monkeypatch.setattr(testing_commands, "render_doctor_report", lambda report: None)

    result = runner.invoke(cli.app, ["doctor", "--run-solution"])

    assert result.exit_code == 0
    assert received == [True]


def test_doctor_command_exits_nonzero_for_failed_report(monkeypatch) -> None:
    report = DoctorReport(checks=(DoctorCheck("session", DoctorStatus.FAIL, "failed"),))
    monkeypatch.setattr(
        testing_commands,
        "get_doctor_report",
        lambda paths, *, run_solution=False: report,
    )
    monkeypatch.setattr(testing_commands, "render_doctor_report", lambda report: None)

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 1


def test_user_scope_commands_do_not_require_workspace_resolution(
    configured_app_paths,
    monkeypatch,
) -> None:
    def reject_workspace_resolution():
        pytest.fail("user-scope command must not resolve a workspace")

    problem = object()
    report = DoctorReport(checks=(DoctorCheck("session", DoctorStatus.PASS, "ok"),))
    monkeypatch.setattr(
        command_common, "require_app_paths", reject_workspace_resolution
    )
    monkeypatch.setattr(
        command_common,
        "require_workspace_paths",
        reject_workspace_resolution,
    )
    monkeypatch.setattr(
        account_commands,
        "try_automatic_login",
        lambda browser, session_file, *, reporter, devtools_port=None: True,
    )
    monkeypatch.setattr(
        account_commands,
        "get_user_status",
        lambda paths: UserStatus(True, "learner"),
    )
    monkeypatch.setattr(account_commands, "get_account_profile", lambda paths: {})
    monkeypatch.setattr(account_commands, "render_profile", lambda profile: None)
    monkeypatch.setattr(
        problem_commands,
        "get_problem_summaries",
        lambda paths, *, limit, skip, progress: [],
    )
    monkeypatch.setattr(problem_commands, "render_problem_list", lambda problems: None)
    monkeypatch.setattr(
        problem_commands,
        "get_problem_detail_by_question_id",
        lambda paths, question_id, *, progress: problem,
    )
    monkeypatch.setattr(problem_commands, "render_problem_detail", lambda detail: None)
    monkeypatch.setattr(
        submission_commands,
        "check_existing_submission",
        lambda paths, submission_id: SubmissionJudged(
            submission_id=submission_id,
            status_message="Accepted",
        ),
    )
    monkeypatch.setattr(
        submission_commands,
        "render_submission_result",
        lambda result: None,
    )
    monkeypatch.setattr(
        testing_commands,
        "get_doctor_report",
        lambda paths, *, run_solution=False: report,
    )
    monkeypatch.setattr(testing_commands, "render_doctor_report", lambda report: None)

    for arguments in (
        ["login"],
        ["status"],
        ["profile"],
        ["show"],
        ["get", "1"],
        ["check", "123"],
        ["doctor"],
    ):
        result = runner.invoke(cli.app, arguments)
        assert result.exit_code == 0, (arguments, result.output)


def test_login_uses_explicit_chrome_devtools_port_without_manual_fallback(
    configured_app_paths,
    monkeypatch,
) -> None:
    cookies = {"LEETCODE_SESSION": "session-value", "csrftoken": "csrf-value"}
    saved_sessions = []

    class SignedInClient:
        def __init__(self, received_cookies):
            assert received_cookies == cookies

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def user_status(self):
            return ClientSuccess(UserStatus(True, "learner"))

    validated = []
    monkeypatch.setattr(
        login_use_case,
        "validate_devtools_browser",
        lambda port, browser: validated.append((port, browser)),
    )
    monkeypatch.setattr(
        login_use_case, "get_cookies_from_devtools", lambda port: cookies
    )
    monkeypatch.setattr(
        account_commands,
        "get_cookies_from_input",
        lambda: pytest.fail("manual Cookie input must not run"),
    )
    monkeypatch.setattr(login_use_case, "LeetCodeClient", SignedInClient)
    monkeypatch.setattr(
        login_use_case,
        "save_session",
        lambda session, path: saved_sessions.append((session, path)),
    )

    result = runner.invoke(
        cli.app,
        ["login", "--browser", "chrome", "--devtools-port", "9222"],
    )

    assert result.exit_code == 0, result.output
    assert validated == [(9222, BrowserKind.CHROME)]
    assert saved_sessions == [
        (
            Session(
                Credentials("session-value", "csrf-value"),
                username="learner",
                source="Chrome DevTools",
            ),
            configured_app_paths.user.session_file,
        )
    ]


def test_login_auto_stops_after_chrome_success(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        login_use_case,
        "_try_authorized_browser_login",
        lambda browser, session_file, *, reporter: calls.append(browser) or True,
    )
    monkeypatch.setattr(
        account_commands,
        "_login_manually",
        lambda session_file: pytest.fail("manual login must not run"),
    )

    result = runner.invoke(cli.app, ["login"])

    assert result.exit_code == 0, result.output
    assert calls == [BrowserKind.CHROME]


def test_login_auto_falls_back_from_chrome_to_edge(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        login_use_case,
        "_try_authorized_browser_login",
        lambda browser, session_file, *, reporter: (
            calls.append(browser) or browser is BrowserKind.EDGE
        ),
    )
    monkeypatch.setattr(
        account_commands,
        "_login_manually",
        lambda session_file: pytest.fail("manual login must not run"),
    )

    result = runner.invoke(cli.app, ["login"])

    assert result.exit_code == 0, result.output
    assert calls == [BrowserKind.CHROME, BrowserKind.EDGE]


@pytest.mark.parametrize(
    ("browser_name", "expected_call"),
    [("chrome", "chrome"), ("edge", "edge")],
)
def test_login_explicit_browser_does_not_try_the_other_browser(
    browser_name,
    expected_call,
    monkeypatch,
) -> None:
    calls = []
    monkeypatch.setattr(
        login_use_case,
        "_try_authorized_browser_login",
        lambda browser, session_file, *, reporter: calls.append(browser.value) or True,
    )

    result = runner.invoke(cli.app, ["login", "--browser", browser_name])

    assert result.exit_code == 0, result.output
    assert calls == [expected_call]


def test_login_auto_falls_back_to_manual_after_both_browsers_fail(
    monkeypatch,
) -> None:
    calls = []
    monkeypatch.setattr(
        login_use_case,
        "_try_authorized_browser_login",
        lambda browser, path, *, reporter: False,
    )
    monkeypatch.setattr(
        account_commands,
        "_login_manually",
        lambda session_file: calls.append("manual"),
    )

    result = runner.invoke(cli.app, ["login"])

    assert result.exit_code == 0, result.output
    assert calls == ["manual"]


def test_login_devtools_port_requires_explicit_browser(monkeypatch) -> None:
    monkeypatch.setattr(
        account_commands,
        "try_automatic_login",
        lambda *args, **kwargs: pytest.fail("ambiguous endpoint must not be used"),
    )

    result = runner.invoke(cli.app, ["login", "--devtools-port", "9222"])

    assert result.exit_code == 2
    plain_output = " ".join(unstyle(result.output).split())
    assert "--browser chrome" in plain_output


def test_login_rejects_removed_chrome_debug_port_alias(monkeypatch) -> None:
    monkeypatch.setattr(
        account_commands,
        "try_automatic_login",
        lambda *args, **kwargs: pytest.fail("removed option must not be accepted"),
    )

    result = runner.invoke(
        cli.app,
        ["login", "--browser", "chrome", "--chrome-debug-port", "9222"],
    )

    assert result.exit_code == 2
    assert "No such option" in result.output


@pytest.mark.parametrize(
    ("browser", "prefixes", "source"),
    [
        (BrowserKind.CHROME, ("Chrome/",), "Chrome DevTools"),
        (BrowserKind.EDGE, ("Edg/",), "Edge DevTools"),
    ],
)
def test_authorized_browser_login_uses_existing_authorization_without_opening_pages(
    browser,
    prefixes,
    source,
    monkeypatch,
) -> None:
    cookies = {"LEETCODE_SESSION": "session", "csrftoken": "csrf"}
    events = []
    endpoint = BrowserDevToolsEndpoint(
        port=53127,
        debugger_url="ws://127.0.0.1:53127/devtools/browser/example",
    )
    monkeypatch.setattr(
        login_use_case,
        "read_browser_devtools_endpoint",
        lambda received_browser: endpoint,
    )
    monkeypatch.setattr(
        login_use_case,
        "get_cookies_from_browser_endpoint",
        lambda url, **kwargs: events.append(("connect", url, kwargs)) or cookies,
    )
    monkeypatch.setattr(
        login_use_case,
        "open_browser_authorization_pages",
        lambda received_browser: pytest.fail(
            "authorized browser must not open another page"
        ),
    )
    monkeypatch.setattr(
        login_use_case,
        "validate_and_save_login",
        lambda received, **kwargs: (
            events.append(("save", received, kwargs["source"])) or True
        ),
    )

    assert (
        login_use_case._try_authorized_browser_login(
            browser,
            Path("session.json"),
            reporter=login_reporter,
        )
        is True
    )
    assert events == [
        (
            "connect",
            endpoint.debugger_url,
            {
                "expected_port": endpoint.port,
                "expected_browser_prefixes": prefixes,
                "timeout_seconds": login_use_case.BROWSER_LOGIN_TIMEOUT_SECONDS,
            },
        ),
        ("save", cookies, source),
    ]


@pytest.mark.parametrize("browser", [BrowserKind.CHROME, BrowserKind.EDGE])
def test_authorized_browser_login_opens_pages_when_permission_is_missing(
    browser,
    monkeypatch,
) -> None:
    cookies = {"LEETCODE_SESSION": "session", "csrftoken": "csrf"}
    events = []
    monkeypatch.setattr(
        login_use_case,
        "read_browser_devtools_endpoint",
        lambda received_browser: (_ for _ in ()).throw(
            login_use_case.BrowserAuthorizationPending("browser 尚未授权")
        ),
    )
    monkeypatch.setattr(
        login_use_case,
        "open_browser_authorization_pages",
        lambda received_browser: events.append(("open", received_browser)),
    )
    monkeypatch.setattr(
        login_use_case,
        "_wait_for_browser_cookies",
        lambda received_browser: cookies,
    )
    monkeypatch.setattr(
        login_use_case, "validate_and_save_login", lambda *args, **kwargs: True
    )

    assert (
        login_use_case._try_authorized_browser_login(
            browser,
            Path("session.json"),
            reporter=login_reporter,
        )
        is True
    )
    assert events == [("open", browser)]


def test_authorized_browser_login_does_not_reopen_for_generic_endpoint_failure(
    monkeypatch,
) -> None:
    endpoint = BrowserDevToolsEndpoint(
        port=53127,
        debugger_url="ws://127.0.0.1:53127/devtools/browser/example",
    )
    monkeypatch.setattr(
        login_use_case,
        "read_browser_devtools_endpoint",
        lambda browser: endpoint,
    )
    monkeypatch.setattr(
        login_use_case,
        "open_browser_authorization_pages",
        lambda browser: pytest.fail("generic failures must not open more pages"),
    )
    monkeypatch.setattr(
        login_use_case,
        "get_cookies_from_browser_endpoint",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            login_use_case.DevToolsError("stale endpoint")
        ),
    )

    assert (
        login_use_case._try_authorized_browser_login(
            BrowserKind.CHROME,
            Path("session.json"),
            reporter=login_reporter,
        )
        is False
    )


def test_chrome_login_starts_browser_when_saved_endpoint_is_unreachable(
    monkeypatch,
) -> None:
    cookies = {"LEETCODE_SESSION": "session", "csrftoken": "csrf"}
    events = []
    info_messages = []
    reporter = login_use_case.LoginReporter(
        info=info_messages.append,
        warning=lambda message: None,
        loading=lambda message: nullcontext(),
    )
    endpoint = BrowserDevToolsEndpoint(
        port=53127,
        debugger_url="ws://127.0.0.1:53127/devtools/browser/example",
    )
    monkeypatch.setattr(
        login_use_case,
        "read_browser_devtools_endpoint",
        lambda browser: endpoint,
    )
    monkeypatch.setattr(
        login_use_case,
        "get_cookies_from_browser_endpoint",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            login_use_case.DevToolsConnectionUnavailable("browser is not running")
        ),
    )
    monkeypatch.setattr(
        login_use_case,
        "open_browser_authorization_pages",
        lambda browser: events.append(("open", browser)),
    )
    monkeypatch.setattr(
        login_use_case,
        "sleep",
        lambda seconds: events.append(("sleep", seconds)),
    )
    monkeypatch.setattr(
        login_use_case,
        "_wait_for_browser_cookies",
        lambda browser: events.append(("wait", browser)) or cookies,
    )
    monkeypatch.setattr(
        login_use_case, "validate_and_save_login", lambda *args, **kwargs: True
    )

    assert (
        login_use_case._try_authorized_browser_login(
            BrowserKind.CHROME,
            Path("session.json"),
            reporter=reporter,
        )
        is True
    )
    assert events == [
        ("open", BrowserKind.CHROME),
        ("sleep", login_use_case.BROWSER_WINDOW_READY_DELAY_SECONDS),
        ("wait", BrowserKind.CHROME),
    ]
    assert info_messages[0] == (
        "Google Chrome 自动登录前，请先打开 "
        "chrome://inspect/#remote-debugging，"
        "勾选 Allow remote debugging for this browser instance"
    )
    assert any(
        "当前未运行或授权端点暂不可用" in message
        and "chrome://inspect/#remote-debugging" in message
        for message in info_messages
    )


def test_wait_for_browser_cookies_retries_while_browser_starts(monkeypatch) -> None:
    cookies = {"LEETCODE_SESSION": "session", "csrftoken": "csrf"}
    endpoint = BrowserDevToolsEndpoint(
        port=53127,
        debugger_url="ws://127.0.0.1:53127/devtools/browser/example",
    )
    attempts = []

    def read_cookies(browser, received_endpoint, *, timeout_seconds):
        attempts.append((browser, received_endpoint, timeout_seconds))
        if len(attempts) == 1:
            raise login_use_case.DevToolsConnectionUnavailable("browser is starting")
        return cookies

    monkeypatch.setattr(
        login_use_case,
        "read_browser_devtools_endpoint",
        lambda browser: endpoint,
    )
    monkeypatch.setattr(login_use_case, "_read_browser_login_cookies", read_cookies)
    monkeypatch.setattr(login_use_case, "sleep", lambda seconds: None)

    assert login_use_case._wait_for_browser_cookies(BrowserKind.CHROME) == cookies
    assert len(attempts) == 2


@pytest.mark.parametrize("browser", [BrowserKind.CHROME, BrowserKind.EDGE])
def test_authorized_browser_login_opens_visible_window_and_retries_after_rejection(
    browser,
    monkeypatch,
) -> None:
    cookies = {"LEETCODE_SESSION": "session", "csrftoken": "csrf"}
    events = []
    endpoint = BrowserDevToolsEndpoint(
        port=53127,
        debugger_url="ws://127.0.0.1:53127/devtools/browser/example",
    )
    monkeypatch.setattr(
        login_use_case,
        "read_browser_devtools_endpoint",
        lambda received_browser: endpoint,
    )
    monkeypatch.setattr(
        login_use_case,
        "get_cookies_from_browser_endpoint",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            login_use_case.DevToolsApprovalRejected("approval rejected")
        ),
    )
    monkeypatch.setattr(
        login_use_case,
        "open_browser_authorization_pages",
        lambda received_browser: events.append(("open", received_browser)),
    )
    monkeypatch.setattr(
        login_use_case,
        "sleep",
        lambda seconds: events.append(("sleep", seconds)),
    )
    monkeypatch.setattr(
        login_use_case,
        "_wait_for_browser_cookies",
        lambda received_browser: events.append(("retry", received_browser)) or cookies,
    )
    monkeypatch.setattr(
        login_use_case, "validate_and_save_login", lambda *args, **kwargs: True
    )

    assert (
        login_use_case._try_authorized_browser_login(
            browser,
            Path("session.json"),
            reporter=login_reporter,
        )
        is True
    )
    assert events == [
        ("open", browser),
        ("sleep", login_use_case.BROWSER_WINDOW_READY_DELAY_SECONDS),
        ("retry", browser),
    ]


def test_solve_command_reports_rejected_workspace_target(monkeypatch) -> None:
    problem = ProblemDetail(
        question_id="1",
        submit_question_id="1",
        title="Two Sum",
        title_slug="two-sum",
        difficulty="Easy",
        tags=("Array",),
        content_html="<p>content</p>",
        python_code="class Solution:\n    pass",
    )
    monkeypatch.setattr(
        problem_commands,
        "get_problem_detail_by_question_id",
        lambda paths, question_id, *, progress: problem,
    )
    monkeypatch.setattr(problem_commands, "render_problem_detail", lambda problem: None)
    monkeypatch.setattr(
        problem_commands,
        "write_problem_solution",
        lambda paths, problem, *, open_editor: (_ for _ in ()).throw(
            UseCaseError("solution.py 是符号链接或断链，已拒绝写入")
        ),
    )

    result = runner.invoke(cli.app, ["solve", "1"])

    assert result.exit_code == 1
    assert "符号链接或断链" in result.output
    assert "Traceback" not in result.output


def test_test_command_reports_missing_solution_without_starting_worker(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        local_test_use_case,
        "inspect_solution_file",
        lambda path: SolutionFileInspection(status=SolutionFileStatus.MISSING),
    )
    monkeypatch.setattr(
        local_test_use_case,
        "LocalExecutionWorker",
        lambda *args, **kwargs: pytest.fail("worker must not start"),
    )

    result = runner.invoke(cli.app, ["test"])

    assert result.exit_code == 1
    assert "未找到 solution.py" in result.output


def test_test_command_reports_syntax_line_without_starting_worker(monkeypatch) -> None:
    monkeypatch.setattr(
        local_test_use_case,
        "inspect_solution_file",
        lambda path: SolutionFileInspection(
            status=SolutionFileStatus.INVALID_SYNTAX,
            syntax_line=7,
        ),
    )

    result = runner.invoke(cli.app, ["test"])

    assert result.exit_code == 1
    assert "第 7 行" in result.output


def test_test_command_rejects_invalid_encoding_without_running(
    configured_app_paths,
    monkeypatch,
) -> None:
    solution_file = configured_app_paths.workspace.solution_file
    solution_file.parent.mkdir(parents=True)
    solution_file.write_bytes(b"\xff\xfeinvalid source")
    monkeypatch.setattr(
        local_test_use_case,
        "LocalExecutionWorker",
        lambda *args, **kwargs: pytest.fail("worker must not start"),
    )

    result = runner.invoke(cli.app, ["test"])

    assert result.exit_code == 1
    assert "不是有效的 UTF-8 编码" in result.output
    assert "Traceback" not in result.output


def test_test_command_interactively_runs_detected_solution_entry(
    configured_app_paths,
) -> None:
    solution_file = configured_app_paths.workspace.solution_file
    solution_file.parent.mkdir(parents=True)
    solution_file.write_text(
        """
class Solution:
    def twoSum(self, nums, target):
        seen = {}
        for index, value in enumerate(nums):
            if target - value in seen:
                return [seen[target - value], index]
            seen[value] = index
        return []
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        cli.app,
        ["test"],
        input="nums = [3, 2, 4], target = 6\n\n\n",
    )

    assert result.exit_code == 0, result.output
    assert "检测到入口：Solution.twoSum(nums, target)" in result.output
    assert "[1, 2]" in result.output
    assert "已成功执行 1 组输入" in result.output


def test_test_command_rejects_empty_input_without_claiming_success(
    configured_app_paths,
) -> None:
    solution_file = configured_app_paths.workspace.solution_file
    solution_file.parent.mkdir(parents=True)
    solution_file.write_text(
        """
class Solution:
    def identity(self, value):
        return value
""",
        encoding="utf-8",
    )

    result = runner.invoke(cli.app, ["test"], input="\n\n")

    assert result.exit_code == 1, result.output
    assert "未执行任何本地输入" in result.output
    assert "执行完成" not in result.output


def test_test_command_continues_after_a_bad_input_and_returns_nonzero(
    configured_app_paths,
) -> None:
    solution_file = configured_app_paths.workspace.solution_file
    solution_file.parent.mkdir(parents=True)
    solution_file.write_text(
        """
class Solution:
    def echo(self, value):
        return value
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        cli.app,
        ["test"],
        input="value = input()\nvalue = 3\n\n\n",
    )

    assert result.exit_code == 1, result.output
    assert "第 1 组执行失败" in result.output
    assert "参数 value 必须是安全 Python 字面量" in result.output
    assert "3" in result.output
    assert "成功 1 组，失败 1 组" in result.output


@pytest.mark.parametrize("timeout", ("0", "-1", "nan", "inf"))
def test_test_command_rejects_invalid_timeout(timeout: str) -> None:
    result = runner.invoke(cli.app, ["test", "--timeout", timeout])

    assert result.exit_code == 2
    assert "大于 0 的有限秒数" in result.output


def test_test_command_stdin_outputs_json_lines(configured_app_paths) -> None:
    solution_file = configured_app_paths.workspace.solution_file
    solution_file.parent.mkdir(parents=True)
    solution_file.write_text(
        """
class Solution:
    def twoSum(self, nums, target):
        return [0, 1]
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        cli.app,
        ["test", "--stdin"],
        input="nums = [2, 7], target = 9\nnums = input()\n",
    )

    assert result.exit_code == 1, result.output
    lines = [json.loads(line) for line in result.output.splitlines()]
    assert lines[0] == {
        "case": 1,
        "ok": True,
        "result": [0, 1],
        "result_is_json": True,
    }
    assert lines[1]["case"] == 2
    assert lines[1]["ok"] is False
    assert lines[-1] == {"kind": "summary", "total": 2, "successful": 1, "failed": 1}


def test_submit_does_not_start_local_execution_worker(monkeypatch) -> None:
    monkeypatch.setattr(
        submission_commands,
        "submit_current_solution",
        lambda paths, **kwargs: SubmissionJudged(123, "Accepted"),
    )
    monkeypatch.setattr(
        submission_commands, "render_submission_result", lambda result: None
    )
    monkeypatch.setattr(
        local_test_use_case,
        "LocalExecutionWorker",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("submit must not execute local tests")
        ),
    )

    result = runner.invoke(cli.app, ["submit"])

    assert result.exit_code == 0


@pytest.mark.parametrize(
    ("submission_result", "expected_exit_code"),
    (
        (SubmissionJudged(123, "Accepted"), 0),
        (SubmissionJudged(123, "Wrong Answer"), 1),
        (SubmissionJudged(123, "Time Limit Exceeded"), 1),
        (SubmissionTimedOut(123, 30), 1),
        (
            SubmissionPollingFailed(
                123,
                ClientErrorKind.NETWORK,
                "网络请求失败",
            ),
            1,
        ),
    ),
)
def test_submit_exit_code_reflects_final_judge_result(
    monkeypatch,
    submission_result,
    expected_exit_code: int,
) -> None:
    rendered_results = []
    monkeypatch.setattr(
        submission_commands,
        "submit_current_solution",
        lambda paths, **kwargs: submission_result,
    )
    monkeypatch.setattr(
        submission_commands,
        "render_submission_result",
        rendered_results.append,
    )

    result = runner.invoke(cli.app, ["submit"])

    assert result.exit_code == expected_exit_code
    assert rendered_results == [submission_result]


@pytest.mark.parametrize("wait_timeout", ("0", "-1", "nan", "inf"))
def test_submit_rejects_invalid_wait_timeout(wait_timeout: str) -> None:
    result = runner.invoke(
        cli.app,
        ["submit", "--wait-timeout", wait_timeout],
    )

    assert result.exit_code == 2
    assert "--wait-timeout" in unstyle(result.output)


def test_submit_forwards_wait_timeout_and_renders_submission_id(monkeypatch) -> None:
    received = []
    submitted = []

    def fake_submit(paths, **kwargs):
        received.append(kwargs["wait_timeout_seconds"])
        kwargs["on_submitted"](123)
        return SubmissionJudged(123, "Accepted")

    monkeypatch.setattr(
        submission_commands,
        "submit_current_solution",
        fake_submit,
    )
    monkeypatch.setattr(
        submission_commands,
        "render_submission_submitted",
        lambda submission_id, *, wait_timeout_seconds: submitted.append(
            (submission_id, wait_timeout_seconds)
        ),
    )
    monkeypatch.setattr(
        submission_commands,
        "render_submission_result",
        lambda result: None,
    )

    result = runner.invoke(
        cli.app,
        ["submit", "--wait-timeout", "12.5"],
    )

    assert result.exit_code == 0
    assert received == [12.5]
    assert submitted == [(123, 12.5)]


def test_submit_rejects_invalid_encoding_before_remote_request(
    configured_app_paths,
    monkeypatch,
) -> None:
    solution_file = configured_app_paths.workspace.solution_file
    solution_file.parent.mkdir(parents=True)
    solution_file.write_bytes(b"\xff\xfeinvalid source")
    monkeypatch.setattr(
        "leetcode_local_cli.use_cases.submission.LeetCodeClient",
        lambda cookies: (_ for _ in ()).throw(
            AssertionError("invalid source must not reach remote client")
        ),
    )
    monkeypatch.setattr(
        "leetcode_local_cli.use_cases.submission.load_cookies_from_session",
        lambda paths: (_ for _ in ()).throw(
            AssertionError("invalid source must not load credentials")
        ),
    )

    result = runner.invoke(cli.app, ["submit"])

    assert result.exit_code == 1
    assert "不是有效的 UTF-8 编码" in result.output
    assert "Traceback" not in result.output


@pytest.mark.parametrize(
    ("submission_result", "expected_exit_code"),
    (
        (SubmissionJudged(123, "Accepted"), 0),
        (SubmissionJudged(123, "Wrong Answer"), 1),
        (SubmissionPending(123), 1),
        (
            SubmissionPollingFailed(
                123,
                ClientErrorKind.NETWORK,
                "网络请求失败",
            ),
            1,
        ),
    ),
)
def test_check_exit_code_reflects_current_submission_result(
    monkeypatch,
    submission_result,
    expected_exit_code: int,
) -> None:
    received_ids = []
    rendered_results = []

    def fake_check(paths, submission_id):
        received_ids.append(submission_id)
        return submission_result

    monkeypatch.setattr(
        submission_commands,
        "check_existing_submission",
        fake_check,
    )
    monkeypatch.setattr(
        submission_commands,
        "render_submission_result",
        rendered_results.append,
    )

    result = runner.invoke(cli.app, ["check", "123"])

    assert result.exit_code == expected_exit_code
    assert received_ids == [123]
    assert rendered_results == [submission_result]


@pytest.mark.parametrize("submission_id", ("0", "-1", "not-an-id"))
def test_check_rejects_invalid_submission_id(submission_id: str) -> None:
    result = runner.invoke(cli.app, ["check", submission_id])

    assert result.exit_code == 2
    assert "submission" in result.output.lower()
