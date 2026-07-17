from collections.abc import Iterator
from contextlib import contextmanager
from html import unescape
from html.parser import HTMLParser
import re
import shutil
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from aether_lc.doctor import DoctorReport, DoctorStatus

console = Console(width=shutil.get_terminal_size(fallback=(120, 24)).columns)


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
    with console.status(message, spinner="dots"):
        yield


def success(message: str) -> None:
    console.print(f"[bold green]{message}[/bold green]")


def warning(message: str) -> None:
    console.print(f"[bold yellow]{message}[/bold yellow]")


def error(message: str) -> None:
    console.print(f"[bold red]{message}[/bold red]")


def render_profile(profile: dict[str, Any]) -> None:
    solved = profile["solved"]
    total = profile["total"]

    table = Table(title="LeetCode CN Profile")
    table.add_column("Item", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    table.add_row("Username", str(profile.get("username") or "-"))
    table.add_row("Real Name", str(profile.get("real_name") or "-"))
    table.add_row("Premium", "Yes" if profile.get("is_premium") else "No")
    table.add_row(
        "Solved",
        f"All {solved['All']} | Easy {solved['Easy']} | Medium {solved['Medium']} | Hard {solved['Hard']}",
    )
    table.add_row(
        "Total",
        f"All {total['All']} | Easy {total['Easy']} | Medium {total['Medium']} | Hard {total['Hard']}",
    )

    console.print(Panel(table, border_style="green", width=_terminal_width()))


def render_problem_list(problems: list[Any]) -> None:
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
        paid_text = (
            "[yellow]Paid[/yellow]" if problem.paid_only else "[green]Free[/green]"
        )
        tags = ", ".join(problem.tags[:4])
        if len(problem.tags) > 4:
            tags = f"{tags}, ..."

        table.add_row(
            problem.question_id,
            problem.title or "-",
            f"[{difficulty_style}]{difficulty}[/{difficulty_style}]",
            paid_text,
            tags or "-",
        )

    console.print(table)


def render_problem_detail(problem: Any) -> None:
    tags = ", ".join(problem.tags) if problem.tags else "-"

    meta = Table.grid(padding=(0, 2))
    meta.add_column(style="cyan", no_wrap=True)
    meta.add_column(style="white")
    meta.add_row("ID", problem.question_id)
    meta.add_row("Slug", problem.title_slug)
    meta.add_row("Difficulty", problem.difficulty)
    meta.add_row("Tags", tags)

    title = f"{problem.question_id}. {problem.title}"
    console.print(
        Panel(meta, title=title, border_style="cyan", width=_terminal_width())
    )

    content_text = _html_to_text(problem.content_html)
    console.print(
        Panel(
            content_text or "-",
            title="题面",
            border_style="white",
            width=_terminal_width(),
        )
    )

    if not problem.python_code:
        warning("未找到 Python3 代码模板")


def render_submission_target(metadata: Any) -> None:
    console.print(
        "[bold cyan]当前提交目标："
        f"{metadata.problem_id}. {metadata.title} ({metadata.title_slug})"
        "[/bold cyan]"
    )


def render_doctor_report(report: DoctorReport) -> None:
    labels = {
        "session": "Session 文件",
        "connectivity": "LeetCode 接口",
        "authentication": "Cookie 登录态",
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
            labels.get(check.name, check.name),
            f"[{status_style}]{status_text}[/{status_style}]",
            check.message,
            check.suggestion or "-",
        )

    border_style = "green" if report.ok else "red"
    console.print(
        Panel(
            table,
            border_style=border_style,
            width=_terminal_width(),
        )
    )


def render_submission_result(result: dict[str, Any] | None) -> None:
    if result is None:
        error("判题超时，请稍后到 LeetCode 查看结果")
        return

    status_msg = str(result.get("status_msg") or "-")
    runtime = str(result.get("status_runtime") or result.get("runtime") or "-")
    memory = str(result.get("memory") or "-")
    total_correct = result.get("total_correct")
    total_testcases = result.get("total_testcases")

    if status_msg == "Accepted":
        success("通过")
    else:
        error(f"提交失败：{status_msg}")

    table = Table(
        title="判题结果", border_style="green" if status_msg == "Accepted" else "red"
    )
    table.add_column("Item", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    table.add_row("Status", status_msg)
    table.add_row("Runtime", runtime)
    table.add_row("Memory", memory)
    if total_correct is not None and total_testcases is not None:
        table.add_row("Cases", f"{total_correct} / {total_testcases}")

    console.print(
        Panel(
            table,
            border_style="green" if status_msg == "Accepted" else "red",
            width=_terminal_width(),
        )
    )
