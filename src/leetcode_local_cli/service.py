from time import sleep

from typer import Exit

from leetcode_local_cli.auth import (
    REQUIRED_COOKIE_NAMES,
    SessionFileError,
    load_session,
)
from leetcode_local_cli.client import ClientErrorKind, LeetCodeClient
from leetcode_local_cli.doctor import (
    DoctorReport,
    DoctorStatus,
    diagnose_remote,
    diagnose_session,
    diagnose_solution,
)
from leetcode_local_cli.problem import (
    ProblemDetail,
    ProblemSummary,
    find_problem_by_id,
    normalize_problem_detail,
    normalize_problem_summaries,
    parse_question_id,
)
from leetcode_local_cli.paths import AppPaths
from leetcode_local_cli.ui import error, loading, render_submission_target, warning
from leetcode_local_cli.workspace import WorkspaceError, parse_solution_submission


MAX_ATTEMPTS = 10


def client_error_message(kind: ClientErrorKind | None) -> str:
    match kind:
        case ClientErrorKind.NETWORK:
            return "网络请求失败，请检查网络连接"

        case ClientErrorKind.HTTP:
            return "LeetCode 接口返回异常，请稍后重试"

        case ClientErrorKind.INVALID_JSON:
            return "LeetCode 返回内容无法解析，请稍后重试"

        case ClientErrorKind.INVALID_RESPONSE:
            return "LeetCode 接口数据结构异常，可能是接口变更"

        case ClientErrorKind.UNAUTHORIZED:
            return "登录态无效或已过期，请重新执行 lc login"

        case ClientErrorKind.MISSING_CSRF:
            return "缺少提交凭证 csrftoken，请重新执行 lc login"

        case _:
            return "未知客户端错误"


def _load_cookies_from_session(paths: AppPaths) -> dict[str, str]:
    session_check = diagnose_session(paths.session_file)
    if session_check.status is DoctorStatus.FAIL:
        error(session_check.message)
        if session_check.suggestion:
            warning(session_check.suggestion)
        raise Exit(1)
    try:
        session = load_session(paths.session_file)
    except SessionFileError as exc:
        error(str(exc))
        raise Exit(1)
    if not isinstance(session, dict):
        warning("未找到有效登录态，请先执行 lc login")
        raise Exit(1)
    cookies = session.get("cookies")
    if not isinstance(cookies, dict):
        error("Session 文件结构无效，请重新执行 lc login")
        raise Exit(1)
    valid_cookies: dict[str, str] = {}
    for name in REQUIRED_COOKIE_NAMES:
        value = cookies.get(name)
        if not isinstance(value, str) or not value:
            error(f"缺少或无效的 Cookie：{name}")
            warning("请重新执行 lc login")
            raise Exit(1)
        valid_cookies[name] = value
    return valid_cookies


def _parse_question_id_or_exit(question_id: str) -> str:
    parse_result = parse_question_id(question_id)
    parsed_question_id = parse_result.question_id
    if not parse_result.ok or parsed_question_id is None:
        error(parse_result.error_message or "题号解析失败")
        raise Exit(1)
    return parsed_question_id


def _find_problem_summary_by_question_id_online(
    client: LeetCodeClient,
    question_id: str,
) -> ProblemSummary:
    limit, skip = 100, 0
    while True:
        problem_list_data = client.problem_list(limit=limit, skip=skip)
        if not problem_list_data.ok:
            error(client_error_message(problem_list_data.error))
            raise Exit(1)
        problem_list = problem_list_data.data
        if not isinstance(problem_list, dict):
            error(client_error_message(ClientErrorKind.INVALID_RESPONSE))
            raise Exit(1)
        questions = problem_list.get("questions", [])
        problem_summaries = normalize_problem_summaries(questions)
        problem_summary = find_problem_by_id(problem_summaries, question_id)
        if problem_summary:
            return problem_summary
        skip += limit
        total = problem_list.get("total") or 0
        if not questions or skip >= total:
            error(f"未找到题号 {question_id}")
            raise Exit(1)


def _validate_show_options(limit: int, skip: int) -> None:
    if limit <= 0:
        error("limit 必须是正整数")
        raise Exit(1)
    if limit > 100:
        error("limit 超过单次查询上限，最大为 100")
        raise Exit(1)
    if skip < 0:
        error("skip 必须是非负整数")
        raise Exit(1)


def get_user_status(paths: AppPaths) -> dict:
    cookies = _load_cookies_from_session(paths)
    with LeetCodeClient(cookies) as client:
        user_status = client.user_status()
    if not user_status.ok:
        error(client_error_message(user_status.error))
        raise Exit(1)
    status = user_status.data
    if not isinstance(status, dict) or not status.get("isSignedIn"):
        error(client_error_message(ClientErrorKind.UNAUTHORIZED))
        raise Exit(1)
    return user_status.data


def get_account_profile(paths: AppPaths) -> dict:
    cookies = _load_cookies_from_session(paths)
    with LeetCodeClient(cookies) as client:
        with loading("正在获取账户信息..."):
            account_profile = client.account_profile()
    if not account_profile.ok:
        error(client_error_message(account_profile.error))
        raise Exit(1)
    if not isinstance(account_profile.data, dict):
        error(client_error_message(ClientErrorKind.INVALID_RESPONSE))
        raise Exit(1)
    return account_profile.data


def get_problem_summaries(
    paths: AppPaths,
    limit: int = 50,
    skip: int = 0,
) -> list[ProblemSummary]:
    _validate_show_options(limit, skip)
    cookies = _load_cookies_from_session(paths)
    with LeetCodeClient(cookies) as client:
        with loading("正在获取题目索引..."):
            problem_list_data = client.problem_list(limit=limit, skip=skip)
    if not problem_list_data.ok:
        error(client_error_message(problem_list_data.error))
        raise Exit(1)
    problem_list = problem_list_data.data
    if not isinstance(problem_list, dict):
        error(client_error_message(ClientErrorKind.INVALID_RESPONSE))
        raise Exit(1)
    questions = problem_list.get("questions", [])

    if not isinstance(questions, list):
        error("题目获取失败")
        raise Exit(1)
    return normalize_problem_summaries(questions)


def get_problem_detail_by_question_id(
    paths: AppPaths,
    question_id: str,
) -> ProblemDetail:
    normalized_question_id = _parse_question_id_or_exit(question_id)
    cookies = _load_cookies_from_session(paths)
    with LeetCodeClient(cookies) as client:
        with loading("正在获取题目索引..."):
            problem_summary = _find_problem_summary_by_question_id_online(
                client,
                normalized_question_id,
            )
        with loading("正在获取题目详情..."):
            problem_detail_data = client.problem_detail(problem_summary.title_slug)
        if not problem_detail_data.ok:
            error(client_error_message(problem_detail_data.error))
            raise Exit(1)
        if not isinstance(problem_detail_data.data, dict):
            error(client_error_message(ClientErrorKind.INVALID_RESPONSE))
            raise Exit(1)
        problem_detail = normalize_problem_detail(problem_detail_data.data)
    return problem_detail


def get_doctor_report(
    paths: AppPaths,
    *,
    run_solution: bool = False,
) -> DoctorReport:
    session_check = diagnose_session(paths.session_file)
    solution_check = diagnose_solution(
        paths.solution_file,
        run_solution=run_solution,
    )

    cookies: dict[str, str] | None = None
    try:
        session = load_session(paths.session_file)
    except SessionFileError:
        session = None
    if isinstance(session, dict):
        raw_cookies = session.get("cookies")
        if isinstance(raw_cookies, dict):
            valid_cookies: dict[str, str] = {}
            for name in REQUIRED_COOKIE_NAMES:
                value = raw_cookies.get(name)
                if not isinstance(value, str) or not value:
                    break
                valid_cookies[name] = value
            else:
                cookies = valid_cookies

    with LeetCodeClient(cookies) as client:
        remote_result = client.user_status()
    connectivity_check, authentication_check = diagnose_remote(remote_result)
    return DoctorReport(
        checks=(
            session_check,
            connectivity_check,
            authentication_check,
            solution_check,
        )
    )


def submit_current_solution(paths: AppPaths) -> dict | None:
    try:
        metadata, code = parse_solution_submission(paths.solution_file)
        submit_question_id, title_slug = (
            metadata.submit_question_id,
            metadata.title_slug,
        )
    except WorkspaceError as exc:
        error(str(exc))
        raise Exit(1)
    render_submission_target(metadata)
    cookies = _load_cookies_from_session(paths)
    with LeetCodeClient(cookies) as client:
        submission_id = client.submit_solution(title_slug, submit_question_id, code)
        if not submission_id.ok:
            error(client_error_message(submission_id.error))
            raise Exit(1)

        for _ in range(MAX_ATTEMPTS):
            result = client.get_submission_result(submission_id.data)
            if not result.ok:
                error(client_error_message(result.error))
                raise Exit(1)
            result_data = result.data
            if not isinstance(result_data, dict):
                error(client_error_message(ClientErrorKind.INVALID_RESPONSE))
                raise Exit(1)
            state = result_data.get("state")
            if state not in {"PENDING", "STARTED"}:
                return result_data
            sleep(0.5)
    return None
