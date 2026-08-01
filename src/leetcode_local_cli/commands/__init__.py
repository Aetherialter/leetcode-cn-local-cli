from typer import Typer

from leetcode_local_cli.commands.account import login, profile, status
from leetcode_local_cli.commands.problems import get_problem, show, solve
from leetcode_local_cli.commands.setup import init_workspace
from leetcode_local_cli.commands.submission import submit
from leetcode_local_cli.commands.testing import doctor, test


def register_commands(app: Typer) -> None:
    """Register every public CLI command without coupling handlers to the app."""
    app.command("init")(init_workspace)
    app.command()(login)
    app.command()(status)
    app.command()(profile)
    app.command("get")(get_problem)
    app.command()(show)
    app.command()(solve)
    app.command()(test)
    app.command()(doctor)
    app.command()(submit)
