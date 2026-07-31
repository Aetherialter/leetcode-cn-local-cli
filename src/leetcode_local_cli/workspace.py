from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
import subprocess
import sys

from leetcode_local_cli._test_runner import (
    EXIT_MISSING_ENTRY,
    EXIT_NOT_CONFIGURED,
)
from leetcode_local_cli.safe_files import SafeFileError, atomic_write_text

METADATA_PREFIX = "# @lc "
START_FLAG = "# @lc submit_begin"
END_FLAG = "# @lc submit_end"

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

SOLUTION_CASE = """
def run_cases() -> None:
    solution = Solution()
    # Add local assertions here, for example:
    # assert solution.twoSum([2, 7, 11, 15], 9) == [0, 1]
    pass


if __name__ == "__main__":
    run_cases()
"""


@dataclass(frozen=True)
class ProblemMetadata:
    problem_id: str
    submit_question_id: str
    title: str
    title_slug: str


class WorkspaceError(ValueError):
    pass


class SolutionFileStatus(str, Enum):
    READY = "ready"
    MISSING = "missing"
    EMPTY = "empty"
    READ_ERROR = "read_error"
    INVALID_SYNTAX = "invalid_syntax"
    NOT_SUBMITTABLE = "not_submittable"


class LocalTestStatus(str, Enum):
    PASSED = "passed"
    MISSING_ENTRY = "missing_entry"
    NOT_CONFIGURED = "not_configured"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class SolutionFileInspection:
    status: SolutionFileStatus
    metadata: ProblemMetadata | None = None
    detail: str = ""
    syntax_line: int | None = None


@dataclass(frozen=True)
class LocalTestResult:
    status: LocalTestStatus
    stdout: str = ""
    stderr: str = ""


def _normalize_python_code(python_code: str) -> str:
    code = python_code.rstrip()
    if code and code.splitlines()[-1].rstrip().endswith(":"):
        return f"{code} pass"
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
        f"{START_FLAG}\n"
        f"{_normalize_python_code(python_code)}\n"
        f"{END_FLAG}\n\n"
        f"{SOLUTION_CASE}\n"
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
    open_path(path)


def open_path(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)
        return

    command = "open" if sys.platform == "darwin" else "xdg-open"
    try:
        subprocess.Popen(
            [command, str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass


def run_solution_file(
    path: Path,
    *,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(path)],
        capture_output=True,
        text=True,
        cwd=path.parent,
        timeout=timeout,
    )


def _timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_local_tests(path: Path, *, timeout: float) -> LocalTestResult:
    path = Path(os.path.abspath(os.fspath(path)))
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUNBUFFERED"] = "1"
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "leetcode_local_cli._test_runner",
                str(path),
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=path.parent,
            env=environment,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return LocalTestResult(
            status=LocalTestStatus.TIMED_OUT,
            stdout=_timeout_output(exc.stdout),
            stderr=_timeout_output(exc.stderr),
        )
    except OSError as exc:
        return LocalTestResult(
            status=LocalTestStatus.FAILED,
            stderr=f"{type(exc).__name__}: {exc}",
        )

    status = LocalTestStatus.FAILED
    if result.returncode == 0:
        status = LocalTestStatus.PASSED
    elif result.returncode == EXIT_MISSING_ENTRY:
        status = LocalTestStatus.MISSING_ENTRY
    elif result.returncode == EXIT_NOT_CONFIGURED:
        status = LocalTestStatus.NOT_CONFIGURED
    return LocalTestResult(
        status=status,
        stdout=result.stdout,
        stderr=result.stderr,
    )


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
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise WorkspaceError("未找到 solution.py，请先执行 lc solve <题号>") from exc
    except OSError as exc:
        raise WorkspaceError("无法读取 solution.py，请检查文件权限") from exc
    return _parse_solution_submission_content(content)


def inspect_solution_file(path: Path) -> SolutionFileInspection:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return SolutionFileInspection(status=SolutionFileStatus.MISSING)
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
