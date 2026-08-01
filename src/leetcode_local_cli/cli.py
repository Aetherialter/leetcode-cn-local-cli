import sys
from typing import Annotated

from typer import Exit, Option, Typer, echo

from leetcode_local_cli.commands import register_commands
from leetcode_local_cli.version import PACKAGE_NAME, get_version


app = Typer(help="力扣中文站本地化刷题 CLI 工具", no_args_is_help=True)


def _configure_utf8_output() -> None:
    """Keep localized CLI output writable when Windows redirects the streams."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="backslashreplace")


def run() -> None:
    """Run the command-line application with deterministic UTF-8 output."""
    _configure_utf8_output()
    app()


def _version_callback(value: bool) -> None:
    if value:
        echo(f"{PACKAGE_NAME} {get_version()}")
        raise Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="显示版本并退出",
        ),
    ] = False,
) -> None:
    """力扣中文站本地化刷题 CLI 工具。"""


register_commands(app)


if __name__ == "__main__":
    run()
