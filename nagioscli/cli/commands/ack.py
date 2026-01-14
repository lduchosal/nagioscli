"""Acknowledge commands for CLI."""

from typing import Any

import click

from nagioscli.core.client import NagiosClient
from nagioscli.core.config import load_config

from ..decorators import common_options
from ..handlers import OutputFormatter, handle_error


def register_ack_commands(main_group: Any) -> None:
    """Register acknowledge commands with the main CLI group."""

    @main_group.command("ack")
    @click.argument("hostname")
    @click.argument("service")
    @click.argument("comment")
    @common_options
    def ack_cmd(
        hostname: str,
        service: str,
        comment: str,
        config: str,
        verbose: int,
    ) -> None:
        """Acknowledge a service problem."""
        try:
            cfg = load_config(config)
            client = NagiosClient(cfg, verbose=verbose)

            OutputFormatter.format_verbose(
                f"Acknowledging {hostname}/{service}", verbose
            )

            success = client.acknowledge_service(hostname, service, comment)

            if success:
                click.echo(f"Acknowledged {hostname}/{service}")
            else:
                click.echo(f"Failed to acknowledge {hostname}/{service}")

        except Exception as e:
            handle_error(e, verbose)

    @main_group.command("ack-host")
    @click.argument("hostname")
    @click.argument("comment")
    @common_options
    def ack_host_cmd(
        hostname: str,
        comment: str,
        config: str,
        verbose: int,
    ) -> None:
        """Acknowledge a host problem."""
        try:
            cfg = load_config(config)
            client = NagiosClient(cfg, verbose=verbose)

            OutputFormatter.format_verbose(f"Acknowledging host {hostname}", verbose)

            success = client.acknowledge_host(hostname, comment)

            if success:
                click.echo(f"Acknowledged host {hostname}")
            else:
                click.echo(f"Failed to acknowledge host {hostname}")

        except Exception as e:
            handle_error(e, verbose)
