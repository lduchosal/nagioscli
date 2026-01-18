"""CLI module for nagioscli."""

import click

from .commands import register_all_commands
from nagioscli import __version__


@click.group()
@click.version_option(version=__version__, prog_name="nagioscli")
def main() -> None:
    """Nagios CLI - Manage Nagios Core via HTTP REST API."""
    pass


# Register all commands
register_all_commands(main)
