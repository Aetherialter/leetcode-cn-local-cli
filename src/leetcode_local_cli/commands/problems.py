from leetcode_local_cli.commands import common
from leetcode_local_cli.ui import (
    loading,
    render_problem_detail,
    render_problem_list,
)
from leetcode_local_cli.use_cases.common import UseCaseError
from leetcode_local_cli.use_cases.problems import (
    get_problem_detail_by_question_id,
    get_problem_summaries,
    write_problem_solution,
)


def get_problem(question_id: str) -> None:
    try:
        problem_detail = get_problem_detail_by_question_id(
            common.get_user_paths(),
            question_id,
            progress=loading,
        )
    except UseCaseError as exc:
        common.exit_for_use_case_error(exc)
    render_problem_detail(problem_detail)


def show(limit: int = 50, skip: int = 0) -> None:
    try:
        problem_summaries = get_problem_summaries(
            common.get_user_paths(),
            limit=limit,
            skip=skip,
            progress=loading,
        )
    except UseCaseError as exc:
        common.exit_for_use_case_error(exc)
    render_problem_list(problem_summaries)


def solve(question_id: str) -> None:
    paths = common.require_app_paths()
    try:
        problem_detail = get_problem_detail_by_question_id(
            paths.user,
            question_id,
            progress=loading,
        )
    except UseCaseError as exc:
        common.exit_for_use_case_error(exc)
    render_problem_detail(problem_detail)
    try:
        write_problem_solution(paths.workspace, problem_detail)
    except UseCaseError as exc:
        common.exit_for_use_case_error(exc)
