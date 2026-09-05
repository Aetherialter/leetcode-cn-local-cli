from leetcode_local_cli.integrations.leetcode import LeetCodeClient
from leetcode_local_cli.models.account import AccountProfile, UserStatus
from leetcode_local_cli.models.result import ClientErrorKind, ClientFailure
from leetcode_local_cli.storage.paths import UserPaths
from leetcode_local_cli.use_cases.common import (
    client_error_message,
    load_cookies_from_session,
)
from leetcode_local_cli.use_cases.errors import ErrorCode, UseCaseError


def get_user_status(paths: UserPaths) -> UserStatus:
    with LeetCodeClient(load_cookies_from_session(paths)) as client:
        result = client.user_status()
    if isinstance(result, ClientFailure):
        raise UseCaseError(client_error_message(result.error), code=ErrorCode.CLIENT)
    if not result.data.signed_in:
        raise UseCaseError(
            client_error_message(ClientErrorKind.UNAUTHORIZED), code=ErrorCode.CLIENT
        )
    return result.data


def get_account_profile(paths: UserPaths) -> AccountProfile:
    with LeetCodeClient(load_cookies_from_session(paths)) as client:
        status = client.user_status()
        if isinstance(status, ClientFailure):
            raise UseCaseError(
                client_error_message(status.error), code=ErrorCode.CLIENT
            )
        if not status.data.signed_in:
            raise UseCaseError(
                client_error_message(ClientErrorKind.UNAUTHORIZED),
                code=ErrorCode.CLIENT,
            )
        stats = client.problem_stats()
    if isinstance(stats, ClientFailure):
        raise UseCaseError(client_error_message(stats.error), code=ErrorCode.CLIENT)
    return AccountProfile(status.data, stats.data)
