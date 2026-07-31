"""Isolated child-process entry point for user-authored local tests."""

import ast
import inspect
from pathlib import Path
import sys

from leetcode_local_cli.solution_source import (
    SolutionSourceEncodingError,
    read_solution_source,
)


EXIT_TEST_FAILED = 1
EXIT_MISSING_ENTRY = 20
EXIT_NOT_CONFIGURED = 21


def _write_exception_summary(exc: BaseException) -> None:
    detail = str(exc)
    message = type(exc).__name__ if not detail else f"{type(exc).__name__}: {detail}"
    print(message, file=sys.stderr)


def _find_run_cases(
    tree: ast.Module,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for statement in reversed(tree.body):
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if statement.name == "run_cases":
                return statement
    return None


def _has_no_parameters(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    arguments = function.args
    return not (
        arguments.posonlyargs
        or arguments.args
        or arguments.vararg
        or arguments.kwonlyargs
        or arguments.kwarg
    )


def _is_empty_run_cases(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """Recognize no-op functions and the generated scaffold."""
    body = list(function.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body.pop(0)
    if not body:
        return True
    if all(
        isinstance(statement, ast.Pass)
        or (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and statement.value.value is Ellipsis
        )
        or (
            isinstance(statement, ast.Return)
            and (
                statement.value is None
                or (
                    isinstance(statement.value, ast.Constant)
                    and statement.value.value is None
                )
            )
        )
        for statement in body
    ):
        return True

    if len(body) not in {1, 2}:
        return False
    assignment = body[0]
    if not isinstance(assignment, ast.Assign) or len(assignment.targets) != 1:
        return False
    target = assignment.targets[0]
    value = assignment.value
    is_solution_instantiation = (
        isinstance(target, ast.Name)
        and target.id == "solution"
        and isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "Solution"
        and not value.args
        and not value.keywords
    )
    return is_solution_instantiation and (
        len(body) == 1 or isinstance(body[1], ast.Pass)
    )


def _load_source(path: Path) -> tuple[str, ast.Module] | None:
    try:
        source = read_solution_source(path)
        return source, ast.parse(source, filename=str(path))
    except (OSError, SolutionSourceEncodingError, SyntaxError) as exc:
        _write_exception_summary(exc)
        return None


def run(path: Path) -> int:
    loaded_source = _load_source(path)
    if loaded_source is None:
        return EXIT_TEST_FAILED
    source, tree = loaded_source
    run_cases_definition = _find_run_cases(tree)
    if run_cases_definition is None:
        return EXIT_MISSING_ENTRY
    if isinstance(run_cases_definition, ast.AsyncFunctionDef) or not _has_no_parameters(
        run_cases_definition
    ):
        _write_exception_summary(TypeError("run_cases() 必须是同步无参数函数"))
        return EXIT_TEST_FAILED
    if _is_empty_run_cases(run_cases_definition):
        return EXIT_NOT_CONFIGURED

    namespace = {
        "__name__": "__lc_test__",
        "__file__": str(path),
        "__package__": None,
        "__spec__": None,
        "__cached__": None,
    }
    try:
        exec(compile(source, str(path), "exec"), namespace)
    except BaseException as exc:
        _write_exception_summary(exc)
        return EXIT_TEST_FAILED

    run_cases = namespace.get("run_cases")
    if not callable(run_cases):
        return EXIT_MISSING_ENTRY

    try:
        result = run_cases()
        if inspect.isawaitable(result):
            close = getattr(result, "close", None)
            if callable(close):
                close()
            raise TypeError("run_cases() 必须是同步无参数函数")
    except BaseException as exc:
        _write_exception_summary(exc)
        return EXIT_TEST_FAILED
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python -m leetcode_local_cli._test_runner SOLUTION_FILE")
        return 2
    return run(Path(sys.argv[1]))


if __name__ == "__main__":
    raise SystemExit(main())
