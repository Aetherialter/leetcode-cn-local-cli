from getpass import getpass
from pathlib import Path
from typing import Annotated

from typer import BadParameter, Exit, Option

from leetcode_local_cli.commands import common
from leetcode_local_cli.commands.rendering import (
    info,
    loading,
    render_profile,
    success,
    warning,
)
from leetcode_local_cli.integrations.browser import BrowserKind
from leetcode_local_cli.integrations.devtools import parse_cookie_header
from leetcode_local_cli.use_cases.account import get_account_profile, get_user_status
from leetcode_local_cli.use_cases.errors import UseCaseError
from leetcode_local_cli.use_cases.login import (
    LoginReporter,
    try_automatic_login,
    validate_and_save_login,
)

LOGIN_REPORTER = LoginReporter(info=info, warning=warning, loading=loading)


def login(
    browser: Annotated[
        BrowserKind,
        Option(
            "--browser",
            help="登录浏览器：auto 依次尝试 Chrome、Edge；也可明确指定",
        ),
    ] = BrowserKind.AUTO,
    devtools_port: Annotated[
        int | None,
        Option(
            "--devtools-port",
            min=1,
            max=65535,
            help="高级用法：连接已开启的本机浏览器 DevTools 端口",
        ),
    ] = None,
) -> None:
    paths = common.get_user_paths()
    if devtools_port is not None and browser is BrowserKind.AUTO:
        raise BadParameter(
            "--devtools-port 必须与 --browser chrome 或 --browser edge 一起使用",
            param_hint="--devtools-port",
        )
    try:
        if try_automatic_login(
            browser,
            paths.session_file,
            reporter=LOGIN_REPORTER,
            devtools_port=devtools_port,
        ):
            success("成功登录")
            return
    except UseCaseError as exc:
        common.exit_for_use_case_error(exc)
    _login_manually(paths.session_file)


def _login_manually(session_file: Path) -> None:
    warning("无法自动获取 LeetCode 登录状态，请手动粘贴 Cookie")
    manual_cookies = get_cookies_from_input()
    if not manual_cookies:
        warning("未获取有效 Cookie")
        raise Exit(1)
    try:
        valid = validate_and_save_login(
            manual_cookies,
            source="manual",
            session_file=session_file,
        )
    except UseCaseError as exc:
        common.exit_for_use_case_error(exc)
    if not valid:
        warning("Cookie 无效或已过期")
        raise Exit(1)
    success("成功登录")


def status() -> None:
    try:
        user_status = get_user_status(common.get_user_paths())
    except UseCaseError as exc:
        common.exit_for_use_case_error(exc)
    username = user_status.username or "未知用户"
    success(f"在线状态: 当前账号 {username}")


def profile() -> None:
    try:
        with loading("正在获取账户信息..."):
            account_profile = get_account_profile(common.get_user_paths())
    except UseCaseError as exc:
        common.exit_for_use_case_error(exc)
    render_profile(account_profile)


def get_cookies_from_input() -> dict[str, str] | None:
    return parse_cookie_header(getpass("请粘贴 Cookie（输入内容不会回显）：\n"))
