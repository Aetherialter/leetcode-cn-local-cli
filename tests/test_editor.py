import subprocess
from pathlib import Path

import pytest

from leetcode_local_cli.integrations import editor


@pytest.mark.parametrize(
    "platform, command", [("darwin", "open"), ("linux", "xdg-open")]
)
@pytest.mark.parametrize("outcome", ["success", "nonzero", "timeout", "missing"])
def test_editor_uses_argument_array_and_classifies_failure(
    tmp_path, monkeypatch, platform, command, outcome
) -> None:
    path = tmp_path / "space ; literal.py"
    monkeypatch.setattr(editor.sys, "platform", platform)

    def run(arguments, *, capture_output, timeout):
        assert arguments == [command, str(path)]
        assert capture_output and timeout == 10
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(arguments, timeout)
        if outcome == "missing":
            raise FileNotFoundError("synthetic failure")
        return subprocess.CompletedProcess(arguments, 1 if outcome == "nonzero" else 0)

    monkeypatch.setattr(editor.subprocess, "run", run)
    if outcome == "success":
        editor.open_path(path)
    else:
        with pytest.raises(editor.EditorError):
            editor.open_path(path)


def test_windows_editor_passes_path_without_shell(tmp_path: Path, monkeypatch) -> None:
    opened = []
    monkeypatch.setattr(editor.sys, "platform", "win32")
    monkeypatch.setattr(editor.os, "startfile", opened.append, raising=False)
    path = tmp_path / "space ; literal.py"
    editor.open_path(path)
    assert opened == [path]
