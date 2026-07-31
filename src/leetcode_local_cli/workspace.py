from dataclasses import dataclass
from enum import Enum
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading

from leetcode_local_cli.local_testing import (
    encode_arguments,
)
from leetcode_local_cli.safe_files import SafeFileError, atomic_write_text
from leetcode_local_cli.solution_source import (
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
    INVALID_ENCODING = "invalid_encoding"
    INVALID_SYNTAX = "invalid_syntax"
    NOT_SUBMITTABLE = "not_submittable"


class LocalExecutionStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class SolutionFileInspection:
    status: SolutionFileStatus
    metadata: ProblemMetadata | None = None
    detail: str = ""
    syntax_line: int | None = None


@dataclass(frozen=True)
class LocalExecutionEntry:
    method_name: str
    method_signature: str


@dataclass(frozen=True)
class LocalExecutionResult:
    status: LocalExecutionStatus
    result_text: str = ""
    result_is_json: bool = False
    stdout: str = ""
    stderr: str = ""
    error: str = ""
    arguments_after_text: str | None = None
    arguments_after_is_json: bool = False


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


class LocalExecutionWorker:
    """Keep one isolated Python worker alive across local input groups."""

    def __init__(self, path: Path, *, timeout: float) -> None:
        self.path = Path(os.path.abspath(os.fspath(path)))
        self.timeout = timeout
        self._process: subprocess.Popen[str] | None = None
        self._events: queue.Queue[str] = queue.Queue()
        self._reader: threading.Thread | None = None
        self.entry: LocalExecutionEntry | None = None

    def __enter__(self) -> "LocalExecutionWorker":
        self.start()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    def start(self) -> LocalExecutionEntry:
        self.close()
        events: queue.Queue[str] = queue.Queue()
        self._events = events
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["PYTHONUNBUFFERED"] = "1"
        try:
            self._process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "leetcode_local_cli._test_runner",
                    str(self.path),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=self.path.parent,
                env=environment,
            )
        except OSError as exc:
            raise WorkspaceError("无法启动本地执行 worker") from exc
        self._reader = threading.Thread(
            target=self._collect_events,
            args=(self._process, events),
            daemon=True,
        )
        self._reader.start()
        try:
            event = self._wait_for_event()
        except (TimeoutError, WorkspaceError) as exc:
            self.close()
            if isinstance(exc, TimeoutError):
                raise WorkspaceError("加载 solution.py 超时") from exc
            raise
        if event.get("kind") != "ready":
            self.close()
            message = event.get("message")
            if isinstance(message, str) and message:
                raise WorkspaceError(message)
            raise WorkspaceError("无法加载 solution.py")
        method_name = event.get("method_name")
        method_signature = event.get("method_signature")
        if not isinstance(method_name, str) or not isinstance(method_signature, str):
            self.close()
            raise WorkspaceError("本地执行 worker 返回了无效入口信息")
        self.entry = LocalExecutionEntry(method_name, method_signature)
        return self.entry

    def execute(self, arguments: dict[str, object]) -> LocalExecutionResult:
        if self._process is None or self._process.poll() is not None:
            try:
                self.start()
            except WorkspaceError as exc:
                return LocalExecutionResult(
                    status=LocalExecutionStatus.FAILED,
                    error=str(exc),
                )
        process = self._process
        if process is None or process.stdin is None:
            return LocalExecutionResult(
                status=LocalExecutionStatus.FAILED,
                error="本地执行 worker 不可用",
            )
        try:
            process.stdin.write(
                json.dumps(
                    {"kind": "call", "arguments": encode_arguments(arguments)},
                    ensure_ascii=False,
                )
                + "\n"
            )
            process.stdin.flush()
        except (OSError, ValueError) as exc:
            self.close()
            return LocalExecutionResult(
                status=LocalExecutionStatus.FAILED,
                error=f"无法向本地执行 worker 发送参数：{type(exc).__name__}",
            )

        try:
            event = self._wait_for_event()
        except TimeoutError:
            self.close()
            return LocalExecutionResult(status=LocalExecutionStatus.TIMED_OUT)
        except WorkspaceError as exc:
            self.close()
            return LocalExecutionResult(
                status=LocalExecutionStatus.FAILED,
                error=str(exc),
            )
        return self._result_from_event(event)

    def close(self) -> None:
        process = self._process
        self._process = None
        self.entry = None
        if process is None:
            return
        if process.stdin is not None:
            try:
                process.stdin.write('{"kind":"shutdown"}\n')
                process.stdin.flush()
            except (OSError, ValueError):
                pass
        try:
            process.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    def _collect_events(
        self,
        process: subprocess.Popen[str] | None,
        events: queue.Queue[str],
    ) -> None:
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            events.put(line)

    def _wait_for_event(self) -> dict[str, object]:
        try:
            line = self._events.get(timeout=self.timeout)
        except queue.Empty as exc:
            raise TimeoutError from exc
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise WorkspaceError("本地执行 worker 返回了无效响应") from exc
        if not isinstance(event, dict):
            raise WorkspaceError("本地执行 worker 返回了无效响应")
        return event

    def _result_from_event(self, event: dict[str, object]) -> LocalExecutionResult:
        if event.get("kind") != "result":
            message = event.get("message")
            return LocalExecutionResult(
                status=LocalExecutionStatus.FAILED,
                error=message
                if isinstance(message, str)
                else "本地执行 worker 执行失败",
            )
        stdout = event.get("stdout")
        stderr = event.get("stderr")
        if event.get("ok") is not True:
            error = event.get("error")
            return LocalExecutionResult(
                status=LocalExecutionStatus.FAILED,
                stdout=stdout if isinstance(stdout, str) else "",
                stderr=stderr if isinstance(stderr, str) else "",
                error=error if isinstance(error, str) else "本地代码执行失败",
            )
        result = event.get("result")
        if not isinstance(result, dict):
            return LocalExecutionResult(
                status=LocalExecutionStatus.FAILED,
                error="本地执行 worker 返回了无效结果",
            )
        result_text = result.get("text")
        result_is_json = result.get("is_json")
        if not isinstance(result_text, str) or not isinstance(result_is_json, bool):
            return LocalExecutionResult(
                status=LocalExecutionStatus.FAILED,
                error="本地执行 worker 返回了无效结果",
            )
        arguments_after = event.get("arguments_after")
        arguments_after_text: str | None = None
        arguments_after_is_json = False
        if isinstance(arguments_after, dict):
            candidate_text = arguments_after.get("text")
            candidate_is_json = arguments_after.get("is_json")
            if isinstance(candidate_text, str) and isinstance(candidate_is_json, bool):
                arguments_after_text = candidate_text
                arguments_after_is_json = candidate_is_json
        return LocalExecutionResult(
            status=LocalExecutionStatus.SUCCEEDED,
            result_text=result_text,
            result_is_json=result_is_json,
            stdout=stdout if isinstance(stdout, str) else "",
            stderr=stderr if isinstance(stderr, str) else "",
            arguments_after_text=arguments_after_text,
            arguments_after_is_json=arguments_after_is_json,
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
