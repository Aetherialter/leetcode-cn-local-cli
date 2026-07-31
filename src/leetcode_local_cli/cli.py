import math
import sys
from pathlib import Path
from typing import Annotated

from typer import Argument, BadParameter, Exit, Option, Typer, confirm, echo, prompt

from leetcode_local_cli.auth import (
    SessionFileError,
    get_cookies_from_browser,
    get_cookies_from_input,
    save_session,
)
from leetcode_local_cli.client import ClientErrorKind, LeetCodeClient
from leetcode_local_cli.config import (
    ConfigError,
    initialize_workspace,
    load_user_config,
    resolve_app_paths,
)
from leetcode_local_cli.paths import (
    APP_DIRECTORY_NAME,
    AppPaths,
    get_user_config_file,
    normalize_workspace_path,
)
from leetcode_local_cli.ui import (
    info,
    loading,
    render_doctor_report,
    render_local_test_output,
    render_submission_result,
    success,
    warning,
    error,
    render_profile,
    render_problem_detail,
    render_problem_list,
)
from leetcode_local_cli.service import (
    client_error_message,
    get_account_profile,
    get_doctor_report,
    get_problem_detail_by_question_id,
    get_problem_summaries,
    get_user_status,
    submit_current_solution,
)
from leetcode_local_cli.workspace import (
    LocalTestStatus,
    ProblemMetadata,
    SolutionFileStatus,
    WorkspaceError,
    inspect_solution_file,
    run_local_tests,
    write_solution_file,
)
from leetcode_local_cli.version import PACKAGE_NAME, get_version

app = Typer(help="力扣中文站本地化刷题 CLI 工具", no_args_is_help=True)


def _configure_utf8_output() -> None:
    """Keep localized CLI output writable when Windows redirects the streams."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="backslashreplace")


def run() -> None:
    """Run the command-line application with deterministic UTF-8 output."""
    _configure_utf8_output()
    app()


def _version_callback(value: bool) -> None:
    if value:
        echo(f"{PACKAGE_NAME} {get_version()}")
        raise Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="显示版本并退出",
        ),
    ] = False,
) -> None:
    """力扣中文站本地化刷题 CLI 工具。"""


def _require_app_paths() -> AppPaths:
    try:
        return resolve_app_paths()
    except ConfigError as exc:
        error(str(exc))
        raise Exit(1) from exc


@app.command("init")
def init_workspace(
    path: Annotated[
        Path | None,
        Argument(help="工作区完整路径；省略时交互输入父目录"),
    ] = None,
    yes: Annotated[
        bool,
        Option("--yes", help="使用显式路径初始化并跳过交互确认"),
    ] = False,
) -> None:
    """配置默认工作区，并安全创建工作区基础文件。"""
    config_file = get_user_config_file()
    if path is None:
        try:
            existing_config = load_user_config(config_file)
            if existing_config is not None:
                existing_paths = resolve_app_paths(config_file)
                success(f"继续使用现有工作区：{existing_paths.workspace_root}")
                return
        except ConfigError as exc:
            error(str(exc))
            raise Exit(1) from exc

        if yes:
            error("--yes 必须与工作区完整路径一起使用")
            raise Exit(1)
        parent_value = prompt("请输入工作区父目录").strip()
        if not parent_value:
            error("工作区父目录不能为空")
            raise Exit(1)
        workspace_root = normalize_workspace_path(parent_value) / APP_DIRECTORY_NAME
    else:
        workspace_root = normalize_workspace_path(path)

    info(f"工作区将配置为：{workspace_root}")
    if not yes and not confirm("确认继续？"):
        warning("已取消工作区配置")
        return

    try:
        result = initialize_workspace(
            workspace_root,
            user_config_file=config_file,
        )
    except ConfigError as exc:
        error(str(exc))
        raise Exit(1) from exc

    if result.reused:
        success(f"工作区已配置，现有文件保持不变：{result.paths.workspace_root}")
    else:
        success(f"工作区配置完成：{result.paths.workspace_root}")


@app.command()
def login() -> None:
    paths = _require_app_paths()
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
                    },
                    paths.session_file,
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
    user_status = get_user_status(_require_app_paths())
    username = user_status.get("username", "未知用户")
    success(f"在线状态: 当前账号 {username}")


@app.command()
def profile() -> None:
    account_profile = get_account_profile(_require_app_paths())
    render_profile(account_profile)


@app.command()
def get(question_id: str) -> None:
    problem_detail = get_problem_detail_by_question_id(
        _require_app_paths(),
        question_id,
    )
    render_problem_detail(problem_detail)


@app.command()
def show(limit: int = 50, skip: int = 0) -> None:
    problem_summaries = get_problem_summaries(
        _require_app_paths(),
        limit=limit,
        skip=skip,
    )
    render_problem_list(problem_summaries)


@app.command()
def solve(question_id: str) -> None:
    paths = _require_app_paths()
    problem_detail = get_problem_detail_by_question_id(paths, question_id)
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
    try:
        write_solution_file(
            paths.solution_file,
            problem_detail.python_code,
            ProblemMetadata(
                problem_id=problem_detail.question_id,
                submit_question_id=problem_detail.submit_question_id,
                title=problem_detail.title,
                title_slug=problem_detail.title_slug,
            ),
        )
    except WorkspaceError as exc:
        error(str(exc))
        raise Exit(1)


@app.command()
def test(
    timeout: Annotated[
        float,
        Option(
            "--timeout",
            help="本地自测总超时秒数",
        ),
    ] = 1.0,
) -> None:
    if not math.isfinite(timeout) or timeout <= 0:
        raise BadParameter("必须是大于 0 的有限秒数", param_hint="--timeout")

    paths = _require_app_paths()
    inspection = inspect_solution_file(paths.solution_file)
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
        case SolutionFileStatus.INVALID_ENCODING:
            error(inspection.detail)
            raise Exit(1)
        case SolutionFileStatus.INVALID_SYNTAX:
            line = (
                f"第 {inspection.syntax_line} 行"
                if inspection.syntax_line
                else "未知行"
            )
            error(f"solution.py 存在 Python 语法错误（{line}）")
            raise Exit(1)

    result = run_local_tests(paths.solution_file, timeout=timeout)
    render_local_test_output(result.stdout)
    render_local_test_output(result.stderr)
    match result.status:
        case LocalTestStatus.PASSED:
            success("本地自测执行成功")
        case LocalTestStatus.MISSING_ENTRY:
            error("未找到可执行的 run_cases()，请检查本地自测入口")
            raise Exit(1)
        case LocalTestStatus.NOT_CONFIGURED:
            error("尚未配置本地自测用例，请在 run_cases() 中添加测试")
            raise Exit(1)
        case LocalTestStatus.TIMED_OUT:
            error(f"本地自测超时：执行时间超过 {timeout:g} 秒")
            raise Exit(1)
        case LocalTestStatus.FAILED:
            error("本地自测执行失败")
            raise Exit(1)


@app.command()
def doctor(
    run_solution: Annotated[
        bool,
        Option(
            "--run-solution",
            help="显式执行当前工作区的 solution.py",
        ),
    ] = False,
) -> None:
    paths = _require_app_paths()
    with loading("正在检查本地环境与 LeetCode 连接..."):
        report = get_doctor_report(paths, run_solution=run_solution)
    render_doctor_report(report)
    if not report.ok:
        raise Exit(1)


@app.command()
def submit() -> None:
    result = submit_current_solution(_require_app_paths())
    render_submission_result(result)


if __name__ == "__main__":
    run()
