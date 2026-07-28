import os
import subprocess
import sys

from typer.testing import CliRunner

from leetcode_local_cli import cli
from leetcode_local_cli.doctor import DoctorCheck, DoctorReport, DoctorStatus
from leetcode_local_cli.problem import ProblemDetail
from leetcode_local_cli.workspace import (
    SolutionFileInspection,
    SolutionFileStatus,
    WorkspaceError,
)


runner = CliRunner()


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


def test_doctor_command_renders_successful_report(monkeypatch) -> None:
    report = DoctorReport(checks=(DoctorCheck("session", DoctorStatus.PASS, "ok"),))
    rendered = []
    received = []
    monkeypatch.setattr(
        cli,
        "get_doctor_report",
        lambda *, run_solution=False: received.append(run_solution) or report,
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
        lambda *, run_solution=False: received.append(run_solution) or report,
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
        lambda *, run_solution=False: report,
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
        lambda question_id: problem,
    )
    monkeypatch.setattr(cli, "render_problem_detail", lambda problem: None)
    monkeypatch.setattr(
        cli,
        "write_solution_file",
        lambda python_code, metadata: (_ for _ in ()).throw(
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
        lambda: SolutionFileInspection(status=SolutionFileStatus.MISSING),
    )
    monkeypatch.setattr(
        cli,
        "run_solution_file",
        lambda: (_ for _ in ()).throw(AssertionError("should not run")),
    )

    result = runner.invoke(cli.app, ["test"])

    assert result.exit_code == 1
    assert "未找到 solution.py" in result.output


def test_test_command_reports_syntax_line_without_running(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "inspect_solution_file",
        lambda: SolutionFileInspection(
            status=SolutionFileStatus.INVALID_SYNTAX,
            syntax_line=7,
        ),
    )

    result = runner.invoke(cli.app, ["test"])

    assert result.exit_code == 1
    assert "第 7 行" in result.output
