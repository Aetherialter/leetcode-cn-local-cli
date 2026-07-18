import pytest
from typer import Exit

from leetcode_local_cli import service
from leetcode_local_cli.client import ClientErrorKind, ClientResult
from leetcode_local_cli.doctor import DoctorCheck, DoctorStatus
from leetcode_local_cli.workspace import ProblemMetadata


class FakeClient:
    def __init__(self, cookies: dict[str, str]) -> None:
        self.cookies = cookies

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return None


@pytest.fixture(autouse=True)
def valid_session_inspection(monkeypatch) -> None:
    monkeypatch.setattr(service, "diagnose_session", lambda: _check("session"))


def _session_data() -> dict:
    return {
        "cookies": {
            "LEETCODE_SESSION": "session-value",
            "csrftoken": "csrf-value",
        }
    }


def test_load_cookies_stops_on_failed_session_inspection(monkeypatch) -> None:
    monkeypatch.setattr(
        service,
        "diagnose_session",
        lambda: DoctorCheck(
            name="session",
            status=DoctorStatus.FAIL,
            message="Session 文件结构无效",
            suggestion="请重新登录",
        ),
    )
    monkeypatch.setattr(
        service,
        "load_session",
        lambda: (_ for _ in ()).throw(AssertionError("should not load")),
    )

    with pytest.raises(Exit):
        service._load_cookies_from_session()


def test_get_user_status_exits_on_client_error(monkeypatch) -> None:
    class ErrorClient(FakeClient):
        def user_status(self) -> ClientResult:
            return ClientResult(error=ClientErrorKind.NETWORK)

    monkeypatch.setattr(service, "load_session", _session_data)
    monkeypatch.setattr(service, "LeetCodeClient", ErrorClient)

    with pytest.raises(Exit):
        service.get_user_status()


@pytest.mark.parametrize(
    "error_kind",
    [ClientErrorKind.UNAUTHORIZED, ClientErrorKind.MISSING_CSRF],
)
def test_authentication_error_messages_use_installed_cli_command(error_kind) -> None:
    message = service.client_error_message(error_kind)

    assert "lc login" in message
    assert "uv run" not in message


def test_get_problem_summaries_exits_on_invalid_response(monkeypatch) -> None:
    class InvalidProblemListClient(FakeClient):
        def problem_list(self, limit: int = 50, skip: int = 0) -> ClientResult:
            return ClientResult(data=None)

    monkeypatch.setattr(service, "load_session", _session_data)
    monkeypatch.setattr(service, "LeetCodeClient", InvalidProblemListClient)

    with pytest.raises(Exit):
        service.get_problem_summaries()


def test_get_problem_summaries_rejects_non_positive_limit(monkeypatch) -> None:
    def fail_load_session():
        raise AssertionError("should not load session for invalid limit")

    monkeypatch.setattr(service, "load_session", fail_load_session)

    with pytest.raises(Exit):
        service.get_problem_summaries(limit=0, skip=0)


def test_get_problem_summaries_rejects_limit_over_single_query_cap(
    monkeypatch,
) -> None:
    def fail_load_session():
        raise AssertionError("should not load session for invalid limit")

    monkeypatch.setattr(service, "load_session", fail_load_session)

    with pytest.raises(Exit):
        service.get_problem_summaries(limit=101, skip=0)


def test_get_problem_summaries_rejects_negative_skip(monkeypatch) -> None:
    def fail_load_session():
        raise AssertionError("should not load session for invalid skip")

    monkeypatch.setattr(service, "load_session", fail_load_session)

    with pytest.raises(Exit):
        service.get_problem_summaries(limit=3, skip=-1)


def test_submit_current_solution_returns_submission_result_data(monkeypatch) -> None:
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
            return ClientResult(
                data={
                    "state": "SUCCESS",
                    "status_msg": "Accepted",
                }
            )

    monkeypatch.setattr(service, "load_session", _session_data)
    monkeypatch.setattr(service, "LeetCodeClient", SubmitClient)
    rendered_targets = []
    monkeypatch.setattr(service, "render_submission_target", rendered_targets.append)
    monkeypatch.setattr(
        service,
        "parse_solution_submission",
        lambda: (
            ProblemMetadata(
                problem_id="1",
                submit_question_id="1",
                title="Two Sum",
                title_slug="two-sum",
            ),
            "class Solution:\n    pass",
        ),
    )

    result = service.submit_current_solution()

    assert result == {
        "state": "SUCCESS",
        "status_msg": "Accepted",
    }
    assert rendered_targets[0].problem_id == "1"


def test_get_doctor_report_collects_local_and_remote_checks(monkeypatch) -> None:
    class DoctorClient(FakeClient):
        def user_status(self) -> ClientResult:
            return ClientResult(data={"isSignedIn": True, "username": "learner"})

    monkeypatch.setattr(
        service,
        "load_session",
        lambda: {
            "cookies": {
                "LEETCODE_SESSION": "session-value",
                "csrftoken": "csrf-value",
            }
        },
    )
    monkeypatch.setattr(service, "LeetCodeClient", DoctorClient)
    monkeypatch.setattr(
        service,
        "diagnose_session",
        lambda: _check("session"),
    )
    monkeypatch.setattr(service, "diagnose_solution", lambda: _check("solution"))

    report = service.get_doctor_report()

    assert [check.name for check in report.checks] == [
        "session",
        "connectivity",
        "authentication",
        "solution",
    ]
    assert report.ok


def _check(name: str) -> DoctorCheck:
    return DoctorCheck(name=name, status=DoctorStatus.PASS, message="ok")
