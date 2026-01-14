"""CLI module for nagioscli."""

import click

from .commands import register_all_commands


@click.group()
@click.version_option()
def main() -> None:
    """Nagios CLI - Manage Nagios Core via HTTP REST API."""
    pass


# Register all commands
register_all_commands(main)
