import json
import math
import sys
from typing import Annotated

from typer import BadParameter, Exit, Option, echo

from leetcode_local_cli.commands import common
from leetcode_local_cli.commands.rendering import (
    error,
    info,
    loading,
    render_doctor_report,
    render_local_execution_error,
    render_local_execution_result,
    success,
    warning,
)
from leetcode_local_cli.execution.protocol import (
    LocalTestInputError,
    parse_parameter_assignments,
)
from leetcode_local_cli.execution.worker import LocalExecutionWorker
from leetcode_local_cli.models.execution import (
    LocalExecutionResult,
    LocalExecutionStatus,
)
from leetcode_local_cli.use_cases.diagnostics import get_doctor_report
from leetcode_local_cli.use_cases.errors import UseCaseError
from leetcode_local_cli.use_cases.local_test import (
    LocalTestStartupError,
    start_local_test,
)


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
    verbose: Annotated[
        bool, Option("--verbose", help="显示完整异常调用栈，不采集局部变量")
    ] = False,
) -> None:
    if not math.isfinite(timeout) or timeout <= 0:
        raise BadParameter("必须是大于 0 的有限秒数", param_hint="--timeout")

    try:
        worker = start_local_test(
            common.require_workspace_paths().solution_file,
            timeout=timeout,
            verbose=verbose,
        )
    except UseCaseError as exc:
        if stdin:
            event: dict[str, object] = {
                "kind": "startup_error",
                "code": exc.code.value,
                "error": exc.message,
            }
            if isinstance(exc, LocalTestStartupError):
                event["error_line"] = exc.error_line
                if verbose and exc.traceback:
                    event["traceback"] = exc.traceback
            _write_stdin_test_event(event)
            raise Exit(1) from exc
        if isinstance(exc, LocalTestStartupError):
            error(exc.message)
            if exc.error_line is not None:
                error(f"位置：solution.py:{exc.error_line}")
            if verbose and exc.traceback:
                error(exc.traceback)
            raise Exit(1) from exc
        common.exit_for_use_case_error(exc)

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
                error_line=result.error_line,
                traceback=result.traceback,
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
                    "error_line": result.error_line,
                    **({"traceback": result.traceback} if result.traceback else {}),
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


def _stdin_result_value(result: LocalExecutionResult) -> object:
    if result.result_is_json:
        return json.loads(result.result_text)
    return result.result_text


def _stdin_arguments_after_value(result: LocalExecutionResult) -> object:
    if result.arguments_after_is_json:
        return json.loads(result.arguments_after_text or "null")
    return result.arguments_after_text


def _write_stdin_test_event(payload: dict[str, object]) -> None:
    echo(json.dumps(payload, ensure_ascii=False, allow_nan=False))


def doctor(
    run_solution: Annotated[
        bool,
        Option(
            "--run-solution",
            help="显式执行当前工作区的 solution.py",
        ),
    ] = False,
) -> None:
    paths = common.get_user_paths()
    with loading("正在检查本地环境与 LeetCode 连接..."):
        report = get_doctor_report(paths, run_solution=run_solution)
    render_doctor_report(report)
    if not report.ok:
        raise Exit(1)
