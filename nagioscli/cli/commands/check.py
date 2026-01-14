"""Check commands for CLI."""

from typing import Any

import click

from nagioscli.core.client import NagiosClient
from nagioscli.core.config import load_config

from ..decorators import common_options
from ..handlers import OutputFormatter, handle_error


def register_check_commands(main_group: Any) -> None:
    """Register check commands with the main CLI group."""

    @main_group.command("check")
    @click.argument("hostname")
    @click.argument("service")
    @common_options
    def check_cmd(
        hostname: str,
        service: str,
        config: str,
        verbose: int,
    ) -> None:
        """Force immediate service check."""
        try:
            cfg = load_config(config)
            client = NagiosClient(cfg, verbose=verbose)

            OutputFormatter.format_verbose(
                f"Forcing check for {hostname}/{service}", verbose
            )

            success = client.force_service_check(hostname, service)

            if success:
                click.echo(f"Force check submitted for {hostname}/{service}")
            else:
                click.echo(f"Failed to submit force check for {hostname}/{service}")

        except Exception as e:
            handle_error(e, verbose)

    @main_group.command("check-host")
    @click.argument("hostname")
    @common_options
    def check_host_cmd(
        hostname: str,
        config: str,
        verbose: int,
    ) -> None:
        """Force immediate host check."""
        try:
            cfg = load_config(config)
            client = NagiosClient(cfg, verbose=verbose)

            OutputFormatter.format_verbose(f"Forcing check for host {hostname}", verbose)

            success = client.force_host_check(hostname)

            if success:
                click.echo(f"Force check submitted for host {hostname}")
            else:
                click.echo(f"Failed to submit force check for host {hostname}")

        except Exception as e:
            handle_error(e, verbose)
