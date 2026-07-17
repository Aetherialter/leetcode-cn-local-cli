from typer import Typer, Exit
from aether_lc.auth import (
    SessionFileError,
    get_cookies_from_browser,
    get_cookies_from_input,
    save_session,
)
from aether_lc.client import ClientErrorKind, LeetCodeClient
from aether_lc.ui import (
    loading,
    render_doctor_report,
    render_submission_result,
    success,
    warning,
    error,
    render_profile,
    render_problem_detail,
    render_problem_list,
)
from aether_lc.service import (
    client_error_message,
    get_account_profile,
    get_doctor_report,
    get_problem_detail_by_question_id,
    get_problem_summaries,
    get_user_status,
    submit_current_solution,
)
from aether_lc.workspace import (
    ProblemMetadata,
    SolutionFileStatus,
    inspect_solution_file,
    run_solution_file,
    write_solution_file,
)

app = Typer(help="力扣中文站本地化刷题 CLI 工具")


@app.command()
def login() -> None:
    with loading("正在读取浏览器 Cookie..."):
        browser_result = get_cookies_from_browser()
    if not browser_result:
        warning("未从浏览器读取到 Cookie，请手动粘贴")
        source, cookies = "manual", get_cookies_from_input()
    else:
        source, cookies = browser_result
    if not cookies:
        warning("未获取有效 Cookie")
        raise Exit(1)
    with LeetCodeClient(cookies) as client:
        status_result = client.user_status()
        status = status_result.data
        if not status_result.ok:
            error(client_error_message(status_result.error))
            raise Exit(1)
        if isinstance(status, dict) and status.get("isSignedIn"):
            username = status.get("username")
            if not isinstance(username, str) or not username:
                error(client_error_message(ClientErrorKind.INVALID_RESPONSE))
                raise Exit(1)
            try:
                save_session(
                    {
                        "site": "leetcode.cn",
                        "source": source,
                        "username": username,
                        "cookies": cookies,
                    }
                )
            except SessionFileError as exc:
                error(str(exc))
                raise Exit(1)
            success("成功登录")
        else:
            warning("Cookie 无效或已过期")
            raise Exit(1)


@app.command()
def status() -> None:
    user_status = get_user_status()
    username = user_status.get("username", "未知用户")
    success(f"在线状态: 当前账号 {username}")


@app.command()
def profile() -> None:
    account_profile = get_account_profile()
    render_profile(account_profile)


@app.command()
def get(question_id: str) -> None:
    problem_detail = get_problem_detail_by_question_id(question_id)
    render_problem_detail(problem_detail)


@app.command()
def show(limit: int = 50, skip: int = 0) -> None:
    problem_summaries = get_problem_summaries(limit=limit, skip=skip)
    render_problem_list(problem_summaries)


@app.command()
def solve(question_id: str) -> None:
    problem_detail = get_problem_detail_by_question_id(question_id)
    render_problem_detail(problem_detail)
    if not problem_detail.python_code:
        error("题目未提供 Python3 代码模板，无法生成 solution.py")
        raise Exit(1)
    if (
        not problem_detail.question_id
        or not problem_detail.submit_question_id
        or not problem_detail.title
        or not problem_detail.title_slug
    ):
        error("题目元信息不完整，无法生成可提交的 solution.py")
        raise Exit(1)
    write_solution_file(
        problem_detail.python_code,
        ProblemMetadata(
            problem_id=problem_detail.question_id,
            submit_question_id=problem_detail.submit_question_id,
            title=problem_detail.title,
            title_slug=problem_detail.title_slug,
        ),
    )


@app.command()
def test() -> None:
    inspection = inspect_solution_file()
    match inspection.status:
        case SolutionFileStatus.MISSING:
            error("未找到 solution.py，请先执行 lc solve <题号>")
            raise Exit(1)
        case SolutionFileStatus.EMPTY:
            error("solution.py 当前为空，请先执行 lc solve <题号>")
            raise Exit(1)
        case SolutionFileStatus.READ_ERROR:
            error("无法读取 solution.py，请检查文件权限")
            raise Exit(1)
        case SolutionFileStatus.INVALID_SYNTAX:
            line = (
                f"第 {inspection.syntax_line} 行"
                if inspection.syntax_line
                else "未知行"
            )
            error(f"solution.py 存在 Python 语法错误（{line}）")
            raise Exit(1)

    result = run_solution_file()
    if result.returncode:
        error("本地测试失败")
        raise Exit(result.returncode)
    success("本地测试通过")


@app.command()
def doctor() -> None:
    with loading("正在检查本地环境与 LeetCode 连接..."):
        report = get_doctor_report()
    render_doctor_report(report)
    if not report.ok:
        raise Exit(1)


@app.command()
def submit() -> None:
    result = submit_current_solution()
    render_submission_result(result)


if __name__ == "__main__":
    app()
