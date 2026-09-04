from collections.abc import Callable
from dataclasses import dataclass
import math
from time import monotonic, sleep

from leetcode_local_cli.client import ClientErrorKind, ClientResult, LeetCodeClient
from leetcode_local_cli.paths import AppPaths, UserPaths
from leetcode_local_cli.submission import (
    SubmissionCheck,
    SubmissionJudged,
    SubmissionOutcome,
    SubmissionPending,
    SubmissionPollingFailed,
    SubmissionTimedOut,
)
from leetcode_local_cli.use_cases.common import (
    UseCaseError,
    client_error_message,
    load_cookies_from_session,
)
from leetcode_local_cli.workspace import (
    ProblemMetadata,
    WorkspaceError,
    parse_solution_submission,
)


DEFAULT_SUBMISSION_WAIT_TIMEOUT_SECONDS = 30.0
DEFAULT_SUBMISSION_POLL_INTERVAL_SECONDS = 0.5
DEFAULT_SUBMISSION_REQUEST_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_CONSECUTIVE_TRANSIENT_ERRORS = 2


@dataclass(frozen=True)
class SubmissionPollingPolicy:
    wait_timeout_seconds: float = DEFAULT_SUBMISSION_WAIT_TIMEOUT_SECONDS
    poll_interval_seconds: float = DEFAULT_SUBMISSION_POLL_INTERVAL_SECONDS
    request_timeout_seconds: float = DEFAULT_SUBMISSION_REQUEST_TIMEOUT_SECONDS
    max_consecutive_transient_errors: int = DEFAULT_MAX_CONSECUTIVE_TRANSIENT_ERRORS


def submit_current_solution(
    paths: AppPaths,
    *,
    wait_timeout_seconds: float = DEFAULT_SUBMISSION_WAIT_TIMEOUT_SECONDS,
    on_target: Callable[[ProblemMetadata], None] | None = None,
    on_submitted: Callable[[int], None] | None = None,
) -> SubmissionOutcome:
    policy = SubmissionPollingPolicy(wait_timeout_seconds=wait_timeout_seconds)
    _validate_polling_policy(policy)
    try:
        metadata, code = parse_solution_submission(paths.workspace.solution_file)
    except WorkspaceError as exc:
        raise UseCaseError(str(exc)) from exc
    if on_target is not None:
        on_target(metadata)
    cookies = load_cookies_from_session(paths.user)
    with LeetCodeClient(cookies) as client:
        submission_result = client.submit_solution(
            metadata.title_slug,
            metadata.submit_question_id,
            code,
        )
        if not submission_result.ok:
            raise UseCaseError(client_error_message(submission_result.error))
        submission_id = submission_result.data
        if not isinstance(submission_id, int) or isinstance(submission_id, bool):
            raise UseCaseError(client_error_message(ClientErrorKind.INVALID_RESPONSE))
        if on_submitted is not None:
            on_submitted(submission_id)
        return _poll_submission(client, submission_id, policy)


def check_existing_submission(
    paths: UserPaths,
    submission_id: int,
) -> SubmissionOutcome:
    if (
        not isinstance(submission_id, int)
        or isinstance(submission_id, bool)
        or submission_id <= 0
    ):
        raise UseCaseError("Submission ID 必须是正整数")
    cookies = load_cookies_from_session(paths)
    with LeetCodeClient(cookies) as client:
        result = client.get_submission_result(
            submission_id,
            timeout=DEFAULT_SUBMISSION_REQUEST_TIMEOUT_SECONDS,
        )
    if not result.ok:
        return _polling_failure(submission_id, result.error)
    check = result.data
    if not isinstance(check, SubmissionCheck):
        return _polling_failure(submission_id, ClientErrorKind.INVALID_RESPONSE)
    return _outcome_from_check(submission_id, check)


def _validate_polling_policy(policy: SubmissionPollingPolicy) -> None:
    if (
        not math.isfinite(policy.wait_timeout_seconds)
        or policy.wait_timeout_seconds <= 0
    ):
        raise UseCaseError("判题等待时间必须是大于 0 的有限秒数")
    if (
        not math.isfinite(policy.poll_interval_seconds)
        or policy.poll_interval_seconds <= 0
    ):
        raise UseCaseError("判题轮询间隔必须是大于 0 的有限秒数")
    if (
        not math.isfinite(policy.request_timeout_seconds)
        or policy.request_timeout_seconds <= 0
    ):
        raise UseCaseError("判题请求超时必须是大于 0 的有限秒数")
    if policy.max_consecutive_transient_errors < 0:
        raise UseCaseError("判题临时错误重试次数不能为负数")


def _poll_submission(
    client: LeetCodeClient,
    submission_id: int,
    policy: SubmissionPollingPolicy,
    *,
    clock: Callable[[], float] = monotonic,
    sleeper: Callable[[float], None] = sleep,
) -> SubmissionOutcome:
    deadline = clock() + policy.wait_timeout_seconds
    consecutive_transient_errors = 0

    while True:
        remaining = deadline - clock()
        if remaining <= 0:
            return SubmissionTimedOut(
                submission_id=submission_id,
                waited_seconds=policy.wait_timeout_seconds,
            )
        result = client.get_submission_result(
            submission_id,
            timeout=min(policy.request_timeout_seconds, remaining),
        )
        if not result.ok:
            if deadline - clock() <= 0:
                return SubmissionTimedOut(
                    submission_id=submission_id,
                    waited_seconds=policy.wait_timeout_seconds,
                )
            retry_delay = _transient_retry_delay(result, policy)
            if retry_delay is None:
                return _polling_failure(submission_id, result.error)
            consecutive_transient_errors += 1
            if consecutive_transient_errors > policy.max_consecutive_transient_errors:
                return _polling_failure(submission_id, result.error)
            _sleep_with_deadline(
                retry_delay,
                deadline=deadline,
                clock=clock,
                sleeper=sleeper,
            )
            continue

        check = result.data
        if not isinstance(check, SubmissionCheck):
            return _polling_failure(
                submission_id,
                ClientErrorKind.INVALID_RESPONSE,
            )
        if check.pending:
            consecutive_transient_errors = 0
            _sleep_with_deadline(
                policy.poll_interval_seconds,
                deadline=deadline,
                clock=clock,
                sleeper=sleeper,
            )
            continue
        return _outcome_from_check(submission_id, check)


def _outcome_from_check(
    submission_id: int,
    check: SubmissionCheck,
) -> SubmissionOutcome:
    if check.pending:
        return SubmissionPending(submission_id=submission_id)
    if check.status_message is None:
        return _polling_failure(
            submission_id,
            ClientErrorKind.INVALID_RESPONSE,
        )
    return SubmissionJudged(
        submission_id=submission_id,
        status_message=check.status_message,
        runtime=check.runtime,
        memory=check.memory,
        total_correct=check.total_correct,
        total_testcases=check.total_testcases,
    )


def _transient_retry_delay(
    result: ClientResult,
    policy: SubmissionPollingPolicy,
) -> float | None:
    if result.error in {ClientErrorKind.TIMEOUT, ClientErrorKind.NETWORK}:
        return policy.poll_interval_seconds
    if result.error is not ClientErrorKind.HTTP:
        return None
    if result.status_code == 429:
        if result.retry_after_seconds is not None:
            return result.retry_after_seconds
        return policy.poll_interval_seconds
    if result.status_code is not None and 500 <= result.status_code <= 599:
        return policy.poll_interval_seconds
    return None


def _sleep_with_deadline(
    delay: float,
    *,
    deadline: float,
    clock: Callable[[], float],
    sleeper: Callable[[float], None],
) -> None:
    remaining = deadline - clock()
    if remaining > 0:
        sleeper(min(delay, remaining))


def _polling_failure(
    submission_id: int,
    error_kind: ClientErrorKind | None,
) -> SubmissionPollingFailed:
    normalized_kind = error_kind or ClientErrorKind.INVALID_RESPONSE
    return SubmissionPollingFailed(
        submission_id=submission_id,
        error_kind=normalized_kind,
        message=client_error_message(normalized_kind),
    )
