"""Verify an installed release artifact without importing the source checkout."""

import json
import os
import subprocess
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

PACKAGE_NAME = "leetcode-local-cli"


def run_lc(
    *arguments: str,
    environment: dict[str, str] | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["lc", *arguments],
        capture_output=True,
        check=False,
        encoding="utf-8",
        env=environment,
        input=input_text,
        timeout=30,
    )


def verify_isolated_workflow() -> None:
    from leetcode_local_cli.models.solution import ProblemMetadata
    from leetcode_local_cli.storage.solution import build_solution_content

    with TemporaryDirectory(prefix="lc-smoke-") as directory:
        root = Path(directory)
        environment = os.environ.copy()
        for key in (
            "APPDATA",
            "LOCALAPPDATA",
            "XDG_CONFIG_HOME",
            "XDG_STATE_HOME",
            "HOME",
            "USERPROFILE",
        ):
            path = root / key.lower()
            path.mkdir()
            environment[key] = str(path)
        missing = run_lc("test", "--stdin", environment=environment)
        assert missing.returncode == 1, missing.stderr
        assert json.loads(missing.stdout)["code"] == "workspace_config"
        configured = run_lc("config", "editor", "zed", environment=environment)
        assert configured.returncode == 0, configured.stderr
        workspace = root / "workspace"
        initialized = run_lc("init", str(workspace), "--yes", environment=environment)
        assert initialized.returncode == 0, initialized.stderr
        editor = run_lc("config", "editor", environment=environment)
        assert editor.returncode == 0 and '"zed"' in editor.stdout
        (workspace / "solution.py").write_text(
            "class Solution:\n    def answer(self, value):\n        return value + 1\n",
            encoding="utf-8",
        )
        tested = run_lc(
            "test",
            "--stdin",
            "--timeout",
            "10",
            environment=environment,
            input_text="value = 41\n",
        )
        assert tested.returncode == 0, (tested.stdout, tested.stderr)
        events = [json.loads(line) for line in tested.stdout.splitlines()]
        assert events[0]["ok"] and events[0]["result"] == 42
        assert events[-1]["kind"] == "summary" and events[-1]["failed"] == 0
        (workspace / "solution.py").write_text(
            build_solution_content(
                "class Solution:\n"
                "    def echo(self, root: Optional[TreeNode]) -> Optional[TreeNode]:\n"
                "        return root\n",
                ProblemMetadata("1", "1", "Example", "example"),
            ),
            encoding="utf-8",
        )
        nodes = run_lc(
            "test",
            "--stdin",
            "--timeout",
            "10",
            environment=environment,
            input_text="root = [1, null, 2, 3]\nroot = []\n",
        )
        assert nodes.returncode == 0, (nodes.stdout, nodes.stderr)
        node_events = [json.loads(line) for line in nodes.stdout.splitlines()]
        assert node_events[0]["result"] == [1, None, 2, 3]
        assert node_events[1]["result"] == []


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

    verify_isolated_workflow()
    print(
        f"verified {expected_output}: entry points, editor settings, isolated init, local worker, nodes"
    )


if __name__ == "__main__":
    main()
