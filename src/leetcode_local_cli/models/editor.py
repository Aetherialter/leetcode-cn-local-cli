from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EditorConfig:
    command: str
    args: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.command.strip() or any(
            ord(c) < 32 or ord(c) == 127 for c in self.command
        ):
            raise ValueError("编辑器命令必须是非空程序名或绝对路径，不能含控制字符")
        if ("/" in self.command or "\\" in self.command) and not Path(
            self.command
        ).is_absolute():
            raise ValueError("编辑器路径必须是绝对路径")
        if any("\x00" in arg for arg in self.args):
            raise ValueError("编辑器参数不能包含 NUL 字符")
