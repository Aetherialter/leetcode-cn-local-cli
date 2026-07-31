from pathlib import Path

import pytest

from leetcode_local_cli.local_testing import (
    LocalTestInputError,
    decode_arguments,
    encode_arguments,
    parse_parameter_assignments,
)
from leetcode_local_cli.workspace import (
    LocalExecutionStatus,
    LocalExecutionWorker,
    WorkspaceError,
)


def _write_solution(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_parameter_assignments_support_nested_literals_and_commas() -> None:
    arguments = parse_parameter_assignments(
        'nums = [3, 2, 4], target = 6, text = "a,b=c", flags = (True, None)'
    )

    assert arguments == {
        "nums": [3, 2, 4],
        "target": 6,
        "text": "a,b=c",
        "flags": (True, None),
    }


def test_parameter_assignments_support_no_argument_method_marker() -> None:
    assert parse_parameter_assignments("()") == {}


@pytest.mark.parametrize(
    "raw",
    (
        "[3, 2, 4]",
        "nums = other_value",
        "nums = input()",
        "nums = {1, 2}",
        "nums = [1], nums = [2]",
        "**values",
    ),
)
def test_parameter_assignments_reject_non_literal_or_ambiguous_input(raw: str) -> None:
    with pytest.raises(LocalTestInputError):
        parse_parameter_assignments(raw)


def test_worker_protocol_preserves_tuple_and_dictionary_literals() -> None:
    arguments = {"value": (1, {"nested": [True, None]})}

    assert decode_arguments(encode_arguments(arguments)) == arguments


def test_worker_automatically_uses_first_public_solution_method(tmp_path: Path) -> None:
    solution_file = tmp_path / "solution.py"
    _write_solution(
        solution_file,
        """
class Helper:
    def unrelated(self):
        return "ignored"


class Solution:
    def _private(self):
        return "ignored"

    def twoSum(self, nums, target):
        seen = {}
        for index, value in enumerate(nums):
            if target - value in seen:
                return [seen[target - value], index]
            seen[value] = index
        return []

    def public_helper(self):
        return "not selected"
""",
    )

    with LocalExecutionWorker(solution_file, timeout=1) as worker:
        assert worker.entry is not None
        assert worker.entry.method_name == "twoSum"
        assert worker.entry.method_signature == "(nums, target)"
        result = worker.execute({"nums": [3, 2, 4], "target": 6})

    assert result.status is LocalExecutionStatus.SUCCEEDED
    assert result.result_is_json
    assert result.result_text == "[1, 2]"


def test_worker_creates_a_fresh_solution_for_every_input_group(tmp_path: Path) -> None:
    solution_file = tmp_path / "solution.py"
    _write_solution(
        solution_file,
        """
class Solution:
    def __init__(self):
        self.calls = 0

    def run(self):
        self.calls += 1
        return self.calls
""",
    )

    with LocalExecutionWorker(solution_file, timeout=1) as worker:
        first = worker.execute({})
        second = worker.execute({})

    assert first.result_text == "1"
    assert second.result_text == "1"


def test_worker_captures_return_value_output_and_in_place_arguments(
    tmp_path: Path,
) -> None:
    solution_file = tmp_path / "solution.py"
    _write_solution(
        solution_file,
        """
class Solution:
    def solve(self, board):
        print("running")
        board[0][0] = "X"
""",
    )

    with LocalExecutionWorker(solution_file, timeout=1) as worker:
        result = worker.execute({"board": [["O"]]})

    assert result.status is LocalExecutionStatus.SUCCEEDED
    assert result.result_text == "null"
    assert result.stdout == "running\n"
    assert result.arguments_after_text == '{"board": [["X"]]}'


def test_worker_returns_controlled_user_exception_without_traceback(
    tmp_path: Path,
) -> None:
    solution_file = tmp_path / "solution.py"
    _write_solution(
        solution_file,
        """
class Solution:
    def divide(self, value):
        return value / 0
""",
    )

    with LocalExecutionWorker(solution_file, timeout=1) as worker:
        result = worker.execute({"value": 3})

    assert result.status is LocalExecutionStatus.FAILED
    assert result.error == "ZeroDivisionError: division by zero"
    assert "Traceback" not in result.stderr


def test_worker_timeout_restarts_for_a_later_input_group(tmp_path: Path) -> None:
    solution_file = tmp_path / "solution.py"
    _write_solution(
        solution_file,
        """
from time import sleep


class Solution:
    def wait(self, seconds):
        sleep(seconds)
        return "done"
""",
    )

    with LocalExecutionWorker(solution_file, timeout=1) as worker:
        timed_out = worker.execute({"seconds": 2})
        recovered = worker.execute({"seconds": 0})

    assert timed_out.status is LocalExecutionStatus.TIMED_OUT
    assert recovered.status is LocalExecutionStatus.SUCCEEDED
    assert recovered.result_text == '"done"'


@pytest.mark.parametrize(
    "content",
    (
        "class NotSolution:\n    pass\n",
        "class Solution:\n    pass\n",
        "class Solution:\n    async def solve(self):\n        return 1\n",
    ),
)
def test_worker_rejects_missing_or_unsupported_solution_entry(
    tmp_path: Path,
    content: str,
) -> None:
    solution_file = tmp_path / "solution.py"
    _write_solution(solution_file, content)

    with pytest.raises(WorkspaceError):
        LocalExecutionWorker(solution_file, timeout=1).start()


def test_worker_rejects_invalid_encoding_without_traceback(tmp_path: Path) -> None:
    solution_file = tmp_path / "solution.py"
    solution_file.write_bytes(b"\xff\xfeinvalid source")

    with pytest.raises(WorkspaceError, match="不是有效的 UTF-8 编码"):
        LocalExecutionWorker(solution_file, timeout=1).start()
