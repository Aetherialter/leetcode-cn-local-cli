from io import StringIO

import pytest
from rich.console import Console

from leetcode_local_cli import ui
from leetcode_local_cli.doctor import DoctorCheck, DoctorReport, DoctorStatus
from leetcode_local_cli.problem import ProblemDetail, ProblemSummary
from leetcode_local_cli.workspace import ProblemMetadata


MARKUP_PAYLOAD = "[link=https://evil.example]click[/link]"
BROKEN_MARKUP_PAYLOAD = "[/]"
ANSI_PAYLOAD = "\x1b[31mforged\x1b[0m"
OSC_PAYLOAD = "\x1b]8;;https://evil.example\x07click\x1b]8;;\x07"


def _terminal_console(output: StringIO) -> Console:
    return Console(
        file=output,
        width=160,
        force_terminal=True,
        color_system="standard",
    )


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


@pytest.mark.parametrize(
    "payload",
    [MARKUP_PAYLOAD, BROKEN_MARKUP_PAYLOAD, ANSI_PAYLOAD, OSC_PAYLOAD],
)
def test_external_text_never_interprets_external_formatting(payload) -> None:
    rendered = ui._external_text(payload)

    assert rendered.spans == []
    assert "\x1b" not in rendered.plain
    assert "\x07" not in rendered.plain


def test_external_text_only_applies_trusted_local_style() -> None:
    rendered = ui._external_text(MARKUP_PAYLOAD, style="bold red")

    assert rendered.plain == MARKUP_PAYLOAD
    assert rendered.style == "bold red"
    assert rendered.spans == []


def test_all_dynamic_renderers_treat_external_markup_as_plain_text(
    monkeypatch,
) -> None:
    output = StringIO()
    monkeypatch.setattr(ui, "console", _terminal_console(output))

    ui.success(MARKUP_PAYLOAD)
    ui.warning(MARKUP_PAYLOAD)
    ui.error(MARKUP_PAYLOAD)
    ui.render_local_test_output(MARKUP_PAYLOAD)
    ui.render_profile(
        {
            "username": MARKUP_PAYLOAD,
            "real_name": MARKUP_PAYLOAD,
            "is_premium": False,
            "solved": {"All": 1, "Easy": 1, "Medium": 0, "Hard": 0},
            "total": {"All": 3, "Easy": 1, "Medium": 1, "Hard": 1},
        }
    )
    ui.render_problem_list(
        [
            ProblemSummary(
                question_id="1",
                title=MARKUP_PAYLOAD,
                title_slug="example",
                difficulty="Easy",
                paid_only=False,
                tags=[MARKUP_PAYLOAD],
            )
        ]
    )
    ui.render_problem_detail(
        ProblemDetail(
            question_id="1",
            submit_question_id="1",
            title=MARKUP_PAYLOAD,
            title_slug=MARKUP_PAYLOAD,
            difficulty="Easy",
            tags=[MARKUP_PAYLOAD],
            content_html=f"<p>{MARKUP_PAYLOAD}</p>",
            python_code="class Solution: pass",
        )
    )
    ui.render_submission_target(
        ProblemMetadata("1", "1", MARKUP_PAYLOAD, MARKUP_PAYLOAD)
    )
    ui.render_doctor_report(
        DoctorReport(
            checks=(
                DoctorCheck(
                    MARKUP_PAYLOAD,
                    DoctorStatus.WARNING,
                    MARKUP_PAYLOAD,
                    MARKUP_PAYLOAD,
                ),
            )
        )
    )
    ui.render_submission_result(
        {
            "status_msg": MARKUP_PAYLOAD,
            "status_runtime": MARKUP_PAYLOAD,
            "memory": MARKUP_PAYLOAD,
        }
    )

    rendered = output.getvalue()
    assert MARKUP_PAYLOAD in rendered
    assert "\x1b]8;" not in rendered


@pytest.mark.parametrize("payload", [ANSI_PAYLOAD, OSC_PAYLOAD])
def test_terminal_control_characters_are_removed_from_rendered_output(
    payload,
    monkeypatch,
) -> None:
    output = StringIO()
    monkeypatch.setattr(ui, "console", _terminal_console(output))

    ui.render_local_test_output(payload)

    rendered = output.getvalue()
    assert "\x1b]8;" not in rendered
    assert "forged" in rendered or "click" in rendered


def test_external_markup_remains_readable_without_color(monkeypatch) -> None:
    output = StringIO()
    monkeypatch.setattr(
        ui,
        "console",
        Console(
            file=output,
            width=120,
            color_system=None,
            markup=False,
            highlight=False,
        ),
    )

    ui.error("[bold]failure[/bold]")

    assert output.getvalue().strip() == "[bold]failure[/bold]"
