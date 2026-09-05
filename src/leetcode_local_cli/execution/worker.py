import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

from leetcode_local_cli.execution.protocol import encode_arguments
from leetcode_local_cli.models.execution import (
    LocalExecutionEntry,
    LocalExecutionResult,
    LocalExecutionStatus,
)
from leetcode_local_cli.models.solution import WorkspaceError


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
                    "leetcode_local_cli.execution.runner",
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
