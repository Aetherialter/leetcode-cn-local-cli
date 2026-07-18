"""Verify an installed release artifact without importing the source checkout."""

from importlib.metadata import version
import os
import subprocess


PACKAGE_NAME = "leetcode-local-cli"


def run_lc(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["lc", *arguments],
        capture_output=True,
        check=False,
        text=True,
    )


def main() -> None:
    expected_version = os.environ["LEETCODE_LOCAL_CLI_EXPECTED_VERSION"]
    installed_version = version(PACKAGE_NAME)
    if installed_version != expected_version:
        raise SystemExit(
            f"installed metadata version is {installed_version}, expected {expected_version}"
        )

    version_result = run_lc("--version")
    expected_output = f"{PACKAGE_NAME} {expected_version}"
    if (
        version_result.returncode != 0
        or version_result.stdout.strip() != expected_output
    ):
        raise SystemExit(
            "lc --version failed: "
            f"exit={version_result.returncode}, "
            f"stdout={version_result.stdout!r}, stderr={version_result.stderr!r}"
        )

    help_result = run_lc("--help")
    if help_result.returncode != 0 or "doctor" not in help_result.stdout:
        raise SystemExit(
            "lc --help failed: "
            f"exit={help_result.returncode}, "
            f"stdout={help_result.stdout!r}, stderr={help_result.stderr!r}"
        )

    print(f"verified {expected_output}")


if __name__ == "__main__":
    main()
