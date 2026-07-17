from io import StringIO

from rich.console import Console

from aether_lc import ui
from aether_lc.doctor import DoctorCheck, DoctorReport, DoctorStatus
from aether_lc.workspace import ProblemMetadata


def test_render_doctor_report_displays_checks_and_suggestions(monkeypatch) -> None:
    output = StringIO()
    monkeypatch.setattr(
        ui, "console", Console(file=output, width=120, color_system=None)
    )
    report = DoctorReport(
        checks=(
            DoctorCheck("session", DoctorStatus.PASS, "Session 有效"),
            DoctorCheck(
                "authentication",
                DoctorStatus.FAIL,
                "Cookie 已过期",
                "执行 lc login",
            ),
        )
    )

    ui.render_doctor_report(report)

    rendered = output.getvalue()
    assert "Session 文件" in rendered
    assert "PASS" in rendered
    assert "FAIL" in rendered
    assert "执行 lc login" in rendered


def test_render_submission_target_includes_slug(monkeypatch) -> None:
    output = StringIO()
    monkeypatch.setattr(ui, "console", Console(file=output, color_system=None))
    metadata = ProblemMetadata("1", "1", "Two Sum", "two-sum")

    ui.render_submission_target(metadata)

    rendered = output.getvalue()
    assert "1. Two Sum" in rendered
    assert "two-sum" in rendered
