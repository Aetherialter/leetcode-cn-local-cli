"""Long-lived isolated worker used by ``lc test``.

The parent process owns terminal interaction.  This worker reads JSON protocol
messages from stdin and writes one JSON event per line to stdout, keeping user
code output away from the protocol channel.
"""

from contextlib import redirect_stderr, redirect_stdout
import inspect
import io
import json
import math
from pathlib import Path
import sys
from typing import Any, TextIO

from leetcode_local_cli.local_testing import decode_arguments
from leetcode_local_cli.solution_source import read_solution_source


def _exception_summary(exc: BaseException) -> str:
    detail = str(exc)
    return type(exc).__name__ if not detail else f"{type(exc).__name__}: {detail}"


def _display_value(value: object) -> dict[str, object]:
    if _is_json_value(value):
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
        return {"is_json": True, "text": encoded}
    try:
        return {"is_json": False, "text": repr(value)}
    except BaseException as exc:
        return {"is_json": False, "text": _exception_summary(exc)}


def _is_json_value(value: object) -> bool:
    if value is None or isinstance(value, (bool, int, str)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_is_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _is_json_value(item) for key, item in value.items()
        )
    return False


def _decode_call_arguments(value: object) -> dict[str, object] | None:
    return decode_arguments(value)


class TestWorker:
    def __init__(self, path: Path, protocol_stdout: TextIO) -> None:
        self.path = path
        self.protocol_stdout = protocol_stdout
        self.solution_class: type[Any] | None = None
        self.method_name = ""
        self.method_signature = ""

    def emit(self, payload: dict[str, object]) -> None:
        self.protocol_stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.protocol_stdout.flush()

    def load(self) -> None:
        source = read_solution_source(self.path)
        namespace = {
            "__name__": "__lc_test__",
            "__file__": str(self.path),
            "__package__": None,
            "__spec__": None,
            "__cached__": None,
        }
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            exec(compile(source, str(self.path), "exec"), namespace)

        solution_class = namespace.get("Solution")
        if not isinstance(solution_class, type):
            raise TypeError("solution.py 必须定义 class Solution")

        for name, member in solution_class.__dict__.items():
            if name.startswith("_") or not inspect.isfunction(member):
                continue
            if inspect.iscoroutinefunction(member):
                raise TypeError("Solution 入口方法必须是同步函数")
            signature = inspect.signature(member)
            parameters = list(signature.parameters.values())
            if not parameters or parameters[0].name != "self":
                raise TypeError("Solution 入口方法必须是实例方法")
            self.solution_class = solution_class
            self.method_name = name
            self.method_signature = str(signature.replace(parameters=parameters[1:]))
            return

        raise TypeError("Solution 中未找到公开实例方法")

    def ready_event(self) -> dict[str, object]:
        return {
            "kind": "ready",
            "method_name": self.method_name,
            "method_signature": self.method_signature,
        }

    def call(self, arguments: dict[str, object]) -> dict[str, object]:
        if self.solution_class is None:
            return {"kind": "error", "message": "本地执行 worker 尚未初始化"}

        stdout, stderr = io.StringIO(), io.StringIO()
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                solution = self.solution_class()
                method = getattr(solution, self.method_name)
                inspect.signature(method).bind(**arguments)
                result = method(**arguments)
        except BaseException as exc:
            return {
                "kind": "result",
                "ok": False,
                "error": _exception_summary(exc),
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue(),
            }

        payload: dict[str, object] = {
            "kind": "result",
            "ok": True,
            "result": _display_value(result),
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
        }
        if result is None:
            payload["arguments_after"] = _display_value(arguments)
        return payload


def _read_message(line: str) -> dict[str, object] | None:
    try:
        message = json.loads(line)
    except json.JSONDecodeError:
        return None
    return message if isinstance(message, dict) else None


def run(path: Path) -> int:
    worker = TestWorker(path, sys.stdout)
    try:
        worker.load()
    except BaseException as exc:
        worker.emit({"kind": "startup_error", "message": _exception_summary(exc)})
        return 1

    worker.emit(worker.ready_event())
    for line in sys.stdin:
        message = _read_message(line)
        if message is None:
            worker.emit({"kind": "error", "message": "worker 收到无效请求"})
            continue
        if message.get("kind") == "shutdown":
            return 0
        if message.get("kind") != "call":
            worker.emit({"kind": "error", "message": "worker 收到未知请求"})
            continue
        arguments = _decode_call_arguments(message.get("arguments"))
        if arguments is None:
            worker.emit({"kind": "error", "message": "worker 参数结构无效"})
            continue
        worker.emit(worker.call(arguments))
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python -m leetcode_local_cli._test_runner SOLUTION_FILE")
        return 2
    return run(Path(sys.argv[1]))


if __name__ == "__main__":
    raise SystemExit(main())
