import pytest

from aether_lc import workspace
from aether_lc.workspace import (
    ProblemMetadata,
    SolutionFileStatus,
    WorkspaceError,
)


def test_build_solution_content_writes_metadata_and_submit_markers() -> None:
    metadata = ProblemMetadata(
        problem_id="1",
        submit_question_id="1",
        title="Two Sum",
        title_slug="two-sum",
    )

    content = workspace.build_solution_content(
        "class Solution:\n    pass",
        metadata,
    )

    assert "# @lc problem_id: 1" in content
    assert "# @lc submit_question_id: 1" in content
    assert "# @lc title: Two Sum" in content
    assert "# @lc title_slug: two-sum" in content
    assert "# pyright: reportUnusedImport=false, reportUnusedVariable=false" in content
    assert "# ruff: noqa: F401, F841" in content
    assert "from typing import Any, Dict, List, Optional, Set, Tuple" in content
    assert "# @lc submit_begin" in content
    assert "# @lc submit_end" in content
    assert "def run_cases() -> None:" in content


def test_build_solution_content_adds_lightweight_pass_placeholder() -> None:
    metadata = ProblemMetadata(
        problem_id="1",
        submit_question_id="1",
        title="Two Sum",
        title_slug="two-sum",
    )

    content = workspace.build_solution_content(
        "class Solution:\n    def twoSum(self, nums: List[int], target: int) -> List[int]:",
        metadata,
    )

    assert (
        "def twoSum(self, nums: List[int], target: int) -> List[int]: pass" in content
    )


def test_build_solution_content_does_not_duplicate_existing_pass() -> None:
    metadata = ProblemMetadata("1", "1", "Two Sum", "two-sum")

    content = workspace.build_solution_content("class Solution:\n    pass", metadata)

    assert "pass pass" not in content
    compile(content, "solution.py", "exec")


def test_parse_solution_submission_reads_metadata_and_submit_code(
    tmp_path,
    monkeypatch,
) -> None:
    solution_file = tmp_path / "solution.py"
    solution_file.write_text(
        "\n".join(
            [
                "# @lc problem_id: 1",
                "# @lc submit_question_id: 1",
                "# @lc title: Two Sum",
                "# @lc title_slug: two-sum",
                "",
                "# @lc submit_begin",
                "class Solution:",
                "    pass",
                "# @lc submit_end",
                "",
                "def run_cases() -> None:",
                "    pass",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(workspace, "SOLUTION_FILE", solution_file)

    metadata, code = workspace.parse_solution_submission()

    assert metadata == ProblemMetadata(
        problem_id="1",
        submit_question_id="1",
        title="Two Sum",
        title_slug="two-sum",
    )
    assert code == "class Solution:\n    pass"


def test_parse_solution_submission_rejects_missing_marker(
    tmp_path,
    monkeypatch,
) -> None:
    solution_file = tmp_path / "solution.py"
    solution_file.write_text(
        "\n".join(
            [
                "# @lc problem_id: 1",
                "# @lc submit_question_id: 1",
                "# @lc title: Two Sum",
                "# @lc title_slug: two-sum",
                "class Solution:",
                "    pass",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(workspace, "SOLUTION_FILE", solution_file)

    with pytest.raises(WorkspaceError, match="提交区域标记不完整"):
        workspace.parse_solution_submission()


def test_parse_solution_submission_reports_missing_file(tmp_path) -> None:
    with pytest.raises(WorkspaceError, match="未找到 solution.py"):
        workspace.parse_solution_submission(tmp_path / "missing.py")


def test_parse_solution_submission_rejects_missing_submit_question_id(
    tmp_path,
    monkeypatch,
) -> None:
    solution_file = tmp_path / "solution.py"
    solution_file.write_text(
        "\n".join(
            [
                "# @lc problem_id: 2161",
                "# @lc title: 根据给定数字划分数组",
                "# @lc title_slug: partition-array-according-to-given-pivot",
                "",
                "# @lc submit_begin",
                "class Solution:",
                "    pass",
                "# @lc submit_end",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(workspace, "SOLUTION_FILE", solution_file)

    with pytest.raises(WorkspaceError, match="缺少元数据"):
        workspace.parse_solution_submission()


def test_inspect_solution_file_reports_missing_and_empty(tmp_path) -> None:
    missing = workspace.inspect_solution_file(tmp_path / "missing.py")
    empty_file = tmp_path / "empty.py"
    empty_file.write_text("", encoding="utf-8")

    assert missing.status is SolutionFileStatus.MISSING
    assert (
        workspace.inspect_solution_file(empty_file).status is SolutionFileStatus.EMPTY
    )


def test_inspect_solution_file_reports_read_and_syntax_errors(tmp_path) -> None:
    read_error = workspace.inspect_solution_file(tmp_path)
    invalid_file = tmp_path / "invalid.py"
    invalid_file.write_text("def broken(:\n", encoding="utf-8")
    invalid = workspace.inspect_solution_file(invalid_file)

    assert read_error.status is SolutionFileStatus.READ_ERROR
    assert invalid.status is SolutionFileStatus.INVALID_SYNTAX
    assert invalid.syntax_line == 1


def test_inspect_solution_file_reports_not_submittable_valid_python(tmp_path) -> None:
    solution_file = tmp_path / "solution.py"
    solution_file.write_text("class Solution:\n    pass\n", encoding="utf-8")

    result = workspace.inspect_solution_file(solution_file)

    assert result.status is SolutionFileStatus.NOT_SUBMITTABLE
    assert "提交区域标记不完整" in result.detail


def test_inspect_solution_file_reports_ready_generated_workspace(tmp_path) -> None:
    solution_file = tmp_path / "solution.py"
    metadata = ProblemMetadata("1", "1", "Two Sum", "two-sum")
    solution_file.write_text(
        workspace.build_solution_content("class Solution:\n    pass", metadata),
        encoding="utf-8",
    )

    result = workspace.inspect_solution_file(solution_file)

    assert result.status is SolutionFileStatus.READY
    assert result.metadata == metadata
