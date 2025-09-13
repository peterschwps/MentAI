import typer.rich_utils

from mentai.utils.styling import except_hook, rich_format_error

# Overwritten functions
typer.rich_utils.rich_format_error = rich_format_error
typer.main.except_hook = except_hook
