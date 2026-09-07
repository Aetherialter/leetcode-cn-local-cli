import os
from pathlib import Path
import subprocess
import tomllib

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_FILE = PROJECT_ROOT / "pyproject.toml"
RELEASE_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "release.yml"
RELEASE_NOTES_DIR = PROJECT_ROOT / "docs" / "release-notes"
SMOKE_TEST = PROJECT_ROOT / "scripts" / "smoke_test.py"


def test_current_version_has_well_formed_release_notes() -> None:
    with PYPROJECT_FILE.open("rb") as file:
        version = tomllib.load(file)["project"]["version"]

    notes_file = RELEASE_NOTES_DIR / f"v{version}.md"
    lines = notes_file.read_text(encoding="utf-8").splitlines()

    assert lines[0].startswith(f"v{version} — ")
    assert lines[1] == ""
    assert f"leetcode-local-cli {version}" in "\n".join(lines[2:])


def test_release_workflow_uses_versioned_title_and_notes() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "docs/release-notes/${GITHUB_REF_NAME}.md" in workflow
    assert '--title "$release_title"' in workflow
    assert '--notes-file "$notes_file"' in workflow


def test_release_smoke_test_decodes_cli_output_as_utf8() -> None:
    smoke_test = SMOKE_TEST.read_text(encoding="utf-8")

    assert 'encoding="utf-8"' in smoke_test
    assert "text=True" not in smoke_test


@pytest.mark.parametrize("job", ["verify", "publish"])
@pytest.mark.parametrize(
    "name, artifact", [("wheel", "*.whl"), ("source distribution", "*.tar.gz")]
)
def test_release_checks_installed_artifacts_before_publishing(
    job, name, artifact
) -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    verify, publish = workflow.split("\n  publish:\n", maxsplit=1)
    publish = publish.split("\n  release:\n", maxsplit=1)[0]
    section = verify if job == "verify" else publish
    header = f"      - name: Smoke test {name}\n"
    assert header in section
    step = section.split(header, maxsplit=1)[1].split("\n      - name:", maxsplit=1)[0]
    assert "        if:" not in step
    assert "        shell: bash" in step
    assert 'export LEETCODE_LOCAL_CLI_EXPECTED_VERSION="$(uv version --short)"' in step
    assert (
        f"uv run --isolated --no-project --with dist/{artifact} scripts/smoke_test.py"
        in step
    )
    assert section.index("name: Build distributions") < section.index(header)
    if job == "verify":
        for platform in ("ubuntu-latest", "macos-latest", "windows-latest"):
            assert f"- {platform}" in section
        assert "    needs: verify" in publish
    else:
        assert section.index(header) < section.index("name: Publish distributions")


@pytest.mark.skipif(
    os.name == "nt",
    reason="release creation runs with Bash on an Ubuntu GitHub Actions runner",
)
def test_release_creation_script_has_valid_bash_syntax() -> None:
    lines = RELEASE_WORKFLOW.read_text(encoding="utf-8").splitlines()
    step_index = lines.index("      - name: Create release")
    run_index = lines.index("        run: |", step_index)
    script_lines = []
    for line in lines[run_index + 1 :]:
        if line and not line.startswith("          "):
            break
        script_lines.append(line[10:] if line else "")

    result = subprocess.run(
        ["bash", "-n"],
        input="\n".join(script_lines),
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
