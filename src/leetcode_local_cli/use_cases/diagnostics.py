from leetcode_local_cli.auth import (
    REQUIRED_COOKIE_NAMES,
    SessionFileError,
    load_session,
)
from leetcode_local_cli.client import LeetCodeClient
from leetcode_local_cli.doctor import (
    DoctorReport,
    diagnose_remote,
    diagnose_session,
    diagnose_solution,
)
from leetcode_local_cli.paths import AppPaths


def get_doctor_report(
    paths: AppPaths,
    *,
    run_solution: bool = False,
) -> DoctorReport:
    session_check = diagnose_session(paths.session_file)
    solution_check = diagnose_solution(
        paths.solution_file,
        run_solution=run_solution,
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
            solution_check,
        )
    )
