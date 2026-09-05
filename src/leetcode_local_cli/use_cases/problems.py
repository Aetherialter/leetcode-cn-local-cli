from dataclasses import dataclass
from pathlib import Path

from leetcode_local_cli.integrations.editor import EditorError, open_path
from leetcode_local_cli.integrations.leetcode import LeetCodeClient
from leetcode_local_cli.models.problem import (
    ProblemDetail,
    ProblemSummary,
    find_problem_by_id,
    parse_question_id,
)
from leetcode_local_cli.models.result import ClientFailure
from leetcode_local_cli.models.solution import ProblemMetadata, WorkspaceError
from leetcode_local_cli.storage.paths import UserPaths, WorkspacePaths
from leetcode_local_cli.storage.solution import write_solution_file
from leetcode_local_cli.use_cases.common import (
    Progress,
    client_error_message,
    load_cookies_from_session,
    no_progress,
)
from leetcode_local_cli.use_cases.errors import ErrorCode, UseCaseError


def _parse_question_id(question_id: str) -> str:
    parse_result = parse_question_id(question_id)
    parsed_question_id = parse_result.question_id
    if not parse_result.ok or parsed_question_id is None:
        raise UseCaseError(parse_result.error_message or "题号解析失败")
    return parsed_question_id


def _find_problem_summary_by_question_id_online(
    client: LeetCodeClient,
    question_id: str,
) -> ProblemSummary:
    limit, skip = 100, 0
    while True:
        problem_list_data = client.problem_list(limit=limit, skip=skip)
        if isinstance(problem_list_data, ClientFailure):
            raise UseCaseError(
                client_error_message(problem_list_data.error), code=ErrorCode.CLIENT
            )
        page = problem_list_data.data
        problem_summary = find_problem_by_id(page.questions, question_id)
        if problem_summary:
            return problem_summary
        skip += limit
        if not page.questions or skip >= page.total:
            raise UseCaseError(f"未找到题号 {question_id}")


def _validate_show_options(limit: int, skip: int) -> None:
    if limit <= 0:
        raise UseCaseError("limit 必须是正整数")
    if limit > 100:
        raise UseCaseError("limit 超过单次查询上限，最大为 100")
    if skip < 0:
        raise UseCaseError("skip 必须是非负整数")


def get_problem_summaries(
    paths: UserPaths,
    limit: int = 50,
    skip: int = 0,
    *,
    progress: Progress = no_progress,
) -> tuple[ProblemSummary, ...]:
    _validate_show_options(limit, skip)
    cookies = load_cookies_from_session(paths)
    with LeetCodeClient(cookies) as client:
        with progress("正在获取题目索引..."):
            problem_list_data = client.problem_list(limit=limit, skip=skip)
    if isinstance(problem_list_data, ClientFailure):
        raise UseCaseError(
            client_error_message(problem_list_data.error), code=ErrorCode.CLIENT
        )
    return problem_list_data.data.questions


def get_problem_detail_by_question_id(
    paths: UserPaths,
    question_id: str,
    *,
    progress: Progress = no_progress,
) -> ProblemDetail:
    normalized_question_id = _parse_question_id(question_id)
    cookies = load_cookies_from_session(paths)
    with LeetCodeClient(cookies) as client:
        with progress("正在获取题目索引..."):
            problem_summary = _find_problem_summary_by_question_id_online(
                client,
                normalized_question_id,
            )
        with progress("正在获取题目详情..."):
            problem_detail_data = client.problem_detail(problem_summary.title_slug)
        if isinstance(problem_detail_data, ClientFailure):
            raise UseCaseError(
                client_error_message(problem_detail_data.error), code=ErrorCode.CLIENT
            )
        return problem_detail_data.data


@dataclass(frozen=True)
class SolveResult:
    path: Path
    open_warning: str | None = None


def write_problem_solution(
    paths: WorkspacePaths, problem: ProblemDetail, *, open_editor: bool = True
) -> SolveResult:
    if not problem.python_code:
        raise UseCaseError(
            "题目未提供 Python3 代码模板，无法生成 solution.py", code=ErrorCode.SOLUTION
        )
    if (
        not problem.question_id
        or not problem.submit_question_id
        or not problem.title
        or not problem.title_slug
    ):
        raise UseCaseError(
            "题目元信息不完整，无法生成可提交的 solution.py", code=ErrorCode.SOLUTION
        )
    try:
        write_solution_file(
            paths.solution_file,
            problem.python_code,
            ProblemMetadata(
                problem_id=problem.question_id,
                submit_question_id=problem.submit_question_id,
                title=problem.title,
                title_slug=problem.title_slug,
            ),
        )
    except WorkspaceError as exc:
        raise UseCaseError(str(exc), code=ErrorCode.SOLUTION) from exc
    if open_editor:
        try:
            open_path(paths.solution_file)
        except EditorError as exc:
            return SolveResult(paths.solution_file, str(exc))
    return SolveResult(paths.solution_file)
