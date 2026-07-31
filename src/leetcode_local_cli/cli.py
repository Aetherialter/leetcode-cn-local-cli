import json
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
    render_local_execution_error,
    render_local_execution_result,
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
from leetcode_local_cli.local_testing import (
    LocalTestInputError,
    parse_parameter_assignments,
)
from leetcode_local_cli.workspace import (
    LocalExecutionStatus,
    LocalExecutionWorker,
    ProblemMetadata,
    SolutionFileStatus,
    WorkspaceError,
    inspect_solution_file,
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
            help="每组本地调用的超时秒数",
        ),
    ] = 1.0,
    stdin: Annotated[
        bool,
        Option("--stdin", help="从标准输入逐行读取参数，不显示 Rich 交互界面"),
    ] = False,
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

    worker = LocalExecutionWorker(paths.solution_file, timeout=timeout)
    try:
        worker.start()
    except WorkspaceError as exc:
        if stdin:
            _write_stdin_test_event({"kind": "startup_error", "error": str(exc)})
        else:
            error(str(exc))
        raise Exit(1) from exc

    try:
        if stdin:
            failed = _run_stdin_local_test(worker)
        else:
            failed = _run_interactive_local_test(worker, timeout=timeout)
    finally:
        worker.close()
    if failed:
        raise Exit(1)


def _run_interactive_local_test(
    worker: LocalExecutionWorker,
    *,
    timeout: float,
) -> bool:
    entry = worker.entry
    if entry is None:
        error("本地执行 worker 未返回入口信息")
        return True
    info(f"检测到入口：Solution.{entry.method_name}{entry.method_signature}")
    info("请输入参数，例如：nums = [3, 2, 4], target = 6")
    info("连续两次直接回车退出。")

    total = successful = failed = 0
    pending_exit = False
    while True:
        try:
            echo("参数 > ", nl=False)
            raw = input()
        except EOFError:
            warning("检测到输入结束，已退出本地交互执行")
            break
        if not raw.strip():
            if pending_exit:
                break
            pending_exit = True
            warning("再次直接回车确认退出；输入参数可继续。")
            continue
        pending_exit = False
        total += 1
        try:
            arguments = parse_parameter_assignments(raw)
        except LocalTestInputError as exc:
            failed += 1
            render_local_execution_error(
                case_index=total,
                error_detail=str(exc),
            )
            continue

        result = worker.execute(arguments)
        if result.status is LocalExecutionStatus.SUCCEEDED:
            successful += 1
            render_local_execution_result(
                case_index=total,
                result_text=result.result_text,
                stdout=result.stdout,
                stderr=result.stderr,
                arguments_after_text=result.arguments_after_text,
            )
        else:
            failed += 1
            error_detail = (
                f"执行时间超过 {timeout:g} 秒"
                if result.status is LocalExecutionStatus.TIMED_OUT
                else result.error
            )
            render_local_execution_error(
                case_index=total,
                error_detail=error_detail or "本地代码执行失败",
                stdout=result.stdout,
                stderr=result.stderr,
            )

    if total == 0:
        error("未执行任何本地输入")
        return True
    if failed:
        error(f"本地交互执行结束（成功 {successful} 组，失败 {failed} 组）")
        return True
    success(f"本地交互执行结束（已成功执行 {successful} 组输入）")
    return False


def _run_stdin_local_test(worker: LocalExecutionWorker) -> bool:
    total = successful = failed = 0
    for raw in sys.stdin:
        if not raw.strip():
            continue
        total += 1
        try:
            arguments = parse_parameter_assignments(raw)
        except LocalTestInputError as exc:
            failed += 1
            _write_stdin_test_event({"case": total, "ok": False, "error": str(exc)})
            continue
        result = worker.execute(arguments)
        if result.status is LocalExecutionStatus.SUCCEEDED:
            successful += 1
            payload: dict[str, object] = {
                "case": total,
                "ok": True,
                "result": _stdin_result_value(result),
                "result_is_json": result.result_is_json,
            }
            if result.stdout:
                payload["stdout"] = result.stdout
            if result.stderr:
                payload["stderr"] = result.stderr
            if result.arguments_after_text is not None:
                payload["arguments_after"] = _stdin_arguments_after_value(result)
            _write_stdin_test_event(payload)
        else:
            failed += 1
            error_detail = (
                f"执行时间超过 {worker.timeout:g} 秒"
                if result.status is LocalExecutionStatus.TIMED_OUT
                else result.error
            )
            _write_stdin_test_event(
                {
                    "case": total,
                    "ok": False,
                    "error": error_detail or "本地代码执行失败",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            )
    if total == 0:
        failed = 1
        _write_stdin_test_event({"kind": "error", "error": "未接收到任何参数输入"})
    _write_stdin_test_event(
        {
            "kind": "summary",
            "total": total,
            "successful": successful,
            "failed": failed,
        }
    )
    return failed > 0


def _stdin_result_value(result: object) -> object:
    result_text = getattr(result, "result_text")
    if getattr(result, "result_is_json"):
        return json.loads(result_text)
    return result_text


def _stdin_arguments_after_value(result: object) -> object:
    arguments_after_text = getattr(result, "arguments_after_text")
    if getattr(result, "arguments_after_is_json"):
        return json.loads(arguments_after_text)
    return arguments_after_text


def _write_stdin_test_event(payload: dict[str, object]) -> None:
    echo(json.dumps(payload, ensure_ascii=False, allow_nan=False))


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
    if result is None or result.get("status_msg") != "Accepted":
        raise Exit(1)


if __name__ == "__main__":
    run()
