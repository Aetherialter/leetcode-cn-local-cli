import subprocess
import sys
from pathlib import Path

import pytest

from leetcode_local_cli.integrations import editor
from leetcode_local_cli.models.editor import EditorConfig


@pytest.mark.parametrize("outcome", ["success", "running", "nonzero", "missing"])
def test_editor_passes_literal_arguments_and_classifies_failure(
    tmp_path, monkeypatch, outcome
) -> None:
    path = tmp_path / "space ; & literal.py"
    monkeypatch.setattr(editor.shutil, "which", lambda command: "/editor.exe")

    class Process:
        def wait(self, *, timeout):
            assert timeout == 1
            if outcome == "running":
                raise subprocess.TimeoutExpired("editor", timeout)
            return 1 if outcome == "nonzero" else 0

    def popen(arguments, *, stdin, stdout, stderr, cwd):
        assert arguments == ["/editor.exe", "--reuse-window", "--", str(path)]
        assert stdin == stdout == stderr == subprocess.DEVNULL
        assert cwd == path.parent
        if outcome == "missing":
            raise FileNotFoundError("synthetic failure")
        return Process()

    monkeypatch.setattr(editor.subprocess, "Popen", popen)
    settings = EditorConfig("zed", ("--reuse-window",))
    if outcome in {"success", "running"}:
        editor.open_path(path, settings)
    else:
        with pytest.raises(editor.EditorError, match="文件已保存"):
            editor.open_path(path, settings)


def test_missing_or_unconfigured_editor_never_uses_system_association(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(editor.shutil, "which", lambda command: None)
    monkeypatch.setattr(
        editor.subprocess, "Popen", lambda *a, **k: pytest.fail("must not launch")
    )
    with pytest.raises(editor.EditorError, match="未配置"):
        editor.open_path(tmp_path / "solution.py")
    with pytest.raises(editor.EditorError, match="找不到"):
        editor.open_path(tmp_path / "solution.py", EditorConfig("missing"))


def test_windows_vscode_uses_native_executable_not_batch(tmp_path, monkeypatch) -> None:
    launcher = tmp_path / "bin" / "code.cmd"
    native = tmp_path / "Code.exe"
    native.touch()
    monkeypatch.setattr(editor.sys, "platform", "win32")
    monkeypatch.setattr(editor.shutil, "which", lambda command: str(launcher))
    assert editor._editor_executable("vscode") == str(native)
    with pytest.raises(editor.EditorError, match="批处理"):
        editor._editor_executable(str(launcher))
    native.unlink()
    with pytest.raises(editor.EditorError, match="批处理"):
        editor._editor_executable("code")


def test_editor_launches_real_harmless_process_with_literal_path(
    tmp_path: Path,
) -> None:
    recorder = tmp_path / "record.py"
    output = tmp_path / "record.txt"
    recorder.write_text(
        "import pathlib, sys\n"
        "pathlib.Path(sys.argv[1]).write_text(repr(sys.argv[2:]), encoding='utf-8')\n",
        encoding="utf-8",
    )
    solution = tmp_path / "a ; & b.py"
    editor.open_path(
        solution, EditorConfig(sys.executable, (str(recorder), str(output)))
    )
    assert output.read_text(encoding="utf-8") == repr(["--", str(solution)])
