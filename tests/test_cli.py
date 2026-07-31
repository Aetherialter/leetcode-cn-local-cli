import os
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from leetcode_local_cli import cli
from leetcode_local_cli.doctor import DoctorCheck, DoctorReport, DoctorStatus
from leetcode_local_cli.problem import ProblemDetail
from leetcode_local_cli.paths import AppPaths
from leetcode_local_cli.workspace import (
    LocalTestResult,
    LocalTestStatus,
    SolutionFileInspection,
    SolutionFileStatus,
    WorkspaceError,
)


runner = CliRunner()


@pytest.fixture(autouse=True)
def configured_app_paths(tmp_path, monkeypatch) -> AppPaths:
    paths = AppPaths.from_workspace(
        tmp_path / "workspace",
        user_config_file=tmp_path / "config.toml",
    )
    monkeypatch.setattr(cli, "_require_app_paths", lambda: paths)
    return paths


def test_module_entrypoint_emits_utf8_when_initial_encoding_is_cp1252() -> None:
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "cp1252"

    result = subprocess.run(
        [sys.executable, "-m", "leetcode_local_cli", "--help"],
        capture_output=True,
        check=False,
        env=environment,
    )

    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert "力扣中文站" in result.stdout.decode("utf-8")


def test_version_option_displays_installed_distribution_version(monkeypatch) -> None:
    monkeypatch.setattr(cli, "get_version", lambda: "1.2.3")

    result = runner.invoke(cli.app, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == "leetcode-local-cli 1.2.3"


def test_help_registers_doctor_command() -> None:
    result = runner.invoke(cli.app, ["--help"])

    assert result.exit_code == 0
    assert "doctor" in result.output


def test_help_registers_init_command() -> None:
    result = runner.invoke(cli.app, ["--help"])

    assert result.exit_code == 0
    assert "init" in result.output


def test_init_explicit_path_yes_creates_and_configures_workspace(
    tmp_path,
    monkeypatch,
) -> None:
    workspace_root = tmp_path / "workspace"
    user_config_file = tmp_path / "config" / "config.toml"
    monkeypatch.setattr(cli, "get_user_config_file", lambda: user_config_file)

    result = runner.invoke(cli.app, ["init", str(workspace_root), "--yes"])

    assert result.exit_code == 0, result.output
    assert (workspace_root / ".leetcode-local-cli.toml").is_file()
    assert (workspace_root / "solution.py").read_text(encoding="utf-8") == ""
    assert workspace_root.as_posix() in user_config_file.read_text(encoding="utf-8")


def test_init_without_path_appends_fixed_workspace_directory(
    tmp_path,
    monkeypatch,
) -> None:
    user_config_file = tmp_path / "config" / "config.toml"
    monkeypatch.setattr(cli, "get_user_config_file", lambda: user_config_file)

    result = runner.invoke(cli.app, ["init"], input=f"{tmp_path}\ny\n")

    workspace_root = tmp_path / "leetcode-local-cli"
    assert result.exit_code == 0, result.output
    assert (workspace_root / ".leetcode-local-cli.toml").is_file()
    assert (workspace_root / "solution.py").is_file()


def test_init_preserves_existing_regular_solution(tmp_path, monkeypatch) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    solution_file = workspace_root / "solution.py"
    solution_file.write_text("existing solution", encoding="utf-8")
    user_config_file = tmp_path / "config" / "config.toml"
    monkeypatch.setattr(cli, "get_user_config_file", lambda: user_config_file)

    result = runner.invoke(cli.app, ["init", str(workspace_root), "--yes"])

    assert result.exit_code == 0, result.output
    assert solution_file.read_text(encoding="utf-8") == "existing solution"


def test_init_without_path_reuses_valid_default_workspace(
    tmp_path,
    monkeypatch,
) -> None:
    workspace_root = tmp_path / "workspace"
    user_config_file = tmp_path / "config" / "config.toml"
    monkeypatch.setattr(cli, "get_user_config_file", lambda: user_config_file)
    first_result = runner.invoke(
        cli.app,
        ["init", str(workspace_root), "--yes"],
    )
    assert first_result.exit_code == 0, first_result.output

    result = runner.invoke(cli.app, ["init"])

    assert result.exit_code == 0, result.output
    assert "继续使用现有工作区" in result.output
    assert "请输入工作区父目录" not in result.output


def test_init_yes_requires_explicit_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "get_user_config_file",
        lambda: tmp_path / "missing" / "config.toml",
    )

    result = runner.invoke(cli.app, ["init", "--yes"])

    assert result.exit_code == 1
    assert "--yes 必须与工作区完整路径一起使用" in result.output


def test_doctor_command_renders_successful_report(monkeypatch) -> None:
    report = DoctorReport(checks=(DoctorCheck("session", DoctorStatus.PASS, "ok"),))
    rendered = []
    received = []
    monkeypatch.setattr(
        cli,
        "get_doctor_report",
        lambda paths, *, run_solution=False: received.append(run_solution) or report,
    )
    monkeypatch.setattr(cli, "render_doctor_report", rendered.append)

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 0
    assert received == [False]
    assert rendered == [report]


def test_doctor_command_forwards_run_solution_option(monkeypatch) -> None:
    report = DoctorReport(checks=(DoctorCheck("solution", DoctorStatus.PASS, "ok"),))
    received = []
    monkeypatch.setattr(
        cli,
        "get_doctor_report",
        lambda paths, *, run_solution=False: received.append(run_solution) or report,
    )
    monkeypatch.setattr(cli, "render_doctor_report", lambda report: None)

    result = runner.invoke(cli.app, ["doctor", "--run-solution"])

    assert result.exit_code == 0
    assert received == [True]


def test_doctor_command_exits_nonzero_for_failed_report(monkeypatch) -> None:
    report = DoctorReport(checks=(DoctorCheck("session", DoctorStatus.FAIL, "failed"),))
    monkeypatch.setattr(
        cli,
        "get_doctor_report",
        lambda paths, *, run_solution=False: report,
    )
    monkeypatch.setattr(cli, "render_doctor_report", lambda report: None)

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 1


def test_solve_command_reports_rejected_workspace_target(monkeypatch) -> None:
    problem = ProblemDetail(
        question_id="1",
        submit_question_id="1",
        title="Two Sum",
        title_slug="two-sum",
        difficulty="Easy",
        tags=["Array"],
        content_html="<p>content</p>",
        python_code="class Solution:\n    pass",
    )
    monkeypatch.setattr(
        cli,
        "get_problem_detail_by_question_id",
        lambda paths, question_id: problem,
    )
    monkeypatch.setattr(cli, "render_problem_detail", lambda problem: None)
    monkeypatch.setattr(
        cli,
        "write_solution_file",
        lambda path, python_code, metadata: (_ for _ in ()).throw(
            WorkspaceError("solution.py 是符号链接或断链，已拒绝写入")
        ),
    )

    result = runner.invoke(cli.app, ["solve", "1"])

    assert result.exit_code == 1
    assert "符号链接或断链" in result.output
    assert "Traceback" not in result.output


def test_test_command_reports_missing_solution_without_running(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "inspect_solution_file",
        lambda path: SolutionFileInspection(status=SolutionFileStatus.MISSING),
    )
    monkeypatch.setattr(
        cli,
        "run_local_tests",
        lambda path, *, timeout: (_ for _ in ()).throw(
            AssertionError("should not run")
        ),
    )

    result = runner.invoke(cli.app, ["test"])

    assert result.exit_code == 1
    assert "未找到 solution.py" in result.output


def test_test_command_reports_syntax_line_without_running(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "inspect_solution_file",
        lambda path: SolutionFileInspection(
            status=SolutionFileStatus.INVALID_SYNTAX,
            syntax_line=7,
        ),
    )

    result = runner.invoke(cli.app, ["test"])

    assert result.exit_code == 1
    assert "第 7 行" in result.output


def test_test_command_rejects_invalid_encoding_without_running(
    configured_app_paths,
    monkeypatch,
) -> None:
    solution_file = configured_app_paths.solution_file
    solution_file.parent.mkdir(parents=True)
    solution_file.write_bytes(b"\xff\xfeinvalid source")
    monkeypatch.setattr(
        cli,
        "run_local_tests",
        lambda path, *, timeout: (_ for _ in ()).throw(
            AssertionError("invalid source must not run")
        ),
    )

    result = runner.invoke(cli.app, ["test"])

    assert result.exit_code == 1
    assert "不是有效的 UTF-8 编码" in result.output
    assert "Traceback" not in result.output


def test_test_command_reports_unconfigured_local_tests(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "inspect_solution_file",
        lambda path: SolutionFileInspection(status=SolutionFileStatus.READY),
    )
    monkeypatch.setattr(
        cli,
        "run_local_tests",
        lambda path, *, timeout: LocalTestResult(status=LocalTestStatus.NOT_CONFIGURED),
    )

    result = runner.invoke(cli.app, ["test"])

    assert result.exit_code == 1
    assert "尚未配置本地自测用例" in result.output
    assert "本地自测执行成功" not in result.output


@pytest.mark.parametrize(
    ("status", "message"),
    (
        (LocalTestStatus.MISSING_ENTRY, "未找到可执行的 run_cases()"),
        (LocalTestStatus.FAILED, "本地自测执行失败"),
    ),
)
def test_test_command_maps_runner_failures_to_nonzero(
    monkeypatch,
    status: LocalTestStatus,
    message: str,
) -> None:
    monkeypatch.setattr(
        cli,
        "inspect_solution_file",
        lambda path: SolutionFileInspection(status=SolutionFileStatus.READY),
    )
    monkeypatch.setattr(
        cli,
        "run_local_tests",
        lambda path, *, timeout: LocalTestResult(
            status=status,
            stderr="controlled error\n",
        ),
    )

    result = runner.invoke(cli.app, ["test"])

    assert result.exit_code == 1
    assert "controlled error" in result.output
    assert message in result.output


def test_test_command_displays_output_and_reports_success(monkeypatch) -> None:
    received_timeouts = []
    monkeypatch.setattr(
        cli,
        "inspect_solution_file",
        lambda path: SolutionFileInspection(status=SolutionFileStatus.READY),
    )
    monkeypatch.setattr(
        cli,
        "run_local_tests",
        lambda path, *, timeout: (
            received_timeouts.append(timeout)
            or LocalTestResult(
                status=LocalTestStatus.PASSED,
                stdout="[2, 7]\n",
            )
        ),
    )

    result = runner.invoke(cli.app, ["test", "--timeout", "30"])

    assert result.exit_code == 0
    assert received_timeouts == [30.0]
    assert "[2, 7]" in result.output
    assert "本地自测执行成功" in result.output


@pytest.mark.parametrize("timeout", ("0", "-1", "nan", "inf"))
def test_test_command_rejects_invalid_timeout(timeout: str) -> None:
    result = runner.invoke(cli.app, ["test", "--timeout", timeout])

    assert result.exit_code == 2
    assert "大于 0 的有限秒数" in result.output


def test_test_command_reports_timeout(monkeypatch) -> None:
    received_timeouts = []
    monkeypatch.setattr(
        cli,
        "inspect_solution_file",
        lambda path: SolutionFileInspection(status=SolutionFileStatus.READY),
    )
    monkeypatch.setattr(
        cli,
        "run_local_tests",
        lambda path, *, timeout: (
            received_timeouts.append(timeout)
            or LocalTestResult(
                status=LocalTestStatus.TIMED_OUT,
                stdout="partial output\n",
            )
        ),
    )

    result = runner.invoke(cli.app, ["test"])

    assert result.exit_code == 1
    assert received_timeouts == [1.0]
    assert "partial output" in result.output
    assert "执行时间超过 1 秒" in result.output


def test_submit_does_not_run_local_tests(monkeypatch) -> None:
    monkeypatch.setattr(cli, "submit_current_solution", lambda paths: None)
    monkeypatch.setattr(cli, "render_submission_result", lambda result: None)
    monkeypatch.setattr(
        cli,
        "run_local_tests",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("submit must not execute local tests")
        ),
    )

    result = runner.invoke(cli.app, ["submit"])

    assert result.exit_code == 0


def test_submit_rejects_invalid_encoding_before_remote_request(
    configured_app_paths,
    monkeypatch,
) -> None:
    solution_file = configured_app_paths.solution_file
    solution_file.parent.mkdir(parents=True)
    solution_file.write_bytes(b"\xff\xfeinvalid source")
    monkeypatch.setattr(
        "leetcode_local_cli.service.LeetCodeClient",
        lambda cookies: (_ for _ in ()).throw(
            AssertionError("invalid source must not reach remote client")
        ),
    )
    monkeypatch.setattr(
        "leetcode_local_cli.service._load_cookies_from_session",
        lambda paths: (_ for _ in ()).throw(
            AssertionError("invalid source must not load credentials")
        ),
    )

    result = runner.invoke(cli.app, ["submit"])

    assert result.exit_code == 1
    assert "不是有效的 UTF-8 编码" in result.output
    assert "Traceback" not in result.output
