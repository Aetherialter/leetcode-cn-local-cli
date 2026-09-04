import math
from typing import Annotated

from typer import Argument, BadParameter, Exit, Option

from leetcode_local_cli.commands import common
from leetcode_local_cli.submission import SubmissionJudged
from leetcode_local_cli.ui import (
    render_submission_result,
    render_submission_submitted,
    render_submission_target,
)
from leetcode_local_cli.use_cases.common import UseCaseError
from leetcode_local_cli.use_cases.submission import (
    DEFAULT_SUBMISSION_WAIT_TIMEOUT_SECONDS,
    check_existing_submission,
    submit_current_solution,
)


def submit(
    wait_timeout: Annotated[
        float,
        Option(
            "--wait-timeout",
            help="取得 submission ID 后等待判题的总秒数",
        ),
    ] = DEFAULT_SUBMISSION_WAIT_TIMEOUT_SECONDS,
) -> None:
    if not math.isfinite(wait_timeout) or wait_timeout <= 0:
        raise BadParameter(
            "必须是大于 0 的有限秒数",
            param_hint="--wait-timeout",
        )
    try:
        result = submit_current_solution(
            common.require_app_paths(),
            wait_timeout_seconds=wait_timeout,
            on_target=render_submission_target,
            on_submitted=lambda submission_id: render_submission_submitted(
                submission_id,
                wait_timeout_seconds=wait_timeout,
            ),
        )
    except UseCaseError as exc:
        common.exit_for_use_case_error(exc)
    render_submission_result(result)
    if not isinstance(result, SubmissionJudged) or not result.accepted:
        raise Exit(1)


def check(
    submission_id: Annotated[
        int,
        Argument(help="要查询的 Submission ID"),
    ],
) -> None:
    if submission_id <= 0:
        raise BadParameter(
            "必须是正整数",
            param_hint="submission-id",
        )
    try:
        result = check_existing_submission(
            common.get_user_paths(),
            submission_id,
        )
    except UseCaseError as exc:
        common.exit_for_use_case_error(exc)
    render_submission_result(result)
    if not isinstance(result, SubmissionJudged) or not result.accepted:
        raise Exit(1)
