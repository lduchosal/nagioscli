"""Error handlers and formatters for click CLI."""

import sys
from typing import NoReturn

import click

from nagioscli.core.exceptions import (
    AuthenticationError,
    ConfigurationError,
    NagiosAPIError,
    NotFoundError,
)


def handle_error(error: Exception, verbose: int = 0) -> NoReturn:
    """Handle exceptions and exit with appropriate code.

    Args:
        error: Exception to handle
        verbose: Verbosity level

    Exit codes:
        1 - General error
        2 - Configuration error
        3 - Authentication error
        4 - API error
        5 - Not found
    """
    if verbose >= 1:
        click.echo(f"DEBUG: {type(error).__name__}: {error}", err=True)

    if isinstance(error, ConfigurationError):
        click.echo(f"Configuration error: {error}", err=True)
        sys.exit(2)
    elif isinstance(error, AuthenticationError):
        click.echo(f"Authentication error: {error}", err=True)
        sys.exit(3)
    elif isinstance(error, NagiosAPIError):
        click.echo(f"API error: {error}", err=True)
        sys.exit(4)
    elif isinstance(error, NotFoundError):
        click.echo(f"Not found: {error}", err=True)
        sys.exit(5)
    else:
        click.echo(f"Error: {error}", err=True)
        sys.exit(1)


class OutputFormatter:
    """Output formatters for different verbosity levels."""

    @staticmethod
    def format_verbose(message: str, verbose_level: int, min_level: int = 1) -> None:
        """Print message if verbosity is high enough."""
        if verbose_level >= min_level:
            click.echo(f"DEBUG: {message}", err=True)

    @staticmethod
    def format_service_status(status: int) -> str:
        """Format service status as text."""
        status_map = {2: "OK", 4: "WARNING", 8: "CRITICAL", 16: "UNKNOWN"}
        return status_map.get(status, f"UNKNOWN({status})")

    @staticmethod
    def format_host_status(status: int) -> str:
        """Format host status as text."""
        status_map = {2: "UP", 4: "DOWN", 8: "UNREACHABLE"}
        return status_map.get(status, f"UNKNOWN({status})")
