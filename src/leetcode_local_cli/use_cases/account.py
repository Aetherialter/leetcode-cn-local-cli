from typing import Any

from leetcode_local_cli.client import ClientErrorKind, LeetCodeClient
from leetcode_local_cli.paths import AppPaths
from leetcode_local_cli.use_cases.common import (
    UseCaseError,
    client_error_message,
    load_cookies_from_session,
)


def get_user_status(paths: AppPaths) -> dict[str, Any]:
    cookies = load_cookies_from_session(paths)
    with LeetCodeClient(cookies) as client:
        user_status = client.user_status()
    if not user_status.ok:
        raise UseCaseError(client_error_message(user_status.error))
    status = user_status.data
    if not isinstance(status, dict) or not status.get("isSignedIn"):
        raise UseCaseError(client_error_message(ClientErrorKind.UNAUTHORIZED))
    return status


def get_account_profile(paths: AppPaths) -> dict[str, Any]:
    cookies = load_cookies_from_session(paths)
    with LeetCodeClient(cookies) as client:
        account_profile = client.account_profile()
    if not account_profile.ok:
        raise UseCaseError(client_error_message(account_profile.error))
    if not isinstance(account_profile.data, dict):
        raise UseCaseError(client_error_message(ClientErrorKind.INVALID_RESPONSE))
    return account_profile.data
