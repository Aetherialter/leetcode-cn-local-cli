from leetcode_local_cli.commands import common
from leetcode_local_cli.commands.rendering import (
    loading,
    render_problem_detail,
    render_problem_list,
    success,
    warning,
)
from leetcode_local_cli.use_cases.errors import UseCaseError
from leetcode_local_cli.use_cases.problems import (
    get_problem_detail_by_question_id,
    get_problem_summaries,
    write_problem_solution,
)
from leetcode_local_cli.use_cases.settings import get_editor


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


def solve(question_id: str, no_open: bool = False, editor: str | None = None) -> None:
    try:
        paths = common.require_app_paths()
        selected_editor = None if no_open else get_editor(paths.user, editor)
        problem_detail = get_problem_detail_by_question_id(
            paths.user,
            question_id,
            progress=loading,
        )
    except UseCaseError as exc:
        common.exit_for_use_case_error(exc)
    render_problem_detail(problem_detail)
    try:
        result = write_problem_solution(
            paths.workspace,
            problem_detail,
            open_editor=not no_open,
            editor=selected_editor,
        )
        success(f"解法已保存：{result.path}")
        if result.open_warning:
            warning(result.open_warning)
    except UseCaseError as exc:
        common.exit_for_use_case_error(exc)
