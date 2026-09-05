from pathlib import Path

import pytest

from leetcode_local_cli.storage import safe_files as safe_files
from leetcode_local_cli.storage.safe_files import SafeFileError


@pytest.mark.parametrize("existing_content", (None, "old content"))
def test_atomic_write_text_creates_or_replaces_regular_file(
    tmp_path: Path,
    existing_content: str | None,
) -> None:
    target = tmp_path / "target.txt"
    if existing_content is not None:
        target.write_text(existing_content, encoding="utf-8")

    safe_files.atomic_write_text(target, "new content", label="测试文件")

    assert target.read_text(encoding="utf-8") == "new content"
    assert list(tmp_path.glob(".target.txt.*.tmp")) == []


def test_atomic_write_text_preserves_old_file_when_replace_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    target = tmp_path / "target.txt"
    target.write_text("old content", encoding="utf-8")

    def fail_replace(source: Path, destination: Path) -> None:
        raise PermissionError("simulated replace failure")

    monkeypatch.setattr(safe_files.os, "replace", fail_replace)

    with pytest.raises(SafeFileError, match="无法写入测试文件"):
        safe_files.atomic_write_text(target, "new content", label="测试文件")

    assert target.read_text(encoding="utf-8") == "old content"
    assert list(tmp_path.glob(".target.txt.*.tmp")) == []


def test_atomic_write_text_rejects_symlink_without_touching_external_file(
    tmp_path: Path,
) -> None:
    external_file = tmp_path / "external.txt"
    external_file.write_text("external content", encoding="utf-8")
    target = tmp_path / "target.txt"
    try:
        target.symlink_to(external_file)
    except OSError as exc:
        pytest.skip(f"symbolic links are unavailable: {exc}")

    with pytest.raises(SafeFileError, match="符号链接"):
        safe_files.atomic_write_text(target, "new content", label="测试文件")

    assert target.is_symlink()
    assert external_file.read_text(encoding="utf-8") == "external content"


def test_create_empty_regular_file_preserves_existing_content(tmp_path: Path) -> None:
    target = tmp_path / "solution.py"
    target.write_text("user code", encoding="utf-8")

    created = safe_files.create_empty_regular_file(target, label="solution.py")

    assert not created
    assert target.read_text(encoding="utf-8") == "user code"


def test_validate_regular_file_target_rejects_directory(tmp_path: Path) -> None:
    target = tmp_path / "solution.py"
    target.mkdir()

    with pytest.raises(SafeFileError, match="是目录"):
        safe_files.validate_regular_file_target(target, label="solution.py")
