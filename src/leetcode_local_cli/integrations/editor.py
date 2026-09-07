import shutil
import subprocess
import sys
from pathlib import Path

from leetcode_local_cli.models.editor import EditorConfig


class EditorError(OSError):
    pass


def _editor_executable(command: str) -> str:
    requested = "code" if command == "vscode" else command
    executable = shutil.which(requested)
    if executable is None:
        raise EditorError("找不到已配置的编辑器，请检查 PATH 或配置可执行文件绝对路径")
    if sys.platform == "win32" and Path(executable).suffix.lower() in {".cmd", ".bat"}:
        # VS Code's Windows PATH entry is a batch launcher; use its native sibling.
        native = Path(executable).parent.parent / "Code.exe"
        if command not in {"code", "vscode"} or not native.is_file():
            raise EditorError("不执行 Windows 批处理编辑器，请指定 .exe 可执行文件")
        return str(native)
    return executable


def open_path(path: Path, editor: EditorConfig | None = None) -> None:
    if editor is None:
        raise EditorError("未配置编辑器；文件已保存，可执行 lc config editor zed")
    executable = _editor_executable(editor.command)
    try:
        process = subprocess.Popen(
            [executable, *editor.args, "--", str(path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=path.parent,
        )
        try:
            returncode = process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            # A GUI editor can stay alive; do not kill it just for being long-lived.
            return
        if returncode:
            raise EditorError("编辑器启动失败；文件已保存，请检查编辑器配置")
    except OSError as exc:
        raise EditorError("编辑器启动失败；文件已保存，请检查编辑器配置") from exc
