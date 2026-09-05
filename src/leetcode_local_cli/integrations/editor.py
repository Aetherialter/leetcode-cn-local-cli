import os
import subprocess
import sys
from pathlib import Path


class EditorError(OSError):
    pass


def open_path(path: Path) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(path)
        else:
            command = "open" if sys.platform == "darwin" else "xdg-open"
            result = subprocess.run(
                [command, str(path)], capture_output=True, timeout=10
            )
            if result.returncode:
                raise EditorError("无法打开文件，请手动打开 solution.py")
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EditorError("无法打开文件，请手动打开 solution.py") from exc
