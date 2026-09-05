from pathlib import Path

from leetcode_local_cli.execution.worker import LocalExecutionWorker
from leetcode_local_cli.models.solution import SolutionFileStatus, WorkspaceError
from leetcode_local_cli.storage.solution import inspect_solution_file
from leetcode_local_cli.use_cases.errors import ErrorCode, UseCaseError


def start_local_test(path: Path, *, timeout: float) -> LocalExecutionWorker:
    inspection = inspect_solution_file(path)
    match inspection.status:
        case SolutionFileStatus.MISSING:
            raise UseCaseError(
                "未找到 solution.py，请先执行 lc solve <题号>", code=ErrorCode.SOLUTION
            )
        case SolutionFileStatus.EMPTY:
            raise UseCaseError(
                "solution.py 当前为空，请先执行 lc solve <题号>",
                code=ErrorCode.SOLUTION,
            )
        case SolutionFileStatus.READ_ERROR:
            raise UseCaseError(
                "无法读取 solution.py，请检查文件权限", code=ErrorCode.SOLUTION
            )
        case SolutionFileStatus.INVALID_ENCODING:
            raise UseCaseError(inspection.detail, code=ErrorCode.SOLUTION)
        case SolutionFileStatus.INVALID_SYNTAX:
            line = (
                f"第 {inspection.syntax_line} 行"
                if inspection.syntax_line
                else "未知行"
            )
            raise UseCaseError(
                f"solution.py 存在 Python 语法错误（{line}）", code=ErrorCode.SOLUTION
            )

    worker = LocalExecutionWorker(path, timeout=timeout)
    try:
        worker.start()
    except WorkspaceError as exc:
        raise UseCaseError(str(exc), code=ErrorCode.SOLUTION) from exc
    return worker
