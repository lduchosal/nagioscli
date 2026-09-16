"""CLI module for nagioscli."""

import io
import sys

import click

from nagioscli import __version__

from .commands import register_all_commands


def _tolerate_unencodable_stdout() -> None:
    """Print unencodable characters as ``?`` instead of crashing.

    A Windows stdout redirected to a pipe or file uses the locale codec
    (cp1252), which cannot encode everything a plugin output may carry —
    e.g. the U+FFFD produced by the client's tolerant decoding (ken #1104).
    A non-strict policy chosen by the user (PYTHONIOENCODING) is kept.
    """
    stdout = sys.stdout
    if isinstance(stdout, io.TextIOWrapper) and stdout.errors == "strict":
        stdout.reconfigure(errors="replace")


@click.group()
@click.version_option(version=__version__, prog_name="nagioscli")
def main() -> None:
    """Nagios CLI - Manage Nagios Core via HTTP REST API."""
    _tolerate_unencodable_stdout()


# Register all commands
register_all_commands(main)
