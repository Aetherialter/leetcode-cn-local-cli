import ast
import re
import subprocess
from importlib.util import resolve_name
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "leetcode_local_cli"
ALLOWED_LAYERS = {
    "models": {"models"},
    "storage": {"storage", "models"},
    "execution": {"execution", "storage", "models"},
    "integrations": {"integrations", "storage", "models"},
    "use_cases": {"use_cases", "integrations", "storage", "execution", "models"},
}


def _imports(path: Path, tree: ast.AST) -> list[str]:
    package = ".".join(("leetcode_local_cli", *path.relative_to(SOURCE).parts[:-1]))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                module = resolve_name("." * node.level + module, package)
            names.append(module)
            names.extend(f"{module}.{alias.name}" for alias in node.names)
    return names


def test_dependency_direction_is_enforced_by_imports() -> None:
    for layer, allowed in ALLOWED_LAYERS.items():
        for path in (SOURCE / layer).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for name in _imports(path, tree):
                assert name.split(".")[0] not in {"typer", "rich"}, (path, name)
                if name.startswith("leetcode_local_cli."):
                    assert name.split(".")[1] in allowed, (path, name)


def test_normal_use_cases_do_not_depend_on_diagnostics() -> None:
    for path in (SOURCE / "use_cases").glob("*.py"):
        if path.stem in {"diagnostics", "doctor_checks"}:
            continue
        names = _imports(path, ast.parse(path.read_text(encoding="utf-8")))
        assert not any(
            name.startswith(
                (
                    "leetcode_local_cli.use_cases.diagnostics",
                    "leetcode_local_cli.use_cases.doctor_checks",
                )
            )
            for name in names
        ), path


def test_root_contains_only_entry_points_and_version() -> None:
    assert {path.name for path in SOURCE.glob("*.py")} == {
        "__init__.py",
        "__main__.py",
        "cli.py",
        "version.py",
    }


def test_runtime_source_does_not_capture_cwd() -> None:
    for path in SOURCE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            assert not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "cwd"
            ), path


def test_solution_is_ignored_and_not_tracked() -> None:
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "solution.py"], cwd=ROOT, check=False
    )
    tracked = subprocess.run(
        ["git", "ls-files", "--", "solution.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert ignored.returncode == 0
    assert tracked.stdout == ""


def test_daily_ci_has_three_platforms_and_no_release_authority() -> None:
    source = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for expected in (
        "push:",
        "pull_request:",
        "ubuntu-latest",
        "macos-latest",
        "windows-latest",
        'python-version: "3.12"',
        "ruff format --check",
        "ruff check",
        "pyright src tests scripts",
        "uv run pytest",
        "contents: read",
    ):
        assert expected in source
    actions = re.findall(r"uses:\s+(\S+)", source)
    assert actions and all(
        re.fullmatch(r"[^@]+@[0-9a-f]{40}", action) for action in actions
    )
    assert not any(
        forbidden in source
        for forbidden in (
            "uv publish",
            "gh release",
            "id-token: write",
            "lc login",
            "lc submit",
        )
    )
