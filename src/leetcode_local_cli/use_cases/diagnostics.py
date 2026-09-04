from leetcode_local_cli.auth import (
    REQUIRED_COOKIE_NAMES,
    SessionFileError,
    load_session,
)
from leetcode_local_cli.client import LeetCodeClient
from leetcode_local_cli.config import (
    ConfigError,
    load_user_config,
    resolve_workspace_paths,
)
from leetcode_local_cli.doctor import (
    DoctorReport,
    DoctorCheck,
    DoctorStatus,
    SOLUTION_CHECK_NAME,
    WORKSPACE_CHECK_NAME,
    diagnose_remote,
    diagnose_session,
    diagnose_solution,
)
from leetcode_local_cli.paths import UserPaths, WorkspacePaths


def get_doctor_report(
    paths: UserPaths,
    *,
    run_solution: bool = False,
) -> DoctorReport:
    session_check = diagnose_session(paths.session_file)
    workspace_check, workspace_paths = _diagnose_workspace(
        paths,
        required=run_solution,
    )
    solution_check = (
        diagnose_solution(
            workspace_paths.solution_file,
            run_solution=run_solution,
        )
        if workspace_paths is not None
        else DoctorCheck(
            name=SOLUTION_CHECK_NAME,
            status=DoctorStatus.WARNING,
            message="未检查（工作区不可用）",
        )
    )

    cookies: dict[str, str] | None = None
    try:
        session = load_session(paths.session_file)
    except SessionFileError:
        session = None
    if isinstance(session, dict):
        raw_cookies = session.get("cookies")
        if isinstance(raw_cookies, dict):
            valid_cookies: dict[str, str] = {}
            for name in REQUIRED_COOKIE_NAMES:
                value = raw_cookies.get(name)
                if not isinstance(value, str) or not value:
                    break
                valid_cookies[name] = value
            else:
                cookies = valid_cookies

    with LeetCodeClient(cookies) as client:
        remote_result = client.user_status()
    connectivity_check, authentication_check = diagnose_remote(remote_result)
    return DoctorReport(
        checks=(
            session_check,
            connectivity_check,
            authentication_check,
            workspace_check,
            solution_check,
        )
    )


def _diagnose_workspace(
    paths: UserPaths,
    *,
    required: bool,
) -> tuple[DoctorCheck, WorkspacePaths | None]:
    try:
        user_config = load_user_config(paths.user_config_file)
    except ConfigError as exc:
        return (
            DoctorCheck(
                name=WORKSPACE_CHECK_NAME,
                status=DoctorStatus.FAIL,
                message=str(exc),
                suggestion="请执行 lc init <完整路径> 重新配置工作区",
            ),
            None,
        )

    if user_config is None:
        return (
            DoctorCheck(
                name=WORKSPACE_CHECK_NAME,
                status=DoctorStatus.FAIL if required else DoctorStatus.WARNING,
                message="尚未配置工作区",
                suggestion="需要本地解题时请执行 lc init",
            ),
            None,
        )

    try:
        workspace_paths = resolve_workspace_paths(paths.user_config_file)
    except ConfigError as exc:
        return (
            DoctorCheck(
                name=WORKSPACE_CHECK_NAME,
                status=DoctorStatus.FAIL,
                message=str(exc),
                suggestion="请执行 lc init <完整路径> 重新配置工作区",
            ),
            None,
        )

    return (
        DoctorCheck(
            name=WORKSPACE_CHECK_NAME,
            status=DoctorStatus.PASS,
            message=f"已配置：{workspace_paths.workspace_root}",
        ),
        workspace_paths,
    )
