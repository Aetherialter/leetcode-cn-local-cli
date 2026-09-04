from pathlib import Path
from typing import cast

import pytest

from leetcode_local_cli.client import ClientErrorKind, ClientResult, LeetCodeClient
from leetcode_local_cli.doctor import DoctorCheck, DoctorStatus
from leetcode_local_cli.paths import AppPaths, UserPaths, WorkspacePaths
from leetcode_local_cli.problem import ParseQuestionIdResult
from leetcode_local_cli.submission import (
    SubmissionCheck,
    SubmissionJudged,
    SubmissionPending,
    SubmissionPollingFailed,
    SubmissionTimedOut,
)
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


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class PollClient:
    def __init__(self, results: list[ClientResult]) -> None:
        self.results = results
        self.timeouts: list[float] = []

    def get_submission_result(
        self,
        submission_id: int,
        *,
        timeout: float,
    ) -> ClientResult:
        assert submission_id == 123
        self.timeouts.append(timeout)
        return self.results.pop(0)


def _poll(
    results: list[ClientResult],
    policy: submission.SubmissionPollingPolicy,
) -> tuple[object, PollClient, FakeClock]:
    client = PollClient(results)
    clock = FakeClock()
    outcome = submission._poll_submission(
        cast(LeetCodeClient, client),
        123,
        policy,
        clock=clock,
        sleeper=clock.sleep,
    )
    return outcome, client, clock


@pytest.fixture
def user_paths(tmp_path) -> UserPaths:
    return UserPaths.defaults(
        user_config_file=tmp_path / "config.toml",
        user_state_directory=tmp_path / "state",
    )


@pytest.fixture
def app_paths(tmp_path, user_paths: UserPaths) -> AppPaths:
    return AppPaths(
        user=user_paths,
        workspace=WorkspacePaths.from_root(tmp_path / "workspace"),
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
    user_paths,
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
        common.load_cookies_from_session(user_paths)

    assert caught.value.message == "Session 文件结构无效"
    assert caught.value.suggestion == "请重新登录"


def test_get_user_status_reports_client_error(monkeypatch, user_paths) -> None:
    class ErrorClient(FakeClient):
        def user_status(self) -> ClientResult:
            return ClientResult(error=ClientErrorKind.NETWORK)

    monkeypatch.setattr(account, "load_cookies_from_session", lambda paths: {})
    monkeypatch.setattr(account, "LeetCodeClient", ErrorClient)

    with pytest.raises(UseCaseError, match="网络请求失败"):
        account.get_user_status(user_paths)


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
    user_paths,
) -> None:
    class InvalidProblemListClient(FakeClient):
        def problem_list(self, limit: int = 50, skip: int = 0) -> ClientResult:
            return ClientResult(data=None)

    monkeypatch.setattr(problems, "load_cookies_from_session", lambda paths: {})
    monkeypatch.setattr(problems, "LeetCodeClient", InvalidProblemListClient)

    with pytest.raises(UseCaseError, match="数据结构异常"):
        problems.get_problem_summaries(user_paths)


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
    user_paths,
) -> None:
    with pytest.raises(UseCaseError, match=message):
        problems.get_problem_summaries(user_paths, limit=limit, skip=skip)


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

        def get_submission_result(
            self,
            submission_id: int,
            *,
            timeout: float,
        ) -> ClientResult:
            assert submission_id == 123
            assert timeout == 10
            return ClientResult(
                data=SubmissionCheck(state="SUCCESS", status_message="Accepted")
            )

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
    submitted = []

    result = submission.submit_current_solution(
        app_paths,
        on_target=targets.append,
        on_submitted=submitted.append,
    )

    assert result == SubmissionJudged(submission_id=123, status_message="Accepted")
    assert targets[0].problem_id == "1"
    assert submitted == [123]


def test_submission_polling_reaches_terminal_result_after_pending_states() -> None:
    policy = submission.SubmissionPollingPolicy(wait_timeout_seconds=5)
    outcome, client, clock = _poll(
        [
            ClientResult(data=SubmissionCheck(state="PENDING")),
            ClientResult(data=SubmissionCheck(state="STARTED")),
            ClientResult(
                data=SubmissionCheck(
                    state="SUCCESS",
                    status_message="Accepted",
                    runtime="4 ms",
                )
            ),
        ],
        policy,
    )

    assert outcome == SubmissionJudged(
        submission_id=123,
        status_message="Accepted",
        runtime="4 ms",
    )
    assert client.timeouts == [5, 4.5, 4]
    assert clock.sleeps == [0.5, 0.5]


def test_submission_polling_uses_total_deadline_and_clamps_sleep() -> None:
    policy = submission.SubmissionPollingPolicy(
        wait_timeout_seconds=1,
        poll_interval_seconds=0.6,
    )
    outcome, client, clock = _poll(
        [
            ClientResult(data=SubmissionCheck(state="PENDING")),
            ClientResult(data=SubmissionCheck(state="PENDING")),
        ],
        policy,
    )

    assert outcome == SubmissionTimedOut(submission_id=123, waited_seconds=1)
    assert client.timeouts == [1, 0.4]
    assert clock.sleeps == [0.6, 0.4]


def test_submission_polling_recovers_from_transient_network_error() -> None:
    policy = submission.SubmissionPollingPolicy(wait_timeout_seconds=5)
    outcome, _, clock = _poll(
        [
            ClientResult(error=ClientErrorKind.NETWORK),
            ClientResult(
                data=SubmissionCheck(
                    state="SUCCESS",
                    status_message="Wrong Answer",
                )
            ),
        ],
        policy,
    )

    assert outcome == SubmissionJudged(
        submission_id=123,
        status_message="Wrong Answer",
    )
    assert clock.sleeps == [0.5]


def test_submission_polling_retries_server_error_and_resets_error_count() -> None:
    policy = submission.SubmissionPollingPolicy(
        wait_timeout_seconds=5,
        max_consecutive_transient_errors=2,
    )
    outcome, _, clock = _poll(
        [
            ClientResult(error=ClientErrorKind.HTTP, status_code=503),
            ClientResult(data=SubmissionCheck(state="PENDING")),
            ClientResult(error=ClientErrorKind.TIMEOUT),
            ClientResult(error=ClientErrorKind.TIMEOUT),
            ClientResult(
                data=SubmissionCheck(
                    state="SUCCESS",
                    status_message="Accepted",
                )
            ),
        ],
        policy,
    )

    assert isinstance(outcome, SubmissionJudged)
    assert clock.sleeps == [0.5, 0.5, 0.5, 0.5]


def test_submission_polling_stops_after_transient_error_limit() -> None:
    policy = submission.SubmissionPollingPolicy(
        wait_timeout_seconds=5,
        max_consecutive_transient_errors=2,
    )
    outcome, _, clock = _poll(
        [
            ClientResult(error=ClientErrorKind.TIMEOUT),
            ClientResult(error=ClientErrorKind.TIMEOUT),
            ClientResult(error=ClientErrorKind.TIMEOUT),
        ],
        policy,
    )

    assert isinstance(outcome, SubmissionPollingFailed)
    assert outcome.submission_id == 123
    assert outcome.error_kind is ClientErrorKind.TIMEOUT
    assert clock.sleeps == [0.5, 0.5]


def test_submission_polling_honors_rate_limit_retry_after() -> None:
    policy = submission.SubmissionPollingPolicy(wait_timeout_seconds=5)
    outcome, _, clock = _poll(
        [
            ClientResult(
                error=ClientErrorKind.HTTP,
                status_code=429,
                retry_after_seconds=1.5,
            ),
            ClientResult(
                data=SubmissionCheck(
                    state="SUCCESS",
                    status_message="Accepted",
                )
            ),
        ],
        policy,
    )

    assert isinstance(outcome, SubmissionJudged)
    assert clock.sleeps == [1.5]


def test_submission_polling_does_not_retry_non_transient_http_error() -> None:
    policy = submission.SubmissionPollingPolicy(wait_timeout_seconds=5)
    outcome, _, clock = _poll(
        [ClientResult(error=ClientErrorKind.HTTP, status_code=401)],
        policy,
    )

    assert isinstance(outcome, SubmissionPollingFailed)
    assert outcome.error_kind is ClientErrorKind.HTTP
    assert clock.sleeps == []


def test_submission_polling_rejects_terminal_result_without_status() -> None:
    policy = submission.SubmissionPollingPolicy(wait_timeout_seconds=5)
    outcome, _, _ = _poll(
        [ClientResult(data=SubmissionCheck(state="SUCCESS"))],
        policy,
    )

    assert isinstance(outcome, SubmissionPollingFailed)
    assert outcome.error_kind is ClientErrorKind.INVALID_RESPONSE


@pytest.mark.parametrize("wait_timeout", (0, -1, float("nan"), float("inf")))
def test_submit_current_solution_rejects_invalid_wait_timeout(
    wait_timeout,
    app_paths,
) -> None:
    with pytest.raises(UseCaseError, match="判题等待时间"):
        submission.submit_current_solution(
            app_paths,
            wait_timeout_seconds=wait_timeout,
        )


def test_submit_current_solution_never_retries_failed_post(
    monkeypatch,
    app_paths,
) -> None:
    attempts = []

    class RejectSubmitClient(FakeClient):
        def submit_solution(
            self,
            title_slug: str,
            question_id: str,
            code: str,
        ) -> ClientResult:
            attempts.append((title_slug, question_id, code))
            return ClientResult(error=ClientErrorKind.TIMEOUT)

        def get_submission_result(
            self,
            submission_id: int,
            *,
            timeout: float,
        ) -> ClientResult:
            raise AssertionError("failed POST must not start polling")

    monkeypatch.setattr(submission, "load_cookies_from_session", lambda paths: {})
    monkeypatch.setattr(submission, "LeetCodeClient", RejectSubmitClient)
    monkeypatch.setattr(
        submission,
        "parse_solution_submission",
        lambda path: (
            ProblemMetadata("1", "1", "Two Sum", "two-sum"),
            "class Solution:\n    pass",
        ),
    )

    with pytest.raises(UseCaseError, match="请求超时"):
        submission.submit_current_solution(app_paths)

    assert attempts == [("two-sum", "1", "class Solution:\n    pass")]


@pytest.mark.parametrize(
    ("check", "expected"),
    (
        (SubmissionCheck(state="PENDING"), SubmissionPending(123)),
        (
            SubmissionCheck(
                state="SUCCESS",
                status_message="Accepted",
                runtime="4 ms",
                memory="17 MB",
            ),
            SubmissionJudged(
                submission_id=123,
                status_message="Accepted",
                runtime="4 ms",
                memory="17 MB",
            ),
        ),
    ),
)
def test_check_existing_submission_queries_once(
    monkeypatch,
    user_paths,
    check: SubmissionCheck,
    expected,
) -> None:
    requests = []

    class CheckClient(FakeClient):
        def get_submission_result(
            self,
            submission_id: int,
            *,
            timeout: float,
        ) -> ClientResult:
            requests.append((submission_id, timeout))
            return ClientResult(data=check)

    monkeypatch.setattr(submission, "load_cookies_from_session", lambda paths: {})
    monkeypatch.setattr(submission, "LeetCodeClient", CheckClient)

    result = submission.check_existing_submission(user_paths, 123)

    assert result == expected
    assert requests == [(123, 10)]


def test_check_existing_submission_preserves_id_on_request_failure(
    monkeypatch,
    user_paths,
) -> None:
    class FailedCheckClient(FakeClient):
        def get_submission_result(
            self,
            submission_id: int,
            *,
            timeout: float,
        ) -> ClientResult:
            return ClientResult(error=ClientErrorKind.NETWORK)

    monkeypatch.setattr(submission, "load_cookies_from_session", lambda paths: {})
    monkeypatch.setattr(submission, "LeetCodeClient", FailedCheckClient)

    result = submission.check_existing_submission(user_paths, 123)

    assert isinstance(result, SubmissionPollingFailed)
    assert result.submission_id == 123
    assert result.error_kind is ClientErrorKind.NETWORK


@pytest.mark.parametrize("submission_id", (0, -1, True))
def test_check_existing_submission_rejects_invalid_id(
    submission_id,
    user_paths,
) -> None:
    with pytest.raises(UseCaseError, match="Submission ID 必须是正整数"):
        submission.check_existing_submission(user_paths, submission_id)


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
    monkeypatch.setattr(
        diagnostics,
        "_diagnose_workspace",
        lambda paths, *, required: (_check("workspace"), app_paths.workspace),
    )
    received = []
    monkeypatch.setattr(
        diagnostics,
        "diagnose_solution",
        lambda path, *, run_solution=False: (
            received.append(run_solution) or _check("solution")
        ),
    )

    report = diagnostics.get_doctor_report(app_paths.user)

    assert received == [False]
    assert [check.name for check in report.checks] == [
        "session",
        "connectivity",
        "authentication",
        "workspace",
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
    monkeypatch.setattr(
        diagnostics,
        "_diagnose_workspace",
        lambda paths, *, required: (_check("workspace"), app_paths.workspace),
    )
    received = []
    monkeypatch.setattr(
        diagnostics,
        "diagnose_solution",
        lambda path, *, run_solution=False: (
            received.append(run_solution) or _check("solution")
        ),
    )

    diagnostics.get_doctor_report(app_paths.user, run_solution=True)

    assert received == [True]


def test_get_doctor_report_warns_and_skips_solution_without_workspace(
    monkeypatch,
    user_paths,
) -> None:
    class DoctorClient(FakeClient):
        def user_status(self) -> ClientResult:
            return ClientResult(data={"isSignedIn": True, "username": "learner"})

    monkeypatch.setattr(diagnostics, "load_session", lambda path: _session_data())
    monkeypatch.setattr(diagnostics, "LeetCodeClient", DoctorClient)
    monkeypatch.setattr(diagnostics, "diagnose_session", lambda path: _check("session"))
    monkeypatch.setattr(
        diagnostics,
        "diagnose_solution",
        lambda *args, **kwargs: pytest.fail("solution must be skipped"),
    )

    report = diagnostics.get_doctor_report(user_paths)

    checks = {check.name: check for check in report.checks}
    assert checks["workspace"].status is DoctorStatus.WARNING
    assert checks["solution"].status is DoctorStatus.WARNING
    assert report.ok


def test_get_doctor_report_requires_workspace_when_running_solution(
    monkeypatch,
    user_paths,
) -> None:
    class DoctorClient(FakeClient):
        def user_status(self) -> ClientResult:
            return ClientResult(data={"isSignedIn": True, "username": "learner"})

    monkeypatch.setattr(diagnostics, "load_session", lambda path: _session_data())
    monkeypatch.setattr(diagnostics, "LeetCodeClient", DoctorClient)
    monkeypatch.setattr(diagnostics, "diagnose_session", lambda path: _check("session"))

    report = diagnostics.get_doctor_report(user_paths, run_solution=True)

    checks = {check.name: check for check in report.checks}
    assert checks["workspace"].status is DoctorStatus.FAIL
    assert not report.ok
