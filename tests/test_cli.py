from typer.testing import CliRunner

from aether_lc import cli
from aether_lc.doctor import DoctorCheck, DoctorReport, DoctorStatus
from aether_lc.workspace import SolutionFileInspection, SolutionFileStatus


runner = CliRunner()


def test_help_registers_doctor_command() -> None:
    result = runner.invoke(cli.app, ["--help"])

    assert result.exit_code == 0
    assert "doctor" in result.output


def test_doctor_command_renders_successful_report(monkeypatch) -> None:
    report = DoctorReport(checks=(DoctorCheck("session", DoctorStatus.PASS, "ok"),))
    rendered = []
    monkeypatch.setattr(cli, "get_doctor_report", lambda: report)
    monkeypatch.setattr(cli, "render_doctor_report", rendered.append)

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 0
    assert rendered == [report]


def test_doctor_command_exits_nonzero_for_failed_report(monkeypatch) -> None:
    report = DoctorReport(checks=(DoctorCheck("session", DoctorStatus.FAIL, "failed"),))
    monkeypatch.setattr(cli, "get_doctor_report", lambda: report)
    monkeypatch.setattr(cli, "render_doctor_report", lambda report: None)

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 1


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
