from pathlib import Path

import pytest

from leetcode_local_cli.client import ClientErrorKind, ClientResult
from leetcode_local_cli.doctor import DoctorCheck, DoctorStatus
from leetcode_local_cli.paths import AppPaths
from leetcode_local_cli.problem import ParseQuestionIdResult
from leetcode_local_cli.use_cases import (
    account,
    common,
    diagnostics,
    problems,
    submission,
)
from leetcode_local_cli.use_cases.common import UseCaseError
from leetcode_local_cli.workspace import ProblemMetadata


class FakeClient:
    def __init__(self, cookies: dict[str, str]) -> None:
        self.cookies = cookies

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return None


@pytest.fixture
def app_paths(tmp_path) -> AppPaths:
    return AppPaths.from_workspace(
        tmp_path / "workspace",
        user_config_file=tmp_path / "config.toml",
    )


def _session_data() -> dict:
    return {
        "cookies": {
            "LEETCODE_SESSION": "session-value",
            "csrftoken": "csrf-value",
        }
    }


def _check(name: str) -> DoctorCheck:
    return DoctorCheck(name=name, status=DoctorStatus.PASS, message="ok")


def test_use_cases_do_not_depend_on_cli_or_rich() -> None:
    use_cases_dir = Path("src/leetcode_local_cli/use_cases")

    for path in use_cases_dir.glob("*.py"):
        content = path.read_text(encoding="utf-8")
        assert "from typer" not in content
        assert "import typer" not in content
        assert "from rich" not in content
        assert "leetcode_local_cli.ui" not in content


def test_load_cookies_stops_on_failed_session_inspection(
    monkeypatch,
    app_paths,
) -> None:
    monkeypatch.setattr(
        common,
        "diagnose_session",
        lambda path: DoctorCheck(
            name="session",
            status=DoctorStatus.FAIL,
            message="Session 文件结构无效",
            suggestion="请重新登录",
        ),
    )
    monkeypatch.setattr(
        common,
        "load_session",
        lambda path: (_ for _ in ()).throw(AssertionError("should not load")),
    )

    with pytest.raises(UseCaseError) as caught:
        common.load_cookies_from_session(app_paths)

    assert caught.value.message == "Session 文件结构无效"
    assert caught.value.suggestion == "请重新登录"


def test_get_user_status_reports_client_error(monkeypatch, app_paths) -> None:
    class ErrorClient(FakeClient):
        def user_status(self) -> ClientResult:
            return ClientResult(error=ClientErrorKind.NETWORK)

    monkeypatch.setattr(account, "load_cookies_from_session", lambda paths: {})
    monkeypatch.setattr(account, "LeetCodeClient", ErrorClient)

    with pytest.raises(UseCaseError, match="网络请求失败"):
        account.get_user_status(app_paths)


@pytest.mark.parametrize(
    "error_kind",
    [ClientErrorKind.UNAUTHORIZED, ClientErrorKind.MISSING_CSRF],
)
def test_authentication_error_messages_use_installed_cli_command(error_kind) -> None:
    message = common.client_error_message(error_kind)

    assert "lc login" in message
    assert "uv run" not in message


def test_parse_question_id_rejects_success_without_id(monkeypatch) -> None:
    monkeypatch.setattr(
        problems,
        "parse_question_id",
        lambda question_id: ParseQuestionIdResult(),
    )

    with pytest.raises(UseCaseError, match="题号解析失败"):
        problems._parse_question_id("1")


def test_get_problem_summaries_rejects_invalid_response(
    monkeypatch,
    app_paths,
) -> None:
    class InvalidProblemListClient(FakeClient):
        def problem_list(self, limit: int = 50, skip: int = 0) -> ClientResult:
            return ClientResult(data=None)

    monkeypatch.setattr(problems, "load_cookies_from_session", lambda paths: {})
    monkeypatch.setattr(problems, "LeetCodeClient", InvalidProblemListClient)

    with pytest.raises(UseCaseError, match="数据结构异常"):
        problems.get_problem_summaries(app_paths)


@pytest.mark.parametrize(
    ("limit", "skip", "message"),
    (
        (0, 0, "limit 必须是正整数"),
        (101, 0, "limit 超过单次查询上限"),
        (3, -1, "skip 必须是非负整数"),
    ),
)
def test_get_problem_summaries_rejects_invalid_options(
    limit,
    skip,
    message,
    app_paths,
) -> None:
    with pytest.raises(UseCaseError, match=message):
        problems.get_problem_summaries(app_paths, limit=limit, skip=skip)


def test_submit_current_solution_returns_result_and_reports_target(
    monkeypatch,
    app_paths,
) -> None:
    class SubmitClient(FakeClient):
        def submit_solution(
            self,
            title_slug: str,
            question_id: str,
            code: str,
        ) -> ClientResult:
            assert title_slug == "two-sum"
            assert question_id == "1"
            assert code == "class Solution:\n    pass"
            return ClientResult(data=123)

        def get_submission_result(self, submission_id: int) -> ClientResult:
            assert submission_id == 123
            return ClientResult(data={"state": "SUCCESS", "status_msg": "Accepted"})

    monkeypatch.setattr(submission, "load_cookies_from_session", lambda paths: {})
    monkeypatch.setattr(submission, "LeetCodeClient", SubmitClient)
    monkeypatch.setattr(
        submission,
        "parse_solution_submission",
        lambda path: (
            ProblemMetadata(
                problem_id="1",
                submit_question_id="1",
                title="Two Sum",
                title_slug="two-sum",
            ),
            "class Solution:\n    pass",
        ),
    )
    targets = []

    result = submission.submit_current_solution(app_paths, on_target=targets.append)

    assert result == {"state": "SUCCESS", "status_msg": "Accepted"}
    assert targets[0].problem_id == "1"


def test_get_doctor_report_collects_local_and_remote_checks(
    monkeypatch,
    app_paths,
) -> None:
    class DoctorClient(FakeClient):
        def user_status(self) -> ClientResult:
            return ClientResult(data={"isSignedIn": True, "username": "learner"})

    monkeypatch.setattr(diagnostics, "load_session", lambda path: _session_data())
    monkeypatch.setattr(diagnostics, "LeetCodeClient", DoctorClient)
    monkeypatch.setattr(diagnostics, "diagnose_session", lambda path: _check("session"))
    received = []
    monkeypatch.setattr(
        diagnostics,
        "diagnose_solution",
        lambda path, *, run_solution=False: (
            received.append(run_solution) or _check("solution")
        ),
    )

    report = diagnostics.get_doctor_report(app_paths)

    assert received == [False]
    assert [check.name for check in report.checks] == [
        "session",
        "connectivity",
        "authentication",
        "solution",
    ]
    assert report.ok


def test_get_doctor_report_forwards_solution_execution(
    monkeypatch,
    app_paths,
) -> None:
    class DoctorClient(FakeClient):
        def user_status(self) -> ClientResult:
            return ClientResult(data={"isSignedIn": False})

    monkeypatch.setattr(diagnostics, "load_session", lambda path: None)
    monkeypatch.setattr(diagnostics, "LeetCodeClient", DoctorClient)
    monkeypatch.setattr(diagnostics, "diagnose_session", lambda path: _check("session"))
    received = []
    monkeypatch.setattr(
        diagnostics,
        "diagnose_solution",
        lambda path, *, run_solution=False: (
            received.append(run_solution) or _check("solution")
        ),
    )

    diagnostics.get_doctor_report(app_paths, run_solution=True)

    assert received == [True]
