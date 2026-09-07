from importlib.resources import files
from pathlib import Path

from leetcode_local_cli.models.solution import (
    ProblemMetadata,
    SolutionFileInspection,
    SolutionFileStatus,
    WorkspaceError,
)
from leetcode_local_cli.storage.safe_files import SafeFileError, atomic_write_text
from leetcode_local_cli.storage.solution_source import (
    SolutionSourceEncodingError,
    read_solution_source,
)

METADATA_PREFIX = "# @lc "
START_FLAG = "# @lc submit_begin"
END_FLAG = "# @lc submit_end"
NOT_IMPLEMENTED_PLACEHOLDER = 'raise NotImplementedError("请实现题目方法")'

SOLUTION_FILE_HEADER = """# pyright: reportUnusedImport=false, reportUnusedVariable=false
# ruff: noqa: F401, F841
"""

SOLUTION_IMPORTS = """from typing import Any, Dict, List, Optional, Set, Tuple
from collections import Counter, defaultdict, deque
from functools import cache, lru_cache
from itertools import accumulate, combinations, permutations, product
from bisect import bisect_left, bisect_right, insort
from heapq import heapify, heappop, heappush
from math import gcd, inf, isqrt, lcm
"""


def _normalize_python_code(python_code: str) -> str:
    code = python_code.rstrip()
    if not code:
        return code

    lines = code.splitlines()
    last_line = lines[-1]
    stripped_last_line = last_line.rstrip()
    indentation = last_line[: len(last_line) - len(last_line.lstrip())]
    if stripped_last_line.endswith(": pass"):
        header = stripped_last_line.removesuffix("pass").rstrip()
        return "\n".join(
            [*lines[:-1], header, f"{indentation}    {NOT_IMPLEMENTED_PLACEHOLDER}"]
        )
    if stripped_last_line.endswith(":"):
        return f"{code}\n{indentation}    {NOT_IMPLEMENTED_PLACEHOLDER}"
    return code


def build_solution_content(python_code: str, metadata: ProblemMetadata) -> str:
    metadata_content = (
        f"{METADATA_PREFIX}problem_id: {metadata.problem_id}\n"
        f"{METADATA_PREFIX}submit_question_id: {metadata.submit_question_id}\n"
        f"{METADATA_PREFIX}title: {metadata.title}\n"
        f"{METADATA_PREFIX}title_slug: {metadata.title_slug}\n\n"
    )
    return (
        f"{SOLUTION_FILE_HEADER}"
        f"{metadata_content}"
        f"{SOLUTION_IMPORTS}\n\n"
        f"{files('leetcode_local_cli.models').joinpath('nodes.py').read_text(encoding='utf-8')}\n\n"
        f"{START_FLAG}\n"
        f"{_normalize_python_code(python_code)}\n"
        f"{END_FLAG}\n"
    )


def write_solution_file(
    path: Path,
    python_code: str,
    metadata: ProblemMetadata,
) -> None:
    try:
        atomic_write_text(
            path,
            build_solution_content(python_code, metadata),
            label="solution.py",
        )
    except SafeFileError as exc:
        raise WorkspaceError(str(exc)) from exc


def _parse_solution_submission_content(content: str) -> tuple[ProblemMetadata, str]:
    metadata: dict[str, str] = {}
    start_flag = end_flag = False
    submission_lines: list[str] = []
    for string in content.splitlines(keepends=True):
        line = string.strip()
        if line == END_FLAG:
            end_flag = True
            break
        if start_flag:
            submission_lines.append(string)
        if line.startswith(METADATA_PREFIX):
            item = line.removeprefix(METADATA_PREFIX)
            key, separator, value = item.partition(":")
            if separator:
                metadata[key.strip()] = value.strip()
        if line == START_FLAG:
            start_flag = True

    if not start_flag or not end_flag:
        raise WorkspaceError("solution.py 提交区域标记不完整，请先执行 lc solve <题号>")

    submission_code = "".join(submission_lines).strip()
    if not submission_code:
        raise WorkspaceError("solution.py 提交区域为空")

    if not all(
        [
            metadata.get("problem_id"),
            metadata.get("submit_question_id"),
            metadata.get("title"),
            metadata.get("title_slug"),
        ]
    ):
        raise WorkspaceError(
            "solution.py 缺少元数据：problem_id、submit_question_id、title、title_slug"
        )

    return (
        ProblemMetadata(
            problem_id=metadata["problem_id"],
            submit_question_id=metadata["submit_question_id"],
            title=metadata["title"],
            title_slug=metadata["title_slug"],
        ),
        submission_code,
    )


def parse_solution_submission(path: Path) -> tuple[ProblemMetadata, str]:
    try:
        content = read_solution_source(path)
    except FileNotFoundError as exc:
        raise WorkspaceError("未找到 solution.py，请先执行 lc solve <题号>") from exc
    except SolutionSourceEncodingError as exc:
        raise WorkspaceError(str(exc)) from exc
    except OSError as exc:
        raise WorkspaceError("无法读取 solution.py，请检查文件权限") from exc
    return _parse_solution_submission_content(content)


def inspect_solution_file(path: Path) -> SolutionFileInspection:
    try:
        content = read_solution_source(path)
    except FileNotFoundError:
        return SolutionFileInspection(status=SolutionFileStatus.MISSING)
    except SolutionSourceEncodingError as exc:
        return SolutionFileInspection(
            status=SolutionFileStatus.INVALID_ENCODING,
            detail=str(exc),
        )
    except OSError:
        return SolutionFileInspection(status=SolutionFileStatus.READ_ERROR)

    if not content.strip():
        return SolutionFileInspection(status=SolutionFileStatus.EMPTY)

    try:
        compile(content, str(path), "exec")
    except SyntaxError as exc:
        return SolutionFileInspection(
            status=SolutionFileStatus.INVALID_SYNTAX,
            detail=exc.msg,
            syntax_line=exc.lineno,
        )

    try:
        metadata, _ = _parse_solution_submission_content(content)
    except WorkspaceError as exc:
        return SolutionFileInspection(
            status=SolutionFileStatus.NOT_SUBMITTABLE,
            detail=str(exc),
        )

    return SolutionFileInspection(
        status=SolutionFileStatus.READY,
        metadata=metadata,
    )
