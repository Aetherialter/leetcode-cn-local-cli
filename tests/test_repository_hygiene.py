import json
import re
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SECRET_JSON_KEYS = {
    "accesskeyid",
    "accesstoken",
    "awsaccesskeyid",
    "awssecretaccesskey",
    "clientsecret",
    "csrftoken",
    "leetcodesession",
    "privatekey",
    "refreshtoken",
    "secretaccesskey",
}


def _git_check_ignore(relative_path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", relative_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _tracked_json_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--", "*.json"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=True,
        encoding="utf-8",
    )
    return [PROJECT_ROOT / path for path in result.stdout.splitlines()]


def _find_secret_keys(value: object) -> set[str]:
    found_keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested_value in value.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", str(key).casefold())
            if normalized_key in SECRET_JSON_KEYS:
                found_keys.add(str(key))
            found_keys.update(_find_secret_keys(nested_value))
    elif isinstance(value, list):
        for item in value:
            found_keys.update(_find_secret_keys(item))
    return found_keys


@pytest.mark.parametrize(
    "relative_path",
    [
        ".zed/settings.json",
        ".idea/workspace.xml",
        ".vscode/settings.json",
        ".cursor/settings.json",
        ".codex/session.json",
        ".leetcode_local_cli/workspace.toml",
        "solution.py",
        ".env.local",
        "credentials.json",
        "private/credentials.dev.json",
        "private/client_secret_account.json",
        "private/service-account-prod.json",
        "private/user.secret.json",
    ],
)
def test_personal_files_and_secret_json_names_are_ignored(
    relative_path: str,
) -> None:
    assert _git_check_ignore(relative_path)


@pytest.mark.parametrize(
    "relative_path",
    [
        ".github/workflows/release.yml",
        "docs/release-notes/v0.7.2.md",
        "tests/fixtures/problem.json",
        ".env.example",
    ],
)
def test_project_files_are_not_ignored(relative_path: str) -> None:
    assert not _git_check_ignore(relative_path)


def test_secret_json_key_detection_handles_nested_values() -> None:
    content = {
        "account": [
            {
                "private_key": "sensitive value must never be reported",
                "display_name": "example",
            }
        ]
    }

    assert _find_secret_keys(content) == {"private_key"}


def test_tracked_json_files_do_not_contain_secret_fields() -> None:
    findings: list[str] = []
    for file_path in _tracked_json_files():
        try:
            content = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        secret_keys = _find_secret_keys(content)
        if secret_keys:
            relative_path = file_path.relative_to(PROJECT_ROOT)
            findings.append(f"{relative_path}: {', '.join(sorted(secret_keys))}")

    assert not findings, "tracked JSON contains secret fields:\n" + "\n".join(findings)
