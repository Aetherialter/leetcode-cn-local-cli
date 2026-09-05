from pathlib import Path
from typing import Annotated

from typer import Argument, BadParameter, Exit, Option, confirm, prompt

from leetcode_local_cli.commands.common import exit_for_use_case_error
from leetcode_local_cli.commands.rendering import error, info, success, warning
from leetcode_local_cli.storage.paths import (
    APP_DIRECTORY_NAME,
    get_user_config_file,
    normalize_workspace_path,
)
from leetcode_local_cli.use_cases.errors import UseCaseError
from leetcode_local_cli.use_cases.setup import (
    configure_workspace,
    resolve_existing_workspace,
)


def init_workspace(
    path: Annotated[
        Path | None,
        Argument(help="工作区完整路径；省略时交互输入父目录"),
    ] = None,
    yes: Annotated[
        bool,
        Option("--yes", help="使用显式路径初始化并跳过交互确认"),
    ] = False,
    repair: Annotated[
        bool, Option("--repair", help="备份并恢复损坏的用户配置和目标工作区标记")
    ] = False,
) -> None:
    """配置默认工作区，并安全创建工作区基础文件。"""
    config_file = get_user_config_file()
    if repair and path is None:
        raise BadParameter(
            "--repair 必须与工作区完整路径一起使用", param_hint="--repair"
        )
    if path is None:
        try:
            existing_paths = resolve_existing_workspace(config_file)
        except UseCaseError as exc:
            exit_for_use_case_error(exc)
        if existing_paths is not None:
            success(f"继续使用现有工作区：{existing_paths.workspace_root}")
            return

        if yes:
            error("--yes 必须与工作区完整路径一起使用")
            raise Exit(1)
        parent_value = prompt("请输入工作区父目录").strip()
        if not parent_value:
            error("工作区父目录不能为空")
            raise Exit(1)
        workspace_root = normalize_workspace_path(parent_value) / APP_DIRECTORY_NAME
    else:
        workspace_root = normalize_workspace_path(path)

    info(f"工作区将配置为：{workspace_root}")
    if not yes and not confirm("确认继续？"):
        warning("已取消工作区配置")
        return

    try:
        result = configure_workspace(
            workspace_root, config_file=config_file, repair=repair
        )
    except UseCaseError as exc:
        exit_for_use_case_error(exc)

    for backup in result.backups:
        info(f"原始配置已备份：{backup}")
    if result.reused:
        success(f"工作区已配置，现有文件保持不变：{result.paths.workspace_root}")
    else:
        success(f"工作区配置完成：{result.paths.workspace_root}")
