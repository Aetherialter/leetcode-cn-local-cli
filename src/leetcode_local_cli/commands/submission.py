from typer import Exit

from leetcode_local_cli.commands import common
from leetcode_local_cli.ui import render_submission_result, render_submission_target
from leetcode_local_cli.use_cases.common import UseCaseError
from leetcode_local_cli.use_cases.submission import submit_current_solution


def submit() -> None:
    try:
        result = submit_current_solution(
            common.require_app_paths(),
            on_target=render_submission_target,
        )
    except UseCaseError as exc:
        common.exit_for_use_case_error(exc)
    render_submission_result(result)
    if result is None or result.get("status_msg") != "Accepted":
        raise Exit(1)
