from pathlib import Path

import pytest

from leetcode_local_cli import workspace
from leetcode_local_cli.workspace import (
    LocalTestStatus,
    ProblemMetadata,
)


def _write_solution(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_generated_empty_run_cases_is_not_reported_as_passed(tmp_path: Path) -> None:
    solution_file = tmp_path / "solution.py"
    _write_solution(
        solution_file,
        workspace.build_solution_content(
            "class Solution:\n    pass",
            ProblemMetadata("1", "1", "Two Sum", "two-sum"),
        ),
    )

    result = workspace.run_local_tests(solution_file, timeout=1)

    assert result.status is LocalTestStatus.NOT_CONFIGURED
    assert result.stdout == ""
    assert result.stderr == ""


def test_legacy_empty_run_cases_is_not_reported_as_passed(tmp_path: Path) -> None:
    solution_file = tmp_path / "solution.py"
    _write_solution(
        solution_file,
        """
class Solution:
    pass


def run_cases() -> None:
    solution = Solution()
    # Add local assertions here.
    pass


if __name__ == "__main__":
    run_cases()
""",
    )

    result = workspace.run_local_tests(solution_file, timeout=1)

    assert result.status is LocalTestStatus.NOT_CONFIGURED


@pytest.mark.parametrize(
    "body",
    (
        "    pass",
        "    ...",
        "    return",
        "    return None",
        '    """No tests yet."""\n    pass',
        "    solution = Solution()",
    ),
)
def test_equivalent_empty_run_cases_is_not_reported_as_passed(
    tmp_path: Path,
    body: str,
) -> None:
    solution_file = tmp_path / "solution.py"
    _write_solution(
        solution_file,
        f"""
class Solution:
    pass


def run_cases() -> None:
{body}
""",
    )

    result = workspace.run_local_tests(solution_file, timeout=1)

    assert result.status is LocalTestStatus.NOT_CONFIGURED


def test_missing_run_cases_is_rejected_without_executing_top_level_code(
    tmp_path: Path,
) -> None:
    solution_file = tmp_path / "solution.py"
    side_effect_file = tmp_path / "side-effect.txt"
    _write_solution(
        solution_file,
        f"""
from pathlib import Path

Path({str(side_effect_file)!r}).write_text("executed", encoding="utf-8")
""",
    )

    result = workspace.run_local_tests(solution_file, timeout=1)

    assert result.status is LocalTestStatus.MISSING_ENTRY
    assert not side_effect_file.exists()


def test_non_callable_run_cases_is_rejected(tmp_path: Path) -> None:
    solution_file = tmp_path / "solution.py"
    _write_solution(
        solution_file,
        """
def run_cases() -> None:
    print("must not run")


run_cases = None
""",
    )

    result = workspace.run_local_tests(solution_file, timeout=1)

    assert result.status is LocalTestStatus.MISSING_ENTRY
    assert result.stdout == ""


def test_latest_run_cases_definition_determines_empty_status(tmp_path: Path) -> None:
    solution_file = tmp_path / "solution.py"
    _write_solution(
        solution_file,
        """
def run_cases() -> None:
    print("obsolete test")


def run_cases() -> None:
    pass
""",
    )

    result = workspace.run_local_tests(solution_file, timeout=1)

    assert result.status is LocalTestStatus.NOT_CONFIGURED
    assert result.stdout == ""


def test_filled_run_cases_runs_once_and_preserves_user_output(tmp_path: Path) -> None:
    workspace_path = tmp_path / "中文 workspace"
    workspace_path.mkdir()
    solution_file = workspace_path / "solution.py"
    calls_file = workspace_path / "calls.txt"
    _write_solution(
        solution_file,
        f"""
def run_cases() -> None:
    with open({str(calls_file)!r}, "a", encoding="utf-8") as file:
        file.write("called\\n")
    print("[2, 7]")
    assert [2, 7] == [2, 7]


if __name__ == "__main__":
    run_cases()
""",
    )

    result = workspace.run_local_tests(solution_file, timeout=1)

    assert result.status is LocalTestStatus.PASSED
    assert result.stdout == "[2, 7]\n"
    assert result.stderr == ""
    assert calls_file.read_text(encoding="utf-8") == "called\n"


def test_relative_solution_path_is_resolved_before_changing_child_cwd(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace_path = tmp_path / "relative-workspace"
    workspace_path.mkdir()
    solution_file = workspace_path / "solution.py"
    _write_solution(
        solution_file,
        """
def run_cases() -> None:
    print("relative path works")
""",
    )
    monkeypatch.chdir(tmp_path)

    result = workspace.run_local_tests(
        Path("relative-workspace") / "solution.py",
        timeout=1,
    )

    assert result.status is LocalTestStatus.PASSED
    assert result.stdout == "relative path works\n"


def test_assertion_failure_returns_controlled_failure(tmp_path: Path) -> None:
    solution_file = tmp_path / "solution.py"
    _write_solution(
        solution_file,
        """
def run_cases() -> None:
    print("before assertion")
    assert 1 == 2, "unexpected result"
""",
    )

    result = workspace.run_local_tests(solution_file, timeout=1)

    assert result.status is LocalTestStatus.FAILED
    assert result.stdout == "before assertion\n"
    assert result.stderr == "AssertionError: unexpected result\n"
    assert "Traceback" not in result.stderr


def test_runtime_error_returns_controlled_failure(tmp_path: Path) -> None:
    solution_file = tmp_path / "solution.py"
    _write_solution(
        solution_file,
        """
def run_cases() -> None:
    raise RuntimeError("simulated failure")
""",
    )

    result = workspace.run_local_tests(solution_file, timeout=1)

    assert result.status is LocalTestStatus.FAILED
    assert result.stderr == "RuntimeError: simulated failure\n"


@pytest.mark.parametrize(
    "definition",
    (
        "async def run_cases() -> None:",
        "def run_cases(value) -> None:",
        "def run_cases(value=1) -> None:",
        "def run_cases(*, value=1) -> None:",
        "def run_cases(*values) -> None:",
        "def run_cases(**values) -> None:",
    ),
)
def test_unsupported_run_cases_signature_is_rejected(
    tmp_path: Path,
    definition: str,
) -> None:
    solution_file = tmp_path / "solution.py"
    _write_solution(
        solution_file,
        f"""
{definition}
    print("must not run")
""",
    )

    result = workspace.run_local_tests(solution_file, timeout=1)

    assert result.status is LocalTestStatus.FAILED
    assert "必须是同步无参数函数" in result.stderr
    assert result.stdout == ""


def test_run_cases_does_not_read_interactive_terminal_input(tmp_path: Path) -> None:
    solution_file = tmp_path / "solution.py"
    _write_solution(
        solution_file,
        """
def run_cases() -> None:
    input("value: ")
""",
    )

    result = workspace.run_local_tests(solution_file, timeout=1)

    assert result.status is LocalTestStatus.FAILED
    assert result.stdout == "value: "
    assert "EOFError" in result.stderr


def test_run_cases_timeout_returns_controlled_result(tmp_path: Path) -> None:
    solution_file = tmp_path / "solution.py"
    _write_solution(
        solution_file,
        """
from time import sleep


def run_cases() -> None:
    print("before timeout")
    sleep(5)
""",
    )

    result = workspace.run_local_tests(solution_file, timeout=0.1)

    assert result.status is LocalTestStatus.TIMED_OUT
    assert result.stdout == "before timeout\n"
