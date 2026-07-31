import os
import stat
import subprocess
from types import SimpleNamespace

import pytest

from leetcode_local_cli import workspace
from leetcode_local_cli.safe_files import SafeFileError, is_windows_reparse_point
from leetcode_local_cli.workspace import (
    ProblemMetadata,
    SolutionFileStatus,
    WorkspaceError,
)


def test_build_solution_content_writes_metadata_and_submit_markers(tmp_path) -> None:
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
    assert "def run_cases() -> None:" not in content
    solution_file = tmp_path / "solution.py"
    solution_file.write_text(content, encoding="utf-8")
    _, submission_code = workspace.parse_solution_submission(solution_file)
    assert "run_cases" not in submission_code


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


@pytest.mark.parametrize("existing_content", [None, "previous solution"])
def test_write_solution_file_creates_or_overwrites_regular_file(
    tmp_path,
    monkeypatch,
    existing_content,
) -> None:
    solution_file = tmp_path / "solution.py"
    if existing_content is not None:
        solution_file.write_text(existing_content, encoding="utf-8")
    opened_paths = []
    monkeypatch.setattr(workspace, "open_path", opened_paths.append)

    workspace.write_solution_file(
        solution_file,
        "class Solution:\n    pass",
        ProblemMetadata("1", "1", "Two Sum", "two-sum"),
    )

    content = solution_file.read_text(encoding="utf-8")
    assert existing_content is None or existing_content not in content
    assert "class Solution:\n    pass" in content
    assert opened_paths == [solution_file]


@pytest.mark.parametrize("target_exists", [True, False])
def test_write_solution_file_rejects_existing_and_broken_symlinks(
    tmp_path,
    monkeypatch,
    target_exists,
) -> None:
    target = tmp_path / "outside.py"
    if target_exists:
        target.write_text("must remain unchanged", encoding="utf-8")
    solution_file = tmp_path / "solution.py"
    try:
        solution_file.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symbolic links are unavailable: {exc}")
    monkeypatch.setattr(
        workspace,
        "open_path",
        lambda path: pytest.fail("rejected target must not be opened"),
    )

    with pytest.raises(WorkspaceError, match="符号链接或断链"):
        workspace.write_solution_file(
            solution_file,
            "class Solution:\n    pass",
            ProblemMetadata("1", "1", "Two Sum", "two-sum"),
        )

    assert solution_file.is_symlink()
    if target_exists:
        assert target.read_text(encoding="utf-8") == "must remain unchanged"
    else:
        assert not target.exists()


def test_write_solution_file_rejects_directory_symlink(
    tmp_path,
    monkeypatch,
) -> None:
    target_directory = tmp_path / "outside-directory"
    target_directory.mkdir()
    solution_file = tmp_path / "solution.py"
    try:
        solution_file.symlink_to(target_directory, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symbolic links are unavailable: {exc}")
    monkeypatch.setattr(
        workspace,
        "open_path",
        lambda path: pytest.fail("rejected target must not be opened"),
    )

    with pytest.raises(WorkspaceError, match="符号链接或断链"):
        workspace.write_solution_file(
            solution_file,
            "class Solution:\n    pass",
            ProblemMetadata("1", "1", "Two Sum", "two-sum"),
        )

    assert solution_file.is_symlink()
    assert list(target_directory.iterdir()) == []


def test_write_solution_file_rejects_directory(tmp_path, monkeypatch) -> None:
    solution_file = tmp_path / "solution.py"
    solution_file.mkdir()
    monkeypatch.setattr(
        workspace,
        "open_path",
        lambda path: pytest.fail("rejected target must not be opened"),
    )

    with pytest.raises(WorkspaceError, match="是目录"):
        workspace.write_solution_file(
            solution_file,
            "class Solution:\n    pass",
            ProblemMetadata("1", "1", "Two Sum", "two-sum"),
        )

    assert solution_file.is_dir()


def test_windows_reparse_point_attribute_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        stat,
        "FILE_ATTRIBUTE_REPARSE_POINT",
        0x400,
        raising=False,
    )
    file_status = SimpleNamespace(st_file_attributes=0x400)

    assert is_windows_reparse_point(file_status)


@pytest.mark.skipif(os.name != "nt", reason="junctions are Windows-specific")
def test_write_solution_file_rejects_windows_junction(
    tmp_path,
    monkeypatch,
) -> None:
    target_directory = tmp_path / "junction-target"
    target_directory.mkdir()
    junction = tmp_path / "solution.py"
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(target_directory)],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode:
        pytest.skip(f"could not create test junction: {result.stderr}")
    assert junction.is_junction()
    monkeypatch.setattr(
        workspace,
        "open_path",
        lambda path: pytest.fail("rejected target must not be opened"),
    )

    with pytest.raises(WorkspaceError, match="reparse point"):
        workspace.write_solution_file(
            junction,
            "class Solution:\n    pass",
            ProblemMetadata("1", "1", "Two Sum", "two-sum"),
        )

    assert junction.is_junction()
    assert list(target_directory.iterdir()) == []


def test_write_solution_file_wraps_write_errors(tmp_path, monkeypatch) -> None:
    solution_file = tmp_path / "solution.py"
    solution_file.write_text("previous solution", encoding="utf-8")
    monkeypatch.setattr(
        workspace,
        "atomic_write_text",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            SafeFileError("无法写入 solution.py")
        ),
    )
    monkeypatch.setattr(
        workspace,
        "open_path",
        lambda path: pytest.fail("failed write must not be opened"),
    )

    with pytest.raises(WorkspaceError, match="无法写入 solution.py"):
        workspace.write_solution_file(
            solution_file,
            "class Solution:\n    pass",
            ProblemMetadata("1", "1", "Two Sum", "two-sum"),
        )


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
    metadata, code = workspace.parse_solution_submission(solution_file)

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
    with pytest.raises(WorkspaceError, match="提交区域标记不完整"):
        workspace.parse_solution_submission(solution_file)


def test_parse_solution_submission_reports_missing_file(tmp_path) -> None:
    with pytest.raises(WorkspaceError, match="未找到 solution.py"):
        workspace.parse_solution_submission(tmp_path / "missing.py")


def test_parse_solution_submission_rejects_non_utf8_source(tmp_path) -> None:
    solution_file = tmp_path / "solution.py"
    solution_file.write_bytes(b"\xff\xfeinvalid source")

    with pytest.raises(WorkspaceError, match="不是有效的 UTF-8 编码"):
        workspace.parse_solution_submission(solution_file)


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
    with pytest.raises(WorkspaceError, match="缺少元数据"):
        workspace.parse_solution_submission(solution_file)


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


def test_inspect_solution_file_distinguishes_invalid_encoding(tmp_path) -> None:
    solution_file = tmp_path / "solution.py"
    solution_file.write_bytes(b"\x81invalid source")

    result = workspace.inspect_solution_file(solution_file)

    assert result.status is SolutionFileStatus.INVALID_ENCODING
    assert "不是有效的 UTF-8 编码" in result.detail


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


def test_inspect_solution_file_accepts_utf8_bom(tmp_path) -> None:
    solution_file = tmp_path / "solution.py"
    metadata = ProblemMetadata("1", "1", "Two Sum", "two-sum")
    solution_file.write_text(
        workspace.build_solution_content("class Solution:\n    pass", metadata),
        encoding="utf-8-sig",
    )

    result = workspace.inspect_solution_file(solution_file)

    assert result.status is SolutionFileStatus.READY
    assert result.metadata == metadata
