import json
from typing import Annotated

from typer import Argument, BadParameter, Option, Typer

from leetcode_local_cli.commands import common
from leetcode_local_cli.commands.rendering import info, success
from leetcode_local_cli.models.editor import EditorConfig
from leetcode_local_cli.use_cases.errors import UseCaseError
from leetcode_local_cli.use_cases.settings import configure_editor, get_editor

config_app = Typer(help="管理当前用户的设置", no_args_is_help=True)


@config_app.command("editor")
def editor_settings(
    command: Annotated[
        str | None, Argument(help="zed、code、vscode 或编辑器可执行文件绝对路径")
    ] = None,
    args: Annotated[
        list[str] | None,
        Option("--arg", help="程序参数，可重复；以 - 开头时使用 --arg=值"),
    ] = None,
    clear: Annotated[bool, Option("--clear", help="移除用户编辑器设置")] = False,
) -> None:
    if clear and (command is not None or args):
        raise BadParameter("--clear 不能与编辑器命令或参数同时使用")
    if args and command is None:
        raise BadParameter("--arg 必须同时指定编辑器命令")
    try:
        paths = common.get_user_paths()
        if clear:
            configure_editor(paths, None)
            success("已移除编辑器设置")
        elif command is not None:
            try:
                editor = EditorConfig(command, tuple(args or ()))
            except ValueError as exc:
                raise BadParameter(str(exc)) from exc
            configure_editor(paths, editor)
            success(f"已设置编辑器：{editor.command}")
        else:
            editor = get_editor(paths)
            info(
                json.dumps([editor.command, *editor.args], ensure_ascii=False)
                if editor
                else "未配置编辑器，可执行 lc config editor zed"
            )
    except UseCaseError as exc:
        common.exit_for_use_case_error(exc)
