import re
import shutil
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from html import unescape
from html.parser import HTMLParser

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from leetcode_local_cli.models.account import AccountProfile
from leetcode_local_cli.models.diagnostics import DoctorReport, DoctorStatus
from leetcode_local_cli.models.problem import ProblemDetail, ProblemSummary
from leetcode_local_cli.models.solution import ProblemMetadata
from leetcode_local_cli.models.submission import (
    SubmissionOutcome,
    SubmissionPending,
    SubmissionPollingFailed,
    SubmissionTimedOut,
)

console = Console(
    width=shutil.get_terminal_size(fallback=(120, 24)).columns,
    markup=False,
    highlight=False,
)

_UNSAFE_TERMINAL_CHARACTERS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def _sanitize_terminal_text(value: object) -> str:
    """Remove terminal control characters while preserving tabs and newlines."""
    return _UNSAFE_TERMINAL_CHARACTERS.sub("\N{REPLACEMENT CHARACTER}", str(value))


def _external_text(value: object, *, style: str = "") -> Text:
    """Render external data as plain text with an optional trusted local style."""
    return Text(_sanitize_terminal_text(value), style=style)


def _terminal_width() -> int:
    return shutil.get_terminal_size(fallback=(console.width, 24)).columns


class _ProblemHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"p", "div", "ul", "ol", "pre"}:
            self.parts.append("\n")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag == "br":
            self.parts.append("\n")
        elif tag == "sup":
            self.parts.append("^")
        elif tag == "sub":
            self.parts.append("_")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "ul", "ol", "pre"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _html_to_text(content_html: str) -> str:
    parser = _ProblemHTMLParser()
    parser.feed(content_html)
    text = unescape("".join(parser.parts))
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@contextmanager
def loading(message: str) -> Iterator[None]:
    with console.status(_external_text(message), spinner="dots"):
        yield


def success(message: str) -> None:
    console.print(_external_text(message, style="bold green"))


def info(message: str) -> None:
    console.print(_external_text(message, style="cyan"))


def warning(message: str) -> None:
    console.print(_external_text(message, style="bold yellow"))


def error(message: str) -> None:
    console.print(_external_text(message, style="bold red"))


def render_local_test_output(output: str, *, style: str = "") -> None:
    if not output:
        return
    end = "" if output.endswith("\n") else "\n"
    console.print(_external_text(output, style=style), end=end)


def render_local_execution_result(
    *,
    case_index: int,
    result_text: str,
    stdout: str,
    stderr: str,
    arguments_after_text: str | None,
) -> None:
    success(f"第 {case_index} 组执行完成")
    if stdout:
        info("标准输出：")
        render_local_test_output(stdout)
    if stderr:
        warning("标准错误：")
        render_local_test_output(stderr)
    info("返回值：")
    render_local_test_output(result_text, style="bold bright_white")
    if arguments_after_text is not None:
        info("调用后参数：")
        render_local_test_output(arguments_after_text)


def render_local_execution_error(
    *,
    case_index: int,
    error_detail: str,
    stdout: str = "",
    stderr: str = "",
) -> None:
    error(f"第 {case_index} 组执行失败")
    console.print(_external_text(f"原因：{error_detail}", style="red"))
    if stdout:
        console.print(_external_text("标准输出：", style="red"))
        console.print(
            _external_text(stdout, style="red"),
            end="" if stdout.endswith("\n") else "\n",
        )
    if stderr:
        console.print(_external_text("标准错误：", style="red"))
        console.print(
            _external_text(stderr, style="red"),
            end="" if stderr.endswith("\n") else "\n",
        )


def render_profile(profile: AccountProfile) -> None:
    solved = profile.stats.solved
    total = profile.stats.total

    table = Table(title="LeetCode CN Profile")
    table.add_column("Item", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    table.add_row("Username", _external_text(profile.user.username or "-"))
    table.add_row("Real Name", _external_text(profile.user.real_name or "-"))
    table.add_row("Premium", _external_text("Yes" if profile.user.premium else "No"))
    table.add_row(
        "Solved",
        _external_text(
            f"All {solved.total} | Easy {solved.easy} | "
            f"Medium {solved.medium} | Hard {solved.hard}"
        ),
    )
    table.add_row(
        "Total",
        _external_text(
            f"All {total.total} | Easy {total.easy} | "
            f"Medium {total.medium} | Hard {total.hard}"
        ),
    )

    console.print(Panel(table, border_style="green", width=_terminal_width()))


def render_problem_list(problems: Sequence[ProblemSummary]) -> None:
    if not problems:
        warning("没有可展示的题目")
        return

    table = Table(
        title=f"LeetCode CN Problems ({len(problems)})",
        border_style="cyan",
        expand=True,
        width=_terminal_width(),
    )
    table.add_column("ID", style="cyan", justify="right", no_wrap=True)
    table.add_column("Title", style="white", overflow="fold")
    table.add_column("Difficulty", justify="center", no_wrap=True)
    table.add_column("Paid", justify="center", no_wrap=True)
    table.add_column("Tags", style="dim", overflow="fold")

    difficulty_styles = {
        "Easy": "green",
        "Medium": "yellow",
        "Hard": "red",
    }

    for problem in problems:
        difficulty = problem.difficulty or "-"
        difficulty_style = difficulty_styles.get(difficulty, "white")
        paid_text = _external_text(
            "Paid" if problem.paid_only else "Free",
            style="yellow" if problem.paid_only else "green",
        )
        tags = ", ".join(problem.tags[:4])
        if len(problem.tags) > 4:
            tags = f"{tags}, ..."

        table.add_row(
            _external_text(problem.question_id),
            _external_text(problem.title or "-"),
            _external_text(difficulty, style=difficulty_style),
            paid_text,
            _external_text(tags or "-", style="dim"),
        )

    console.print(table)


def render_problem_detail(problem: ProblemDetail) -> None:
    tags = ", ".join(problem.tags) if problem.tags else "-"

    meta = Table.grid(padding=(0, 2))
    meta.add_column(style="cyan", no_wrap=True)
    meta.add_column(style="white")
    meta.add_row("ID", _external_text(problem.question_id))
    meta.add_row("Slug", _external_text(problem.title_slug))
    meta.add_row("Difficulty", _external_text(problem.difficulty))
    meta.add_row("Tags", _external_text(tags))

    title = _external_text(f"{problem.question_id}. {problem.title}")
    console.print(
        Panel(meta, title=title, border_style="cyan", width=_terminal_width())
    )

    content_text = _html_to_text(problem.content_html)
    console.print(
        Panel(
            _external_text(content_text or "-"),
            title="题面",
            border_style="white",
            width=_terminal_width(),
        )
    )

    if not problem.python_code:
        warning("未找到 Python3 代码模板")


def render_submission_target(metadata: ProblemMetadata) -> None:
    console.print(
        _external_text(
            f"当前提交目标：{metadata.problem_id}. "
            f"{metadata.title} ({metadata.title_slug})",
            style="bold cyan",
        )
    )


def render_submission_submitted(
    submission_id: int,
    *,
    wait_timeout_seconds: float,
) -> None:
    info(f"提交已发送：{submission_id}")
    info(f"正在等待判题，最多 {wait_timeout_seconds:g} 秒……")


def render_doctor_report(report: DoctorReport) -> None:
    labels = {
        "session": "Session 文件",
        "connectivity": "LeetCode 接口",
        "authentication": "Cookie 登录态",
        "workspace": "工作区",
        "solution": "solution.py",
    }
    status_labels = {
        DoctorStatus.PASS: ("PASS", "green"),
        DoctorStatus.WARNING: ("WARNING", "yellow"),
        DoctorStatus.FAIL: ("FAIL", "red"),
    }
    table = Table(title="环境诊断", expand=True)
    table.add_column("检查项", style="cyan", no_wrap=True)
    table.add_column("状态", justify="center", no_wrap=True)
    table.add_column("结果", overflow="fold")
    table.add_column("建议", overflow="fold")

    for check in report.checks:
        status_text, status_style = status_labels[check.status]
        table.add_row(
            _external_text(labels.get(check.name, check.name)),
            _external_text(status_text, style=status_style),
            _external_text(check.message),
            _external_text(check.suggestion or "-"),
        )

    border_style = "green" if report.ok else "red"
    console.print(
        Panel(
            table,
            border_style=border_style,
            width=_terminal_width(),
        )
    )


def render_submission_result(result: SubmissionOutcome) -> None:
    if isinstance(result, SubmissionPending):
        warning("提交仍在判题中")
        info(f"Submission ID：{result.submission_id}")
        info(f"可稍后重新执行：lc check {result.submission_id}")
        return
    if isinstance(result, SubmissionTimedOut):
        error(f"判题等待超过 {result.waited_seconds:g} 秒")
        warning("代码已经成功发送，可稍后重新查询")
        info(f"Submission ID：{result.submission_id}")
        info(f"重新查询：lc check {result.submission_id}")
        return
    if isinstance(result, SubmissionPollingFailed):
        error(f"无法继续获取判题结果：{result.message}")
        warning("代码已经提交，可稍后通过 Submission ID 查看")
        info(f"Submission ID：{result.submission_id}")
        return

    status_msg = result.status_message
    runtime = result.runtime or "-"
    memory = result.memory or "-"
    total_correct = result.total_correct
    total_testcases = result.total_testcases

    if result.accepted:
        success("通过")
    else:
        error(f"提交失败：{status_msg}")

    table = Table(title="判题结果", border_style="green" if result.accepted else "red")
    table.add_column("Item", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    table.add_row("Status", _external_text(status_msg))
    table.add_row("Runtime", _external_text(runtime))
    table.add_row("Memory", _external_text(memory))
    if total_correct is not None and total_testcases is not None:
        table.add_row("Cases", _external_text(f"{total_correct} / {total_testcases}"))

    console.print(
        Panel(
            table,
            border_style="green" if result.accepted else "red",
            width=_terminal_width(),
        )
    )
