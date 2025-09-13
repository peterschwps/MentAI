import os
from types import TracebackType

import click
import typer
import typer.main
import typer.rich_utils
from pygments.token import Comment
from rich.default_styles import DEFAULT_STYLES as default_styles
from rich.panel import Panel
from rich.style import Style
from rich.syntax import ANSI_DARK as ansi_dark
from rich.syntax import ANSI_LIGHT as ansi_light
from typer.models import DeveloperExceptionConfig

# Customize Typer console styles
typer.rich_utils.STYLE_OPTION = "white"
typer.rich_utils.STYLE_SWITCH = "white"
typer.rich_utils.STYLE_METAVAR = "grey30"
typer.rich_utils.STYLE_USAGE = "red"
typer.rich_utils.STYLE_USAGE_COMMAND = ""
typer.rich_utils.STYLE_HELPTEXT_FIRST_LINE = ""
typer.rich_utils.STYLE_OPTION_HELP = "white"
typer.rich_utils.STYLE_REQUIRED_SHORT = " red"
typer.rich_utils.STYLE_REQUIRED_LONG = "dim bold red"


# Customize error output
def rich_format_error(self: click.ClickException) -> None:
    """Print richly formatted click errors.

    Called by custom exception handler to print richly formatted click errors.
    Mimics original click.ClickException.echo() function but with rich
    formatting.
    """
    console = typer.rich_utils._get_rich_console(stderr=True)
    ctx: click.Context | None = getattr(self, "ctx", None)
    if ctx is not None:
        console.print()
        console.print(ctx.get_usage())

    if ctx is not None and ctx.command.get_help_option(ctx) is not None:
        console.print(
            f"\nTry [bold]'{ctx.command_path} {ctx.help_option_names[0]}'[/] "
            f"for help.\n",
            style="dim",
        )

    console.print(
        Panel(
            typer.rich_utils.highlighter(self.format_message()),
            border_style=typer.rich_utils.STYLE_ERRORS_PANEL_BORDER,
            title=typer.rich_utils.ERRORS_PANEL_TITLE,
            title_align=typer.rich_utils.ALIGN_ERRORS_PANEL,
        )
    )


# Customize default styles for Rich
for key in list(default_styles.keys()):
    if not key.startswith("traceback."):
        default_styles[key] = Style.null()
default_styles["scope.border"] = Style(color="white", bold=True)

# Customize syntax highlighting for Rich
for key in list(
    filter(lambda iterable: iterable is not Comment, ansi_light.keys())
):
    ansi_light[key] = Style.null()
for key in list(
    filter(lambda iterable: iterable is not Comment, ansi_dark.keys())
):
    ansi_dark[key] = Style.null()


# Customize exception handling
def except_hook(
    exc_type: type[BaseException],
    exc_value: BaseException,
    tb: TracebackType | None,
    use_rich: bool = True,
) -> None:
    exception_config: DeveloperExceptionConfig | None = getattr(
        exc_value, typer.main._typer_developer_exception_attr_name, None
    )
    if not use_rich or exception_config is None:
        typer.main._original_except_hook(exc_type, exc_value, tb)
        return
    else:
        typer_path = os.path.dirname(__file__)
        click_path = os.path.dirname(click.__file__)
        internal_dir_names = [typer_path, click_path]
        exc = exc_value
        rich_tb = typer.rich_utils.get_traceback(
            exc, exception_config, internal_dir_names
        )
        console_stderr = typer.rich_utils._get_rich_console(stderr=True)
        console_stderr.print(rich_tb)
        return
