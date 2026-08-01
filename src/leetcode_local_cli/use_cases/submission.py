from collections.abc import Callable
from time import sleep
from typing import Any

from leetcode_local_cli.client import ClientErrorKind, LeetCodeClient
from leetcode_local_cli.paths import AppPaths
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


MAX_ATTEMPTS = 10


def submit_current_solution(
    paths: AppPaths,
    *,
    on_target: Callable[[ProblemMetadata], None] | None = None,
) -> dict[str, Any] | None:
    try:
        metadata, code = parse_solution_submission(paths.solution_file)
    except WorkspaceError as exc:
        raise UseCaseError(str(exc)) from exc
    if on_target is not None:
        on_target(metadata)
    cookies = load_cookies_from_session(paths)
    with LeetCodeClient(cookies) as client:
        submission_id = client.submit_solution(
            metadata.title_slug,
            metadata.submit_question_id,
            code,
        )
        if not submission_id.ok:
            raise UseCaseError(client_error_message(submission_id.error))

        for _ in range(MAX_ATTEMPTS):
            result = client.get_submission_result(submission_id.data)
            if not result.ok:
                raise UseCaseError(client_error_message(result.error))
            result_data = result.data
            if not isinstance(result_data, dict):
                raise UseCaseError(
                    client_error_message(ClientErrorKind.INVALID_RESPONSE)
                )
            state = result_data.get("state")
            if state not in {"PENDING", "STARTED"}:
                return result_data
            sleep(0.5)
    return None
