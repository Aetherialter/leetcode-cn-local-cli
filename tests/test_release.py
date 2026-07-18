from pathlib import Path
import subprocess
import tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_FILE = PROJECT_ROOT / "pyproject.toml"
RELEASE_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "release.yml"
RELEASE_NOTES_DIR = PROJECT_ROOT / ".github" / "release-notes"


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

    assert ".github/release-notes/${GITHUB_REF_NAME}.md" in workflow
    assert '--title "$release_title"' in workflow
    assert '--notes-file "$notes_file"' in workflow


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
